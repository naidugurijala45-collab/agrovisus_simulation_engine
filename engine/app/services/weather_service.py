# AGROVISUS_SIMULATION_ENGINE/app/services/weather_service.py
"""
Unified Weather Service with API integration and multi-level fallback.

Fallback chain (tries in order):
1. OpenWeatherMap API (if api_key provided)
2. Open-Meteo API (free, no key needed, 10k requests/day)
3. Local CSV file (existing hourly_weather.csv)
4. Synthetic data generation (always available)

Usage:
    weather_service = WeatherService(config)
    daily_data = weather_service.get_daily_weather(lat, lon, date)
"""

import calendar
import logging
import os
import json
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from pathlib import Path

import numpy as np
import pandas as pd

from app.utils.exceptions import (
    WeatherDataError as _WeatherDataError,
    NoWeatherDataError as _NoWeatherDataError,
    WeatherQualityError,
)

logger = logging.getLogger(__name__)

# Cache directory for API responses
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".weather_cache")

# Physical limits for weather data quality checks
_WEATHER_LIMITS = {
    "avg_temp_c": (-60.0, 60.0),
    "min_temp_c": (-70.0, 60.0),
    "max_temp_c": (-60.0, 65.0),
    "total_precip_mm": (0.0, 500.0),
    "avg_humidity": (0.0, 100.0),
    "max_humidity_percent": (0.0, 100.0),
    "avg_wind_speed_m_s": (0.0, 75.0),
    "total_solar_rad_mj_m2": (0.0, 50.0),
}


# ── NOAA Illinois precipitation climatology (1991-2020 normals) ──────────────
# Monthly totals (mm) for central Illinois.  Used to calibrate the synthetic
# precipitation fallback so simulated rain matches real-world climate norms.
_IL_MONTHLY_PRECIP_MM = {
    1: 50.0, 2: 48.0, 3: 64.0, 4:  79.0, 5:  97.0, 6: 102.0,
    7: 99.0, 8: 89.0, 9: 84.0, 10: 69.0, 11: 66.0, 12:  57.0,
}

# Fraction of days per month with measurable precipitation (wet-day probability).
# spring/summer 0.35-0.40, winter 0.30-0.35.
_IL_WET_DAY_PROB = {
    1: 0.30, 2: 0.30, 3: 0.33, 4: 0.35, 5: 0.38, 6: 0.40,
    7: 0.38, 8: 0.35, 9: 0.33, 10: 0.32, 11: 0.33, 12: 0.30,
}

# Growing-season months (May-Aug) where consecutive dry days are capped.
_DRY_SPELL_CAP_MONTHS = frozenset({5, 6, 7, 8})
_MAX_CONSECUTIVE_DRY_DAYS = 5

# Backward-compatible aliases so existing imports still work
class WeatherServiceError(_WeatherDataError):
    """Base exception for weather service errors (legacy alias)."""
    pass


class NoWeatherDataError(_NoWeatherDataError):
    """Raised when no weather data could be obtained (legacy alias)."""
    pass


class WeatherService:
    """
    Unified weather data service with automatic fallback chain.

    Priority order:
    1. OpenWeatherMap API (if api_key provided)
    2. Open-Meteo API (free, no key required)
    3. Local CSV file (if path provided and file exists)
    4. Synthetic data generation (always available)
    """

    # ── ERA5-Land → gridMET bias correction (Corn Belt, 36–48°N) ─────────────
    # Monthly multiplicative scaling factors for central Illinois.
    # Corrects ERA5-Land JJA dry bias vs gridMET (USDA reference).
    # Source: ERA5 vs PRISM/gridMET evaluation literature.
    # JJA convective-precip underestimate: 10–30 %.
    _ILLINOIS_PRECIP_SCALE: Dict[int, float] = {
        1: 1.00, 2: 1.00, 3: 1.00, 4: 1.05,
        5: 1.05, 6: 1.15, 7: 1.20, 8: 1.15,
        9: 1.05, 10: 1.00, 11: 1.00, 12: 1.00,
    }
    # Suppress ERA5's spurious sub-threshold drizzle events.
    _DRIZZLE_THRESHOLD_MM: float = 0.5

    def __init__(self, config: Dict[str, Any], project_root: str = ""):
        self.project_root = project_root
        self.config = config

        # API configuration
        weather_config = config.get("weather_service", {})
        self.api_key = weather_config.get("openweathermap_api_key", "")
        self.cache_enabled = weather_config.get("cache_enabled", True)
        self.cache_ttl_hours = weather_config.get("cache_ttl_hours", 24)

        # CSV fallback path
        csv_path = config.get("historical_data_paths", {}).get("hourly_weather_csv", "")
        if csv_path and not os.path.isabs(csv_path):
            csv_path = os.path.join(project_root, csv_path)
        self.csv_path = csv_path

        # In-memory cache for loaded CSV data
        self._csv_data: Optional[pd.DataFrame] = None
        self._csv_daily_cache: Dict[date, Dict] = {}

        # API request tracking (rate limiting)
        self._api_calls_today = 0
        self._api_call_timestamps: List[float] = []

        # In-memory cache for prefetched Open-Meteo range data (date -> dict)
        self._openmeteo_daily_cache: Dict[date, Dict] = {}

        # Consecutive dry day counter — used by the synthetic precipitation model
        # to enforce the Illinois growing-season dry-spell cap (≤5 days May-Aug).
        self._consecutive_dry_days: int = 0

        # Month-to-date precipitation tracker — used to prevent extreme monthly
        # deficits by boosting wet-day probability when too far below NOAA normal.
        self._synthetic_month: int = 0
        self._synthetic_month_precip_mm: float = 0.0

        # Setup cache directory
        if self.cache_enabled:
            os.makedirs(CACHE_DIR, exist_ok=True)

        # Log configuration
        sources = []
        if self.api_key:
            sources.append("OpenWeatherMap API")
        if self.csv_path and os.path.exists(self.csv_path):
            sources.append(f"CSV ({os.path.basename(self.csv_path)})")
        sources.append("Synthetic data (fallback)")
        logger.info(f"WeatherService initialized. Sources: {', '.join(sources)}")

    # ── Public API ─────────────────────────────────────────────

    def get_daily_weather(
        self, lat: float, lon: float, target_date: date
    ) -> Dict[str, Any]:
        """
        Get daily aggregated weather data for a specific date and location.

        Tries sources in order: API → CSV → Synthetic

        Returns dict with keys:
            total_precip_mm, avg_temp_c, min_temp_c, max_temp_c,
            avg_humidity, avg_wind_speed_m_s, total_solar_rad_mj_m2,
            max_humidity_percent, source
        """
        errors = []
        weather_config = self.config.get("weather_service", {})
        preferred_source = weather_config.get("preferred_source", "auto")

        # 0. Try CSV first if preferred
        if preferred_source == "csv" and self.csv_path:
            try:
                data = self._fetch_from_csv(target_date)
                if data:
                    data["source"] = "csv"
                    return self._validate_weather_data(data)
            except Exception as e:
                errors.append(f"CSV (preferred): {e}")
                logger.warning(f"Preferred CSV source failed: {e}")

        # 1. Try OpenWeatherMap API
        if self.api_key:
            try:
                data = self._fetch_from_api(lat, lon, target_date)
                if data:
                    data["source"] = "openweathermap"
                    return self._validate_weather_data(data)
            except Exception as e:
                errors.append(f"OpenWeatherMap: {e}")
                logger.warning(f"OpenWeatherMap API failed: {e}")

        # 2. Try Open-Meteo (free, no key required)
        try:
            data = self._fetch_from_open_meteo(lat, lon, target_date)
            if data:
                data["source"] = "open_meteo"
                return self._validate_weather_data(data)
        except Exception as e:
            errors.append(f"Open-Meteo: {e}")
            logger.warning(f"Open-Meteo API failed: {e}")

        # 3. Try CSV (if not already tried or failed)
        if self.csv_path and preferred_source != "csv":
            try:
                data = self._fetch_from_csv(target_date)
                if data:
                    data["source"] = "csv"
                    return self._validate_weather_data(data)
            except Exception as e:
                errors.append(f"CSV: {e}")
                logger.warning(f"CSV fallback failed: {e}")

        # 4. Generate synthetic data (always succeeds)
        logger.info(f"Using synthetic weather for {target_date}")
        data = self._generate_synthetic_daily(lat, target_date)
        data["source"] = "synthetic"
        return data

    def get_hourly_weather(
        self, lat: float, lon: float, target_date: date
    ) -> Optional[List[Dict]]:
        """
        Get hourly weather records for a specific date.
        Used by disease model for leaf wetness calculation.

        Returns list of hourly dicts or None.
        """
        # Try CSV first (has hourly data)
        if self.csv_path:
            try:
                df = self._load_csv_data()
                if df is not None:
                    day_data = df[df.index.date == target_date]
                    if not day_data.empty:
                        return day_data.to_dict('records')
            except Exception as e:
                logger.warning(f"Failed to get hourly CSV data: {e}")

        # API hourly data (if available)
        if self.api_key:
            try:
                return self._fetch_hourly_from_api(lat, lon, target_date)
            except Exception as e:
                logger.warning(f"Failed to get hourly API data: {e}")

        # Generate synthetic hourly
        return self._generate_synthetic_hourly(lat, target_date)

    def get_date_range(self) -> Optional[tuple]:
        """Return (min_date, max_date) of available CSV data, or None."""
        df = self._load_csv_data()
        if df is not None and not df.empty:
            return (df.index.min().date(), df.index.max().date())
        return None

    def get_available_dates(self) -> List[date]:
        """Return sorted list of dates with available CSV data."""
        df = self._load_csv_data()
        if df is not None and not df.empty:
            return sorted(list(set(df.index.date)))
        return []

    def prefetch_date_range(self, lat: float, lon: float, start_date: date, end_date: date):
        """
        Fetch the entire simulation date range from Open-Meteo in ONE API call.

        Results are stored in self._openmeteo_daily_cache so per-day calls in
        get_daily_weather() skip the network entirely and return instantly.
        Falls back silently — per-day fetches still work if this fails.
        Open-Meteo Archive only covers data up to ~5 days ago; skip the call
        for current or future date ranges (synthetic will be used instead).
        """
        cutoff = date.today() - timedelta(days=5)
        # If the entire range is beyond the archive cutoff, nothing to fetch
        if start_date >= cutoff:
            logger.info("Prefetch skipped: date range is too recent for Open-Meteo Archive.")
            return
        # Clamp end_date to what the archive actually has
        effective_end = min(end_date, cutoff)
        end_date = effective_end
        try:
            import urllib.request

            url = (
                f"https://archive-api.open-meteo.com/v1/archive"
                f"?latitude={lat}&longitude={lon}"
                f"&start_date={start_date.isoformat()}&end_date={end_date.isoformat()}"
                f"&daily=temperature_2m_max,temperature_2m_min,"
                f"temperature_2m_mean,precipitation_sum,"
                f"windspeed_10m_max,shortwave_radiation_sum"
                f"&hourly=dewpoint_2m"
                f"&timezone=auto"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "AgroVisus/1.0"})
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = json.loads(response.read().decode())

            daily = raw.get("daily", {})
            times = daily.get("time", [])
            if not times:
                return

            t_max_list   = daily.get("temperature_2m_max", [])
            t_min_list   = daily.get("temperature_2m_min", [])
            t_mean_list  = daily.get("temperature_2m_mean", [None] * len(times))
            precip_list  = daily.get("precipitation_sum", [0.0] * len(times))
            wind_list    = daily.get("windspeed_10m_max", [2.0] * len(times))
            solar_list   = daily.get("shortwave_radiation_sum", [None] * len(times))

            # Build per-date dewpoint lookup from the accompanying hourly block
            hourly_raw       = raw.get("hourly", {})
            hourly_times_raw = hourly_raw.get("time", [])
            hourly_td_raw    = hourly_raw.get("dewpoint_2m", [])
            td_by_date: Dict[str, List[float]] = {}
            for j, t_str in enumerate(hourly_times_raw):
                d_str = t_str[:10]  # "YYYY-MM-DD"
                if j < len(hourly_td_raw) and hourly_td_raw[j] is not None:
                    td_by_date.setdefault(d_str, []).append(float(hourly_td_raw[j]))

            for i, date_str in enumerate(times):
                d = date.fromisoformat(date_str)
                t_max  = t_max_list[i] if i < len(t_max_list) else 25.0
                t_min  = t_min_list[i] if i < len(t_min_list) else 15.0
                t_mean = t_mean_list[i] if (i < len(t_mean_list) and t_mean_list[i] is not None) else (t_max + t_min) / 2.0
                precip = precip_list[i] or 0.0 if i < len(precip_list) else 0.0
                wind_max = wind_list[i] or 2.0 if i < len(wind_list) else 2.0
                wind_avg_ms = (wind_max / 3.6) * 0.748  # FAO-56 10 m → 2 m
                solar = solar_list[i] if (i < len(solar_list) and solar_list[i] is not None) else self._estimate_solar_radiation(lat, d, 60.0)
                # FAO-56 Eq. 12: es = (e°(Tmax) + e°(Tmin)) / 2
                es_tmax_d = 0.6108 * np.exp(17.27 * t_max / (t_max + 237.3))
                es_tmin_d = 0.6108 * np.exp(17.27 * t_min / (t_min + 237.3))
                es_d      = (es_tmax_d + es_tmin_d) / 2.0

                td_vals = td_by_date.get(date_str, [])
                if td_vals:
                    td_mean_d  = sum(td_vals) / len(td_vals)
                    td_max_d   = max(td_vals)
                    ea_d       = self._dewpoint_to_ea(td_mean_d)
                    rh_d       = max(0.0, min(100.0, 100.0 * ea_d / es_d)) if es_d > 0 else 60.0
                    ea_max_d   = self._dewpoint_to_ea(td_max_d)
                    rh_max_d   = min(100.0, 100.0 * ea_max_d / es_tmin_d) if es_tmin_d > 0 else rh_d
                    dewpoint_d = round(td_mean_d, 2)
                    ea_kpa_d   = round(ea_d, 4)
                else:
                    diurnal_range = max(1, t_max - t_min)
                    rh_d       = max(30.0, min(95.0, 85.0 - diurnal_range * 1.5))
                    rh_max_d   = min(100.0, rh_d + 15.0)
                    ea_kpa_d   = round((rh_d / 100.0) * es_d, 4)
                    dewpoint_d = None

                # Precipitation bias correction
                precip_raw_d      = float(precip)
                precip_corrected_d = self._bias_correct_precip(precip_raw_d, d.month, lat)
                self._openmeteo_daily_cache[d] = {
                    "total_precip_mm":        round(precip_corrected_d,   2),
                    "avg_temp_c":             round(float(t_mean),        2),
                    "min_temp_c":             round(float(t_min),         2),
                    "max_temp_c":             round(float(t_max),         2),
                    "avg_humidity":           round(rh_d,                 2),
                    "max_humidity_percent":   round(rh_max_d,             2),
                    "avg_wind_speed_m_s":     round(wind_avg_ms,          2),
                    "total_solar_rad_mj_m2":  round(float(solar),         2),
                    "dewpoint_c":             dewpoint_d,
                    "ea_kpa":                 ea_kpa_d,
                    "precip_bias_corrected":  precip_corrected_d != precip_raw_d,
                }

            logger.info(
                f"Weather prefetch complete: {len(self._openmeteo_daily_cache)} days "
                f"({start_date} to {end_date}) in one API call."
            )
        except Exception as e:
            logger.warning(f"Open-Meteo prefetch failed, will fetch per-day: {e}")

    # ── Data Quality Validation ─────────────────────────────────

    def _validate_weather_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and clamp weather data to physically plausible ranges.

        Logs warnings for clamped values. Returns the (possibly corrected) dict.
        """
        for key, (lo, hi) in _WEATHER_LIMITS.items():
            if key not in data:
                continue
            val = data[key]
            if val is None:
                continue
            if val < lo or val > hi:
                clamped = max(lo, min(hi, val))
                logger.warning(
                    f"Weather quality: {key}={val:.2f} outside [{lo}, {hi}], "
                    f"clamped to {clamped:.2f}"
                )
                data[key] = clamped

        # Ensure min_temp <= avg_temp <= max_temp
        t_min = data.get("min_temp_c")
        t_max = data.get("max_temp_c")
        t_avg = data.get("avg_temp_c")
        if t_min is not None and t_max is not None and t_min > t_max:
            logger.warning(
                f"Weather quality: min_temp ({t_min:.1f}) > max_temp ({t_max:.1f}), swapping."
            )
            data["min_temp_c"], data["max_temp_c"] = t_max, t_min
            t_min, t_max = t_max, t_min

        if t_avg is not None and t_min is not None and t_max is not None:
            if t_avg < t_min or t_avg > t_max:
                data["avg_temp_c"] = (t_min + t_max) / 2.0

        return data

    # ── OpenWeatherMap API ─────────────────────────────────────

    def _fetch_from_api(
        self, lat: float, lon: float, target_date: date
    ) -> Optional[Dict]:
        """Fetch daily weather from OpenWeatherMap API."""
        # Check cache first
        cached = self._get_cached_api_response(lat, lon, target_date)
        if cached is not None:
            return cached

        # Rate limiting: max 60 calls/minute
        self._enforce_rate_limit()

        try:
            import urllib.request
            import urllib.error

            # Use One Call API 3.0 for historical/current data
            # For dates in the past, use history endpoint
            # For today/future, use forecast
            days_diff = (target_date - date.today()).days

            if days_diff <= 0:
                # Historical or today - use history/timemachine
                dt_unix = int(datetime.combine(target_date, datetime.min.time()).timestamp())
                url = (
                    f"https://api.openweathermap.org/data/2.5/onecall/timemachine"
                    f"?lat={lat}&lon={lon}&dt={dt_unix}"
                    f"&appid={self.api_key}&units=metric"
                )
            else:
                # Future - use forecast
                url = (
                    f"https://api.openweathermap.org/data/2.5/forecast"
                    f"?lat={lat}&lon={lon}"
                    f"&appid={self.api_key}&units=metric"
                )

            req = urllib.request.Request(url, headers={"User-Agent": "AgroVisus/1.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                raw_data = json.loads(response.read().decode())

            self._api_calls_today += 1
            self._api_call_timestamps.append(time.time())

            # Parse response into our standard format
            result = self._parse_owm_response(raw_data, target_date)

            # Cache the result
            if result and self.cache_enabled:
                self._cache_api_response(lat, lon, target_date, result)

            return result

        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise WeatherServiceError(
                    "Invalid OpenWeatherMap API key",
                    suggestion="Check your API key in config.json under weather_service.openweathermap_api_key"
                )
            elif e.code == 429:
                raise WeatherServiceError(
                    "OpenWeatherMap rate limit exceeded",
                    suggestion="Wait a few minutes or upgrade your plan"
                )
            raise
        except ImportError:
            logger.warning("urllib not available for API calls")
            return None

    def _parse_owm_response(
        self, raw_data: Dict, target_date: date
    ) -> Optional[Dict]:
        """Parse OpenWeatherMap response into standard daily format."""
        try:
            # Handle different response formats
            if "hourly" in raw_data:
                # One Call API format
                hourly = raw_data["hourly"]
                temps = [h.get("temp", 15) for h in hourly]
                humidities = [h.get("humidity", 70) for h in hourly]
                precip = sum(h.get("rain", {}).get("1h", 0) for h in hourly)
                wind_speeds = [h.get("wind_speed", 2) for h in hourly]

                return {
                    "total_precip_mm": precip,
                    "avg_temp_c": np.mean(temps),
                    "min_temp_c": min(temps),
                    "max_temp_c": max(temps),
                    "avg_humidity": np.mean(humidities),
                    "max_humidity_percent": max(humidities),
                    "avg_wind_speed_m_s": np.mean(wind_speeds),
                    "total_solar_rad_mj_m2": self._estimate_solar_radiation(
                        raw_data.get("lat", 40), target_date, np.mean(humidities)
                    ),
                }

            elif "list" in raw_data:
                # Forecast API format (3-hour intervals)
                entries = [
                    e for e in raw_data["list"]
                    if datetime.fromtimestamp(e["dt"]).date() == target_date
                ]
                if not entries:
                    return None

                temps = [e["main"]["temp"] for e in entries]
                humidities = [e["main"]["humidity"] for e in entries]
                precip = sum(e.get("rain", {}).get("3h", 0) for e in entries)
                wind_speeds = [e["wind"]["speed"] for e in entries]

                return {
                    "total_precip_mm": precip,
                    "avg_temp_c": np.mean(temps),
                    "min_temp_c": min(temps),
                    "max_temp_c": max(temps),
                    "avg_humidity": np.mean(humidities),
                    "max_humidity_percent": max(humidities),
                    "avg_wind_speed_m_s": np.mean(wind_speeds),
                    "total_solar_rad_mj_m2": self._estimate_solar_radiation(
                        raw_data.get("city", {}).get("coord", {}).get("lat", 40),
                        target_date,
                        np.mean(humidities),
                    ),
                }

            elif "current" in raw_data:
                # Current weather format
                current = raw_data["current"]
                temp = current.get("temp", 15)
                return {
                    "total_precip_mm": current.get("rain", {}).get("1h", 0),
                    "avg_temp_c": temp,
                    "min_temp_c": temp - 5,
                    "max_temp_c": temp + 5,
                    "avg_humidity": current.get("humidity", 70),
                    "max_humidity_percent": current.get("humidity", 70),
                    "avg_wind_speed_m_s": current.get("wind_speed", 2),
                    "total_solar_rad_mj_m2": self._estimate_solar_radiation(
                        raw_data.get("lat", 40), target_date,
                        current.get("humidity", 70)
                    ),
                }

        except (KeyError, IndexError, TypeError) as e:
            logger.warning(f"Failed to parse OWM response: {e}")

        return None

    def _fetch_hourly_from_api(
        self, lat: float, lon: float, target_date: date
    ) -> Optional[List[Dict]]:
        """Fetch hourly weather from API and convert to internal format."""
        # For now, generate synthetic hourly if we have daily data
        daily = self._fetch_from_api(lat, lon, target_date)
        if daily:
            return self._daily_to_synthetic_hourly(daily, target_date)
        return None

    def _enforce_rate_limit(self):
        """Enforce 60 calls/minute rate limit."""
        now = time.time()
        # Remove timestamps older than 60 seconds
        self._api_call_timestamps = [
            ts for ts in self._api_call_timestamps if now - ts < 60
        ]
        if len(self._api_call_timestamps) >= 55:  # Leave buffer
            wait_time = 60 - (now - self._api_call_timestamps[0])
            if wait_time > 0:
                logger.info(f"Rate limiting: waiting {wait_time:.1f}s")
                time.sleep(wait_time)

    # ── API Response Caching ───────────────────────────────────

    def _get_cache_path(self, lat: float, lon: float, target_date: date) -> str:
        """Get file path for cached API response."""
        key = f"{lat:.2f}_{lon:.2f}_{target_date.isoformat()}"
        return os.path.join(CACHE_DIR, f"{key}.json")

    def _get_cached_api_response(
        self, lat: float, lon: float, target_date: date
    ) -> Optional[Dict]:
        """Return cached API response if fresh enough."""
        if not self.cache_enabled:
            return None
        cache_path = self._get_cache_path(lat, lon, target_date)
        if os.path.exists(cache_path):
            age_hours = (time.time() - os.path.getmtime(cache_path)) / 3600
            if age_hours < self.cache_ttl_hours:
                try:
                    with open(cache_path, 'r') as f:
                        return json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass
        return None

    def _cache_api_response(
        self, lat: float, lon: float, target_date: date, data: Dict
    ):
        """Cache API response to disk."""
        try:
            cache_path = self._get_cache_path(lat, lon, target_date)
            # Convert numpy types to native Python types for JSON serialization
            serializable = {
                k: float(v) if isinstance(v, (np.floating, np.integer)) else v
                for k, v in data.items()
            }
            with open(cache_path, 'w') as f:
                json.dump(serializable, f)
        except (IOError, TypeError) as e:
            logger.warning(f"Failed to cache weather data: {e}")

    # ── CSV Fallback ───────────────────────────────────────────

    def _load_csv_data(self) -> Optional[pd.DataFrame]:
        """Load and cache CSV weather data."""
        if self._csv_data is not None:
            return self._csv_data

        if not self.csv_path or not os.path.exists(self.csv_path):
            return None

        try:
            df = pd.read_csv(
                self.csv_path, index_col="datetime", parse_dates=True
            )
            self._csv_data = df
            logger.info(f"CSV weather loaded: {len(df)} records")

            # Pre-compute daily cache
            self._precompute_csv_daily_cache(df)
            return df
        except Exception as e:
            logger.error(f"Failed to load CSV weather: {e}")
            return None

    def _precompute_csv_daily_cache(self, df: pd.DataFrame):
        """Pre-compute daily aggregates from hourly CSV data."""
        try:
            for day_date, group in df.groupby(df.index.date):
                self._csv_daily_cache[day_date] = {
                    "total_precip_mm": float(group["precip_mm"].sum()),
                    "avg_temp_c": float(group["temp_c"].mean()),
                    "min_temp_c": float(group["temp_c"].min()),
                    "max_temp_c": float(group["temp_c"].max()),
                    "avg_humidity": float(group["humidity"].mean()),
                    "max_humidity_percent": float(group["humidity"].max()),
                    "avg_wind_speed_m_s": float(group["daily_avg_wind_speed_m_s"].iloc[0]),
                    "total_solar_rad_mj_m2": float(group["daily_total_solar_rad_mj_m2"].iloc[0]),
                }
            logger.info(f"Pre-computed daily cache: {len(self._csv_daily_cache)} days")
        except Exception as e:
            logger.error(f"Failed to precompute daily cache: {e}")

    def _fetch_from_csv(self, target_date: date) -> Optional[Dict]:
        """Fetch daily weather from cached CSV data."""
        if not self._csv_daily_cache:
            self._load_csv_data()
        return self._csv_daily_cache.get(target_date)

    # ── Open-Meteo API (Free, no key) ──────────────────────────

    def _fetch_from_open_meteo(
        self, lat: float, lon: float, target_date: date
    ) -> Optional[Dict]:
        """
        Fetch daily weather from Open-Meteo Archive API.

        Free tier: 10,000 requests/day, no API key required.
        Covers historical data from 1940 to present-5 days.
        https://open-meteo.com/en/docs/historical-weather-api
        """
        # Check prefetched in-memory cache first (populated by prefetch_date_range)
        if target_date in self._openmeteo_daily_cache:
            return self._openmeteo_daily_cache[target_date]

        # Open-Meteo Archive API only has data up to ~5 days ago.
        # For recent or future dates, skip the HTTP call entirely.
        from datetime import date as _date
        if target_date >= _date.today() - timedelta(days=5):
            return None

        # Check disk cache
        cache_key_prefix = "openmeteo"
        cache_path = os.path.join(
            CACHE_DIR,
            f"{cache_key_prefix}_{lat:.2f}_{lon:.2f}_{target_date.isoformat()}.json",
        )
        if self.cache_enabled and os.path.exists(cache_path):
            age_hours = (time.time() - os.path.getmtime(cache_path)) / 3600
            if age_hours < self.cache_ttl_hours:
                try:
                    with open(cache_path, "r") as f:
                        return json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass

        try:
            import urllib.request
            import urllib.error

            date_str = target_date.isoformat()
            url = (
                f"https://archive-api.open-meteo.com/v1/archive"
                f"?latitude={lat}&longitude={lon}"
                f"&start_date={date_str}&end_date={date_str}"
                f"&daily=temperature_2m_max,temperature_2m_min,"
                f"temperature_2m_mean,precipitation_sum,"
                f"windspeed_10m_max,shortwave_radiation_sum"
                f"&hourly=dewpoint_2m"
                f"&timezone=auto"
            )

            req = urllib.request.Request(
                url, headers={"User-Agent": "AgroVisus/1.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                raw = json.loads(response.read().decode())

            daily = raw.get("daily", {})
            if not daily or not daily.get("time"):
                return None

            t_max = daily["temperature_2m_max"][0]
            t_min = daily["temperature_2m_min"][0]
            t_mean = daily.get("temperature_2m_mean", [None])[0]
            if t_mean is None:
                t_mean = (t_max + t_min) / 2.0

            precip = daily.get("precipitation_sum", [0])[0] or 0.0
            wind_max = daily.get("windspeed_10m_max", [2.0])[0] or 2.0
            # Convert km/h to m/s; FAO-56 10 m → 2 m height correction factor 0.748
            wind_avg_ms = (wind_max / 3.6) * 0.748

            solar = daily.get("shortwave_radiation_sum", [None])[0]
            if solar is None:
                solar = self._estimate_solar_radiation(lat, target_date, 60.0)

            # Derive RH from hourly dewpoint (actual measurement, Magnus formula)
            # FAO-56 Eq. 12: es = (e°(Tmax) + e°(Tmin)) / 2
            es_tmax = 0.6108 * np.exp(17.27 * t_max / (t_max + 237.3))
            es_tmin = 0.6108 * np.exp(17.27 * t_min / (t_min + 237.3))
            es = (es_tmax + es_tmin) / 2.0

            hourly_raw = raw.get("hourly", {})
            td_values = [v for v in hourly_raw.get("dewpoint_2m", []) if v is not None]
            if td_values:
                td_mean    = sum(td_values) / len(td_values)
                td_max_val = max(td_values)
                ea         = self._dewpoint_to_ea(td_mean)
                rh_avg     = max(0.0, min(100.0, 100.0 * ea / es)) if es > 0 else 60.0
                ea_max     = self._dewpoint_to_ea(td_max_val)
                es_min     = es_tmin
                rh_max     = min(100.0, 100.0 * ea_max / es_min) if es_min > 0 else rh_avg
                dewpoint_c = round(td_mean, 2)
                ea_kpa     = round(ea, 4)
            else:
                # Fallback: diurnal-range proxy when hourly dewpoint unavailable
                diurnal_range = max(1, t_max - t_min)
                rh_avg     = max(30.0, min(95.0, 85.0 - diurnal_range * 1.5))
                rh_max     = min(100.0, rh_avg + 15.0)
                ea         = (rh_avg / 100.0) * es
                dewpoint_c = None
                ea_kpa     = round(ea, 4)

            # Precipitation bias correction (ERA5-Land Corn Belt dry bias)
            precip_raw       = precip
            precip           = self._bias_correct_precip(precip, target_date.month, lat)
            precip_corrected = precip != precip_raw

            result = {
                "total_precip_mm": round(precip, 2),
                "avg_temp_c": round(t_mean, 2),
                "min_temp_c": round(t_min, 2),
                "max_temp_c": round(t_max, 2),
                "avg_humidity": round(rh_avg, 2),
                "max_humidity_percent": round(rh_max, 2),
                "avg_wind_speed_m_s": round(wind_avg_ms, 2),
                "total_solar_rad_mj_m2": round(solar, 2),
                "dewpoint_c": dewpoint_c,
                "ea_kpa": ea_kpa,
                "precip_bias_corrected": precip_corrected,
            }

            # Cache
            if self.cache_enabled:
                try:
                    os.makedirs(CACHE_DIR, exist_ok=True)
                    serializable = {
                        k: float(v) if isinstance(v, (np.floating, np.integer)) else v
                        for k, v in result.items()
                    }
                    with open(cache_path, "w") as f:
                        json.dump(serializable, f)
                except (IOError, TypeError) as e:
                    logger.warning(f"Failed to cache Open-Meteo data: {e}")

            return result

        except ImportError:
            logger.warning("urllib not available for Open-Meteo API calls")
            return None
        except Exception as e:
            logger.warning(f"Open-Meteo API error: {e}")
            return None

    # ── Synthetic Data Generation ──────────────────────────────

    def _generate_synthetic_daily(
        self, lat: float, target_date: date
    ) -> Dict[str, Any]:
        """
        Generate realistic synthetic daily weather based on latitude and day-of-year.
        Uses simplified climate model with seasonal variation.
        """
        doy = target_date.timetuple().tm_yday

        # Temperature model: seasonal sinusoidal with latitude adjustment
        # Northern hemisphere: warmest around day 200 (mid-July)
        lat_factor = 1.0 - abs(lat) / 90.0  # Warmer near equator
        seasonal_temp = 15 + 15 * lat_factor * np.sin(2 * np.pi * (doy - 80) / 365)

        avg_temp = seasonal_temp + np.random.normal(0, 2)
        diurnal_range = 8 + 4 * (1 - abs(np.sin(2 * np.pi * doy / 365)))
        min_temp = avg_temp - diurnal_range / 2 + np.random.normal(0, 1)
        max_temp = avg_temp + diurnal_range / 2 + np.random.normal(0, 1)

        # Humidity: inversely related to temperature
        avg_humidity = max(30, min(95, 75 - (avg_temp - 15) * 0.8 + np.random.normal(0, 5)))

        # Precipitation: calibrated to NOAA Illinois monthly normals.
        # Uses a Gamma(shape=0.8) distribution on wet days — shape < 1 gives a
        # realistic right-skewed distribution (many small events, occasional large).
        # scale = monthly_total / wet_days_per_month per NOAA specification;
        # E[amount per wet day] = shape × scale ≈ 80 % of monthly_normal (realistic).
        month = target_date.month
        days_in_month = calendar.monthrange(target_date.year, month)[1]
        monthly_normal_mm = _IL_MONTHLY_PRECIP_MM.get(month, 75.0)
        wet_day_prob = _IL_WET_DAY_PROB.get(month, 0.33)
        wet_days_per_month = wet_day_prob * days_in_month
        gamma_shape = 0.8
        gamma_scale = monthly_normal_mm / max(1.0, wet_days_per_month)

        # ── Monthly deficit correction (May-Aug only) ──────────────────────
        # Reset tracker on a new month.
        if month != self._synthetic_month:
            self._synthetic_month = month
            self._synthetic_month_precip_mm = 0.0

        # If we are in a growing-season month and the month-to-date total is
        # more than 35 % of the monthly normal BELOW the pro-rated expected
        # amount, raise wet_day_prob by up to +0.15 so future days catch up.
        effective_wet_day_prob = wet_day_prob
        if month in _DRY_SPELL_CAP_MONTHS:
            day_of_month = target_date.day
            expected_so_far = monthly_normal_mm * (day_of_month / days_in_month)
            deficit_mm = expected_so_far - self._synthetic_month_precip_mm
            if deficit_mm > 0.35 * monthly_normal_mm:
                # Scale the boost proportionally to how far behind we are,
                # capped at +0.15 (never exceed 55 % wet-day probability).
                boost = min(0.15, (deficit_mm - 0.35 * monthly_normal_mm) / monthly_normal_mm)
                effective_wet_day_prob = min(0.55, wet_day_prob + boost)

        # ── Dry-spell cap (May-Aug) ────────────────────────────────────────
        # During May-Aug, enforce ≤5 consecutive dry days to prevent
        # unrealistic month-long droughts in the Illinois growing season.
        force_wet = (
            month in _DRY_SPELL_CAP_MONTHS
            and self._consecutive_dry_days >= _MAX_CONSECUTIVE_DRY_DAYS
        )
        is_wet = force_wet or (np.random.random() < effective_wet_day_prob)

        if is_wet:
            precip = float(np.random.gamma(shape=gamma_shape, scale=gamma_scale))
            # When the dry-spell cap forces a rain event, ensure the amount is
            # agronomically meaningful (≥50% of the average event depth).
            # This prevents the pathological case where the cap fires but the
            # gamma draw is tiny, leaving soil moisture critically low.
            if force_wet:
                min_forced_mm = gamma_shape * gamma_scale * 0.5
                precip = max(precip, min_forced_mm)
            self._consecutive_dry_days = 0
        else:
            precip = 0.0
            self._consecutive_dry_days += 1

        # Update month-to-date accumulator for the deficit correction above.
        self._synthetic_month_precip_mm += precip

        # Wind speed: 1.5-4 m/s typical
        wind_speed = max(0.5, np.random.normal(2.5, 0.8))

        # Solar radiation: coupled to precipitation status.
        # On rainy days cloud cover raises effective humidity → reduces solar.
        # This correctly represents: rain = cloud cover = less shortwave radiation.
        solar_humidity = max(avg_humidity, 85.0) if is_wet else avg_humidity
        solar_rad = self._estimate_solar_radiation(lat, target_date, solar_humidity)

        return {
            "total_precip_mm": round(precip, 2),
            "avg_temp_c": round(avg_temp, 2),
            "min_temp_c": round(min_temp, 2),
            "max_temp_c": round(max_temp, 2),
            "avg_humidity": round(avg_humidity, 2),
            "max_humidity_percent": round(min(100, avg_humidity + 15), 2),
            "avg_wind_speed_m_s": round(wind_speed, 2),
            "total_solar_rad_mj_m2": round(solar_rad, 2),
        }

    def _generate_synthetic_hourly(
        self, lat: float, target_date: date
    ) -> List[Dict]:
        """Generate 24 synthetic hourly records for a date."""
        daily = self._generate_synthetic_daily(lat, target_date)
        return self._daily_to_synthetic_hourly(daily, target_date)

    def _daily_to_synthetic_hourly(
        self, daily: Dict, target_date: date
    ) -> List[Dict]:
        """Convert daily aggregate to synthetic hourly records."""
        hourly = []
        for hour in range(24):
            # Temperature: sinusoidal with peak at 14:00
            hour_frac = (hour - 6) / 24.0  # Shift so 6am is low
            temp_range = daily["max_temp_c"] - daily["min_temp_c"]
            temp = daily["avg_temp_c"] + (temp_range / 2) * np.sin(2 * np.pi * (hour - 6) / 24)

            # Humidity: inverse of temperature
            humidity = daily["avg_humidity"] - 10 * np.sin(2 * np.pi * (hour - 6) / 24)
            humidity = max(30, min(100, humidity))

            # Precipitation: distribute randomly
            precip = 0.0
            if daily["total_precip_mm"] > 0 and np.random.random() < 0.15:
                precip = daily["total_precip_mm"] * np.random.uniform(0.05, 0.3)

            dt = datetime.combine(target_date, datetime.min.time()) + timedelta(hours=hour)
            hourly.append({
                "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "temp_c": round(temp, 2),
                "humidity": round(humidity, 2),
                "precip_mm": round(precip, 2),
                "daily_total_solar_rad_mj_m2": daily.get("total_solar_rad_mj_m2", 20.0),
                "daily_avg_wind_speed_m_s": daily.get("avg_wind_speed_m_s", 2.0),
            })
        return hourly

    # ── Utility Methods ────────────────────────────────────────

    def _estimate_solar_radiation(
        self, lat: float, target_date: date, humidity: float
    ) -> float:
        """
        Estimate daily solar radiation (MJ/m²) using Hargreaves radiation formula.
        Based on extraterrestrial radiation adjusted by cloud cover (humidity proxy).
        """
        doy = target_date.timetuple().tm_yday
        lat_rad = np.radians(lat)

        # Solar declination
        decl = 0.4093 * np.sin(2 * np.pi / 365 * doy - 1.405)

        # Sunset hour angle
        cos_ws = -np.tan(lat_rad) * np.tan(decl)
        cos_ws = np.clip(cos_ws, -1, 1)
        ws = np.arccos(cos_ws)

        # Inverse relative distance Earth-Sun
        dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365)

        # Extraterrestrial radiation (Ra) in MJ/m²/day
        Gsc = 0.0820  # Solar constant
        Ra = (24 * 60 / np.pi) * Gsc * dr * (
            ws * np.sin(lat_rad) * np.sin(decl) +
            np.cos(lat_rad) * np.cos(decl) * np.sin(ws)
        )

        # Adjust for cloud cover using an Angstrom-Prescott calibration.
        # The Angstrom equation: Rs = Ra × (a + b × n/N) where
        #   a=0.25, b=0.50, n/N = fractional sunshine hours.
        # Sunshine fraction correlates inversely with humidity.
        # Calibrated for midlatitude humid continental climate (Illinois):
        #   humidity 50 % (dry)  → cloud_factor ≈ 0.55 (22 MJ/m²/day)
        #   humidity 70 % (normal) → cloud_factor ≈ 0.52 (21 MJ/m²/day)
        #   humidity 85 % (rainy) → cloud_factor ≈ 0.45 (18 MJ/m²/day)
        cloud_factor = max(0.25, min(0.55, 0.875 - 0.005 * humidity))

        return max(0, Ra * cloud_factor)

    def _dewpoint_to_ea(self, td_c: float) -> float:
        """Actual vapour pressure from dewpoint temperature (kPa). FAO-56 Eq. 14."""
        return 0.6108 * np.exp(17.27 * td_c / (td_c + 237.3))

    def _bias_correct_precip(
        self, precip_mm: float, month: int, lat: float
    ) -> float:
        """
        Apply monthly multiplicative bias correction to ERA5-Land precipitation
        for Corn Belt fields (36–48°N).

        Suppresses drizzle events below _DRIZZLE_THRESHOLD_MM.
        Returns precip_mm unchanged for locations outside the Corn Belt.
        """
        if not (36 <= lat <= 48):
            return precip_mm
        corrected = precip_mm * self._ILLINOIS_PRECIP_SCALE.get(month, 1.0)
        return 0.0 if corrected < self._DRIZZLE_THRESHOLD_MM else corrected
