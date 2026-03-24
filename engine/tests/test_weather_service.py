"""
Tests for WeatherService.

Tests cover:
- Synthetic weather generation (no API/CSV needed)
- Data quality validation (clamping, temperature consistency)
- Fallback chain behavior
- CSV loading (mocked)
- Cache behavior
"""
import os
import sys
import json
import tempfile
import shutil
from datetime import date
from unittest.mock import patch, MagicMock

import pytest
import numpy as np

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from app.services.weather_service import WeatherService, _WEATHER_LIMITS


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def basic_config():
    """Minimal config with no API key and no CSV."""
    return {
        "weather_service": {
            "openweathermap_api_key": "",
            "cache_enabled": False,
            "cache_ttl_hours": 24,
            "preferred_source": "auto",
        },
        "historical_data_paths": {},
    }


@pytest.fixture
def csv_config(tmp_path):
    """Config with a valid CSV file."""
    import pandas as pd

    csv_path = os.path.join(str(tmp_path), "test_weather.csv")

    # Create sample hourly weather CSV
    dates = pd.date_range("2024-06-01", periods=48, freq="h")
    df = pd.DataFrame(
        {
            "datetime": dates,
            "temp_c": np.random.normal(25, 3, 48),
            "humidity": np.random.normal(65, 10, 48),
            "precip_mm": np.maximum(0, np.random.normal(0, 0.5, 48)),
            "daily_avg_wind_speed_m_s": np.full(48, 2.5),
            "daily_total_solar_rad_mj_m2": np.full(48, 22.0),
        }
    )
    df.set_index("datetime", inplace=True)
    df.to_csv(csv_path)

    return {
        "weather_service": {
            "openweathermap_api_key": "",
            "cache_enabled": False,
            "preferred_source": "csv",
        },
        "historical_data_paths": {"hourly_weather_csv": csv_path},
    }


# ── Synthetic Weather Tests ───────────────────────────────────


class TestSyntheticWeather:
    """Tests that run without any API or CSV dependency."""

    def test_returns_all_required_keys(self, basic_config):
        ws = WeatherService(basic_config)
        data = ws.get_daily_weather(40.0, -88.0, date(2024, 7, 15))

        required_keys = [
            "total_precip_mm",
            "avg_temp_c",
            "min_temp_c",
            "max_temp_c",
            "avg_humidity",
            "max_humidity_percent",
            "avg_wind_speed_m_s",
            "total_solar_rad_mj_m2",
            "source",
        ]
        for key in required_keys:
            assert key in data, f"Missing key: {key}"

    def test_synthetic_source_label(self, basic_config):
        ws = WeatherService(basic_config)
        data = ws.get_daily_weather(40.0, -88.0, date(2024, 7, 15))
        # Without API key or CSV, should fall back to open_meteo or synthetic
        assert data["source"] in ("synthetic", "open_meteo")

    def test_temperature_ordering(self, basic_config):
        ws = WeatherService(basic_config)
        for _ in range(10):
            data = ws.get_daily_weather(40.0, -88.0, date(2024, 7, 15))
            if data["source"] == "synthetic":
                # Synthetic data should have reasonable temps
                assert data["min_temp_c"] <= data["max_temp_c"] + 1  # Small tolerance

    def test_non_negative_values(self, basic_config):
        ws = WeatherService(basic_config)
        data = ws.get_daily_weather(40.0, -88.0, date(2024, 7, 15))
        assert data["total_precip_mm"] >= 0
        assert data["total_solar_rad_mj_m2"] >= 0
        assert data["avg_wind_speed_m_s"] >= 0

    def test_seasonal_variation(self, basic_config):
        """Summer should be warmer than winter at mid-latitudes."""
        ws = WeatherService(basic_config)
        # Collect many samples to average out randomness
        summer_temps = []
        winter_temps = []
        for _ in range(20):
            s = ws._generate_synthetic_daily(40.0, date(2024, 7, 15))
            w = ws._generate_synthetic_daily(40.0, date(2024, 1, 15))
            summer_temps.append(s["avg_temp_c"])
            winter_temps.append(w["avg_temp_c"])

        assert np.mean(summer_temps) > np.mean(winter_temps)


# ── Data Quality Validation Tests ─────────────────────────────


class TestDataQualityValidation:
    """Test the _validate_weather_data method."""

    def test_clamps_extreme_temperature(self, basic_config):
        ws = WeatherService(basic_config)
        data = {
            "avg_temp_c": 100.0,  # Way too hot
            "min_temp_c": -80.0,  # Way too cold
            "max_temp_c": 70.0,   # Over limit
            "total_precip_mm": 5.0,
        }
        result = ws._validate_weather_data(data)
        assert result["avg_temp_c"] <= 60.0
        assert result["min_temp_c"] >= -70.0
        assert result["max_temp_c"] <= 65.0

    def test_clamps_negative_precip(self, basic_config):
        ws = WeatherService(basic_config)
        data = {"total_precip_mm": -5.0, "avg_temp_c": 20.0}
        result = ws._validate_weather_data(data)
        assert result["total_precip_mm"] == 0.0

    def test_swaps_inverted_temperatures(self, basic_config):
        ws = WeatherService(basic_config)
        data = {
            "min_temp_c": 30.0,
            "max_temp_c": 10.0,  # Inverted!
            "avg_temp_c": 20.0,
        }
        result = ws._validate_weather_data(data)
        assert result["min_temp_c"] <= result["max_temp_c"]

    def test_corrects_avg_outside_range(self, basic_config):
        ws = WeatherService(basic_config)
        data = {
            "min_temp_c": 10.0,
            "max_temp_c": 20.0,
            "avg_temp_c": 25.0,  # Above max!
        }
        result = ws._validate_weather_data(data)
        assert result["min_temp_c"] <= result["avg_temp_c"] <= result["max_temp_c"]

    def test_passes_valid_data_unchanged(self, basic_config):
        ws = WeatherService(basic_config)
        data = {
            "total_precip_mm": 5.0,
            "avg_temp_c": 20.0,
            "min_temp_c": 15.0,
            "max_temp_c": 25.0,
            "avg_humidity": 65.0,
            "avg_wind_speed_m_s": 2.5,
            "total_solar_rad_mj_m2": 20.0,
        }
        result = ws._validate_weather_data(data.copy())
        for key in data:
            assert result[key] == data[key]


# ── CSV Fallback Tests ────────────────────────────────────────


class TestCSVFallback:
    def test_csv_loading(self, csv_config):
        ws = WeatherService(csv_config)
        data = ws.get_daily_weather(40.0, -88.0, date(2024, 6, 1))
        assert data is not None
        assert data["source"] == "csv"
        assert "avg_temp_c" in data

    def test_csv_date_range(self, csv_config):
        ws = WeatherService(csv_config)
        date_range = ws.get_date_range()
        assert date_range is not None
        assert date_range[0] == date(2024, 6, 1)

    def test_csv_missing_date_falls_through(self, csv_config):
        ws = WeatherService(csv_config)
        # Date not in CSV should fall through to open_meteo or synthetic
        data = ws.get_daily_weather(40.0, -88.0, date(2020, 1, 1))
        assert data is not None
        assert data["source"] in ("open_meteo", "synthetic")


# ── Hourly Weather Tests ──────────────────────────────────────


class TestHourlyWeather:
    def test_synthetic_hourly_has_24_records(self, basic_config):
        ws = WeatherService(basic_config)
        hourly = ws._generate_synthetic_hourly(40.0, date(2024, 7, 15))
        assert len(hourly) == 24

    def test_hourly_records_have_required_keys(self, basic_config):
        ws = WeatherService(basic_config)
        hourly = ws._generate_synthetic_hourly(40.0, date(2024, 7, 15))
        for record in hourly:
            assert "temp_c" in record
            assert "humidity" in record
            assert "precip_mm" in record


# ── Solar Radiation Tests ─────────────────────────────────────


class TestSolarRadiation:
    def test_positive_radiation(self, basic_config):
        ws = WeatherService(basic_config)
        rad = ws._estimate_solar_radiation(40.0, date(2024, 7, 15), 60.0)
        assert rad > 0

    def test_summer_more_than_winter(self, basic_config):
        ws = WeatherService(basic_config)
        summer = ws._estimate_solar_radiation(40.0, date(2024, 6, 21), 60.0)
        winter = ws._estimate_solar_radiation(40.0, date(2024, 12, 21), 60.0)
        assert summer > winter

    def test_high_humidity_reduces_radiation(self, basic_config):
        ws = WeatherService(basic_config)
        dry = ws._estimate_solar_radiation(40.0, date(2024, 7, 15), 30.0)
        humid = ws._estimate_solar_radiation(40.0, date(2024, 7, 15), 90.0)
        assert dry > humid


# ── Wind Height Correction ────────────────────────────────────


class TestWindHeightCorrection:
    def test_wind_conversion_formula(self, basic_config):
        """36 km/h at 10 m → 7.48 m/s at 2 m (FAO-56 Eq. 47)."""
        wind_max_kmh = 36.0
        u2 = (wind_max_kmh / 3.6) * 0.748
        assert abs(u2 - 7.48) < 0.01

    def test_open_meteo_wind_uses_fao56(self, basic_config):
        """Mock Open-Meteo response: verify output wind speed uses 0.748 factor."""
        import json
        from unittest.mock import patch, MagicMock

        mock_body = json.dumps({
            "daily": {
                "time": ["2023-06-15"],
                "temperature_2m_max": [28.0],
                "temperature_2m_min": [18.0],
                "temperature_2m_mean": [23.0],
                "precipitation_sum": [2.0],
                "windspeed_10m_max": [36.0],       # km/h
                "shortwave_radiation_sum": [22.0],
            },
            "hourly": {
                "time": ["2023-06-15T12:00"],
                "dewpoint_2m": [15.0],
            },
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        ws = WeatherService(basic_config)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            data = ws._fetch_from_open_meteo(40.0, -88.0, date(2023, 6, 15))

        assert data is not None
        expected_u2 = (36.0 / 3.6) * 0.748
        assert abs(data["avg_wind_speed_m_s"] - expected_u2) < 0.01


# ── Dewpoint → Humidity (Magnus / FAO-56) ─────────────────────


class TestDewpointHumidity:
    def test_dewpoint_to_ea(self, basic_config):
        """ea from 15 °C dewpoint = 1.705 kPa (FAO-56 Eq. 14)."""
        ws = WeatherService(basic_config)
        ea = ws._dewpoint_to_ea(15.0)
        assert abs(ea - 1.705) < 0.005

    def test_rh_derived_from_dewpoint(self, basic_config):
        """Td=15°C, Tmax=28°C, Tmin=18°C → RH ≈ 58 % (within 55–65)."""
        import json
        from unittest.mock import patch, MagicMock

        mock_body = json.dumps({
            "daily": {
                "time": ["2023-06-15"],
                "temperature_2m_max": [28.0],
                "temperature_2m_min": [18.0],
                "temperature_2m_mean": [23.0],
                "precipitation_sum": [0.0],
                "windspeed_10m_max": [10.0],
                "shortwave_radiation_sum": [22.0],
            },
            "hourly": {
                "time": [f"2023-06-15T{h:02d}:00" for h in range(24)],
                "dewpoint_2m": [15.0] * 24,
            },
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        ws = WeatherService(basic_config)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            data = ws._fetch_from_open_meteo(40.0, -88.0, date(2023, 6, 15))

        assert data is not None
        assert 55 <= data["avg_humidity"] <= 65, (
            f"Expected RH 55–65 %, got {data['avg_humidity']}"
        )
        assert data["dewpoint_c"] == 15.0
        assert data["ea_kpa"] is not None

    def test_humidity_fallback_when_no_dewpoint(self, basic_config):
        """When dewpoint_2m is absent, humidity falls back to diurnal-range estimate."""
        import json
        from unittest.mock import patch, MagicMock

        mock_body = json.dumps({
            "daily": {
                "time": ["2023-06-15"],
                "temperature_2m_max": [30.0],
                "temperature_2m_min": [15.0],
                "temperature_2m_mean": [22.0],
                "precipitation_sum": [0.0],
                "windspeed_10m_max": [10.0],
                "shortwave_radiation_sum": [22.0],
            },
            "hourly": {"time": [], "dewpoint_2m": []},
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        ws = WeatherService(basic_config)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            data = ws._fetch_from_open_meteo(40.0, -88.0, date(2023, 6, 15))

        assert data is not None
        assert data["dewpoint_c"] is None
        assert 30 <= data["avg_humidity"] <= 95


# ── Disease Step Hourly Wiring ────────────────────────────────


class TestDiseaseStepHourlyWiring:
    def test_lwd_nonzero_with_rainy_hourly(self, basic_config):
        """Synthetic hourly records from a rainy day produce lwd_hours > 0."""
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from app.utils.leaf_wetness_model import calculate_leaf_wetness_duration

        ws = WeatherService(basic_config)
        rainy_day = {
            "total_precip_mm": 12.0,
            "avg_temp_c": 20.0,
            "min_temp_c": 15.0,
            "max_temp_c": 25.0,
            "avg_humidity": 80.0,
            "avg_wind_speed_m_s": 2.0,
            "total_solar_rad_mj_m2": 15.0,
        }
        hourly = ws._daily_to_synthetic_hourly(rainy_day, date(2024, 7, 15))
        assert len(hourly) == 24
        assert all("humidity" in h and "precip_mm" in h for h in hourly)

        # 12 mm daily rain distributed randomly → at least one hour exceeds 0.1 mm
        # Use a liberal threshold: run 5 independent samples, at least one must pass
        any_wet = False
        for _ in range(5):
            hourly_i = ws._daily_to_synthetic_hourly(rainy_day, date(2024, 7, 15))
            if calculate_leaf_wetness_duration(hourly_i) > 0:
                any_wet = True
                break
        assert any_wet, "Expected at least one rainy-day sample to have lwd > 0"


# ── WFPS ─────────────────────────────────────────────────────


class TestWFPS:
    def _make_soil(self, moisture_fraction: float):
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from app.models.soil_model import SoilModel
        return SoilModel(
            "SiltLoam", soil_depth_mm=600.0,
            initial_moisture_fraction_awc=moisture_fraction,
        )

    def test_wfps_at_saturation(self):
        """All layers at saturation → WFPS = 1.0 ≥ 0.95."""
        soil = self._make_soil(0.5)
        for layer in soil.layers:
            layer.current_water_mm = layer.water_at_sat_mm
        assert soil.get_wfps() >= 0.95

    def test_wfps_at_wilting_point(self):
        """All layers at WP → WFPS = WP_vol / SAT_vol < 0.35."""
        soil = self._make_soil(0.5)
        for layer in soil.layers:
            layer.current_water_mm = layer.water_at_wp_mm
        assert soil.get_wfps() < 0.35

    def test_wfps_in_status_dict(self):
        """get_soil_moisture_status() includes consistent wfps key."""
        soil = self._make_soil(0.5)
        status = soil.get_soil_moisture_status()
        assert "wfps" in status
        assert 0.0 <= status["wfps"] <= 1.0

    def test_wfps_increases_with_moisture(self):
        """Wetter soil → higher WFPS than drier soil."""
        dry  = self._make_soil(0.1)
        wet  = self._make_soil(0.9)
        assert wet.get_wfps() > dry.get_wfps()


# ── Precipitation Bias Correction ────────────────────────────


class TestPrecipBiasCorrection:
    def test_july_illinois_scaled(self, basic_config):
        """July, lat 40°N: 5.0 mm × 1.20 = 6.0 mm."""
        ws = WeatherService(basic_config)
        result = ws._bias_correct_precip(5.0, month=7, lat=40.0)
        assert abs(result - 6.0) < 0.01

    def test_drizzle_suppressed(self, basic_config):
        """0.3 mm after scaling is below drizzle threshold → 0.0 mm."""
        ws = WeatherService(basic_config)
        # 0.3 mm × 1.20 = 0.36 mm < 0.5 mm threshold
        result = ws._bias_correct_precip(0.3, month=7, lat=40.0)
        assert result == 0.0

    def test_outside_corn_belt_unchanged(self, basic_config):
        """Latitude outside 36–48°N → no correction applied."""
        ws = WeatherService(basic_config)
        assert ws._bias_correct_precip(5.0, month=7, lat=30.0) == 5.0
        assert ws._bias_correct_precip(5.0, month=7, lat=55.0) == 5.0

    def test_winter_month_no_scaling(self, basic_config):
        """January scale factor = 1.00 → value unchanged above threshold."""
        ws = WeatherService(basic_config)
        result = ws._bias_correct_precip(5.0, month=1, lat=40.0)
        assert abs(result - 5.0) < 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
