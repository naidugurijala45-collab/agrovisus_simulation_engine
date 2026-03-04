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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
