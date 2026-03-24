"""
ET0 (Reference Evapotranspiration) Calculation Service

Provides a unified interface for calculating ET0 using different methods.
Supports both Penman-Monteith and Hargreaves methods with configurable selection.
"""

import logging
import math
from typing import Dict, Any, Optional
from datetime import date

import pandas as pd
import pyet as et

logger = logging.getLogger(__name__)


class ET0Service:
    """
    Service for calculating reference evapotranspiration (ET0).
    
    Supports multiple calculation methods:
    - penman_monteith: FAO-56 Penman-Monteith (requires full weather data)
    - hargreaves: Simplified Hargreaves (requires only temperature data)
    """
    
    VALID_METHODS = ["penman_monteith", "hargreaves"]
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize ET0 service with configuration.
        
        Args:
            config: Optional configuration dict with keys:
                - default_method: Method to use ("penman_monteith" or "hargreaves")
                - fallback_value: Default ET0 if calculation fails
        """
        if config is None:
            config = {}
        
        self.default_method = config.get("default_method", "penman_monteith")
        self.fallback_value = config.get("fallback_value", 2.0)
        
        if self.default_method not in self.VALID_METHODS:
            logger.warning(
                f"Invalid ET0 method '{self.default_method}', using 'penman_monteith'"
            )
            self.default_method = "penman_monteith"
        
        logger.info(f"ET0Service initialized with method: {self.default_method}")
    
    def calculate_et0(
        self,
        weather_data: Dict[str, float],
        location: Dict[str, float],
        day_of_year: date,
        method: Optional[str] = None
    ) -> float:
        """
        Calculate ET0 using specified or default method.
        
        Args:
            weather_data: Dictionary with weather variables:
                - t_min: Minimum temperature (°C)
                - t_max: Maximum temperature (°C)
                - t_avg: Average temperature (°C)
                - rh_avg: Average relative humidity (%) [optional for Hargreaves]
                - rs_mj_m2: Solar radiation (MJ/m²/day) [optional for Hargreaves]
                - u2_m_s: Wind speed at 2m (m/s) [optional for Hargreaves]
            location: Dictionary with location data:
                - lat: Latitude (degrees)
                - elevation_m: Elevation (meters)
            day_of_year: Date for calculation
            method: Override default method ("penman_monteith" or "hargreaves")
        
        Returns:
            ET0 value in mm/day
        """
        use_method = method or self.default_method

        if use_method not in self.VALID_METHODS:
            logger.warning(f"Invalid method '{use_method}', using default")
            use_method = self.default_method

        # pyet requires a DatetimeIndex on all Series for Ra calculation.
        # Keep the original date object; if an integer DOY was passed, reconstruct
        # a synthetic date (current year) so we can build the index.
        if isinstance(day_of_year, int):
            from datetime import date as _date, timedelta
            sim_date: date = _date(date.today().year, 1, 1) + timedelta(days=day_of_year - 1)
        else:
            sim_date = day_of_year

        try:
            if use_method == "hargreaves":
                return self._calculate_hargreaves(weather_data, location, sim_date)
            else:
                return self._calculate_penman_monteith(weather_data, location, sim_date)
        except Exception as e:
            logger.error(f"ET0 calculation failed: {e}", exc_info=True)
            return self.fallback_value
    
    def _calculate_hargreaves(
        self,
        weather_data: Dict[str, float],
        location: Dict[str, float],
        day_of_year: date,
    ) -> float:
        """
        Calculate ET0 using Hargreaves equation.

        Requires: t_min, t_max, t_avg, lat
        """
        try:
            t_min = weather_data["t_min"]
            t_max = weather_data["t_max"]
            t_avg = weather_data["t_avg"]
            lat_deg = location["lat"]

            # pyet needs a DatetimeIndex for Ra computation and lat in radians.
            idx = pd.DatetimeIndex([day_of_year])
            lat_rad = math.radians(lat_deg)

            tmean = pd.Series([t_avg], index=idx)
            tmax  = pd.Series([t_max], index=idx)
            tmin  = pd.Series([t_min], index=idx)

            et0_series = et.hargreaves(tmean, tmax, tmin, lat=lat_rad)
            et0_value = et0_series.iloc[0]

            return float(et0_value) if et0_value > 0 else 0.0
        except KeyError as e:
            logger.error(f"Missing required data for Hargreaves: {e}")
            return self.fallback_value
        except Exception as e:
            logger.error(f"Hargreaves calculation error: {e}", exc_info=True)
            return self.fallback_value
    
    def _calculate_penman_monteith(
        self,
        weather_data: Dict[str, float],
        location: Dict[str, float],
        day_of_year: date,
    ) -> float:
        """
        Calculate ET0 using FAO-56 Penman-Monteith equation.

        Requires: t_min, t_max, t_avg, rh_avg OR ea_kpa, rs_mj_m2, u2_m_s, lat,
        elevation_m.  Falls back to Hargreaves if data is incomplete.

        Humidity precedence:
          1. ea_kpa  — measured actual vapour pressure from dewpoint (kPa)
          2. rh_avg  — estimated relative humidity (%)
        """
        try:
            # Check for required variables (humidity: ea_kpa OR rh_avg)
            has_ea = "ea_kpa" in weather_data and weather_data["ea_kpa"] is not None and not pd.isna(weather_data["ea_kpa"])
            required_base = ["t_min", "t_max", "t_avg", "rs_mj_m2", "u2_m_s"]
            if not has_ea:
                required_base.append("rh_avg")
            missing = [v for v in required_base if v not in weather_data or pd.isna(weather_data[v])]

            if missing:
                logger.warning(
                    f"Missing variables for Penman-Monteith: {missing}. "
                    "Falling back to Hargreaves."
                )
                return self._calculate_hargreaves(weather_data, location, day_of_year)

            # Extract values
            t_min     = weather_data["t_min"]
            t_max     = weather_data["t_max"]
            t_avg     = weather_data["t_avg"]
            rs_mj_m2  = weather_data["rs_mj_m2"]
            u2_m_s    = weather_data["u2_m_s"]
            elevation_m = location["elevation_m"]
            lat_deg   = location["lat"]

            # pyet needs DatetimeIndex for Ra and lat in radians.
            idx      = pd.DatetimeIndex([day_of_year])
            lat_rad  = math.radians(lat_deg)

            tmean = pd.Series([t_avg],    index=idx)
            tmax  = pd.Series([t_max],    index=idx)
            tmin  = pd.Series([t_min],    index=idx)
            wind  = pd.Series([u2_m_s],   index=idx)

            doy_int = day_of_year.timetuple().tm_yday

            # Humidity: prefer measured ea_kpa (FAO-56 Eq. 14) over estimated rh
            if has_ea:
                ea_kpa = weather_data["ea_kpa"]
                ea_for_rn = ea_kpa
                ea_series = pd.Series([ea_kpa], index=idx)
                rn_val = self._compute_rn(
                    rs_mj_m2, t_max, t_min, ea_for_rn, lat_rad, doy_int, elevation_m
                )
                rn_series = pd.Series([rn_val], index=idx)
                et0_series = et.pm(
                    tmean, wind, rn=rn_series,
                    elevation=elevation_m, lat=lat_rad,
                    tmax=tmax, tmin=tmin,
                    ea=ea_series,
                )
                logger.debug(
                    f"PM using measured ea_kpa={ea_kpa:.4f} kPa, Rn={rn_val:.3f} MJ/m2/day"
                )
            else:
                rh_avg = weather_data["rh_avg"]
                # Estimate ea from rh for Rnl (FAO-56 Eq. 11)
                es_tavg = 0.6108 * math.exp(17.27 * t_avg / (t_avg + 237.3))
                ea_for_rn = (rh_avg / 100.0) * es_tavg
                rh = pd.Series([rh_avg], index=idx)
                rn_val = self._compute_rn(
                    rs_mj_m2, t_max, t_min, ea_for_rn, lat_rad, doy_int, elevation_m
                )
                rn_series = pd.Series([rn_val], index=idx)
                et0_series = et.pm(
                    tmean, wind, rn=rn_series,
                    elevation=elevation_m, lat=lat_rad,
                    tmax=tmax, tmin=tmin,
                    rh=rh,
                )
                logger.debug(
                    f"PM using estimated rh_avg={rh_avg:.1f}%, Rn={rn_val:.3f} MJ/m2/day"
                )
            et0_value = et0_series.iloc[0]
            
            # Validate result
            if pd.isna(et0_value) or et0_value < 0:
                logger.warning(
                    f"Penman-Monteith returned invalid value ({et0_value}). "
                    "Falling back to Hargreaves."
                )
                return self._calculate_hargreaves(weather_data, location, day_of_year)
            
            return float(et0_value)
        except KeyError as e:
            logger.error(f"Missing required data for Penman-Monteith: {e}")
            return self._calculate_hargreaves(weather_data, location, day_of_year)
        except Exception as e:
            logger.error(f"Penman-Monteith calculation error: {e}", exc_info=True)
            return self.fallback_value

    def _compute_rn(
        self,
        rs_mj_m2: float,
        t_max_c: float,
        t_min_c: float,
        ea_kpa: float,
        lat_rad: float,
        doy: int,
        elevation_m: float,
    ) -> float:
        """Net radiation Rn (MJ/m²/day) per FAO-56 Equations 21, 37-39.

        Args:
            rs_mj_m2:   Incoming shortwave radiation (MJ/m²/day) from Open-Meteo.
            t_max_c:    Daily maximum temperature (°C).
            t_min_c:    Daily minimum temperature (°C).
            ea_kpa:     Actual vapour pressure from dewpoint (kPa).
            lat_rad:    Site latitude in radians.
            doy:        Day of year (1–365).
            elevation_m: Site elevation above sea level (m).

        Returns:
            Rn in MJ/m²/day (always ≥ 0).
        """
        # ── Extraterrestrial radiation Ra (FAO-56 Eq. 21) ────────────────────
        dr   = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
        decl = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
        ws   = math.acos(-math.tan(lat_rad) * math.tan(decl))
        Ra   = (24 * 60 / math.pi) * 0.0820 * dr * (
            ws * math.sin(lat_rad) * math.sin(decl)
            + math.cos(lat_rad) * math.cos(decl) * math.sin(ws)
        )
        Ra = max(Ra, 0.0)

        # ── Clear-sky radiation Rso (FAO-56 Eq. 37) ──────────────────────────
        Rso = (0.75 + 2e-5 * elevation_m) * Ra
        Rso = max(Rso, 0.1)

        # ── Net shortwave Rns (FAO-56 Eq. 38, albedo = 0.23) ─────────────────
        Rns = 0.77 * rs_mj_m2

        # ── Net longwave Rnl (FAO-56 Eq. 39) ─────────────────────────────────
        T_max_K = t_max_c + 273.16
        T_min_K = t_min_c + 273.16
        sigma   = 4.903e-9          # Stefan-Boltzmann MJ K⁻⁴ m⁻² day⁻¹
        Rs_Rso  = min(1.0, rs_mj_m2 / Rso)
        Rnl = (
            sigma
            * (T_max_K**4 + T_min_K**4) / 2
            * (0.34 - 0.14 * math.sqrt(max(ea_kpa, 0.01)))
            * (1.35 * Rs_Rso - 0.35)
        )
        Rnl = max(0.0, Rnl)

        return Rns - Rnl
