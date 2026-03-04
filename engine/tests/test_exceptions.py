"""
Tests for the AgroVisus custom exception hierarchy.
"""
import os
import sys

import pytest

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from app.utils.exceptions import (
    AgroVisusError,
    ConfigValidationError,
    WeatherDataError,
    NoWeatherDataError,
    WeatherQualityError,
    SimulationError,
    ModelInitError,
    NumericalError,
    DataError,
)


# ── Hierarchy Tests ───────────────────────────────────────────


class TestExceptionHierarchy:
    def test_all_inherit_from_agrovisus_error(self):
        """Every custom exception should be catchable as AgroVisusError."""
        exceptions = [
            ConfigValidationError("test"),
            WeatherDataError("test"),
            NoWeatherDataError(),
            WeatherQualityError("test"),
            SimulationError("test"),
            ModelInitError("crop_model", "bad config"),
            NumericalError(),
            DataError("test"),
        ]
        for exc in exceptions:
            assert isinstance(exc, AgroVisusError), f"{type(exc).__name__} not AgroVisusError"

    def test_weather_hierarchy(self):
        assert isinstance(NoWeatherDataError(), WeatherDataError)
        assert isinstance(WeatherQualityError("test"), WeatherDataError)

    def test_simulation_hierarchy(self):
        assert isinstance(ModelInitError("m", "r"), SimulationError)
        assert isinstance(NumericalError(), SimulationError)


# ── Suggestion Tests ──────────────────────────────────────────


class TestSuggestions:
    def test_base_error_with_suggestion(self):
        e = AgroVisusError("Something failed", suggestion="Try X instead")
        assert e.suggestion == "Try X instead"

    def test_config_error_auto_suggestion(self):
        e = ConfigValidationError("Bad value", key="soil.depth_mm")
        assert "soil.depth_mm" in e.suggestion

    def test_no_weather_auto_suggestion(self):
        e = NoWeatherDataError()
        assert "OpenWeatherMap" in e.suggestion or "CSV" in e.suggestion

    def test_model_init_auto_suggestion(self):
        e = ModelInitError("CropModel", "missing gdd_thresholds")
        assert "CropModel" in str(e)
        assert "CropModel" in e.suggestion

    def test_numerical_error_auto_suggestion(self):
        e = NumericalError()
        assert "extreme input" in e.suggestion.lower() or "numerical" in str(e).lower()


# ── User Message Tests ────────────────────────────────────────


class TestUserMessage:
    def test_user_message_includes_error(self):
        e = AgroVisusError("Disk full")
        msg = e.user_message()
        assert "Disk full" in msg
        assert "ERROR" in msg

    def test_user_message_includes_suggestion(self):
        e = AgroVisusError("Disk full", suggestion="Free space on drive C:")
        msg = e.user_message()
        assert "Fix:" in msg
        assert "Free space" in msg

    def test_user_message_no_suggestion(self):
        e = AgroVisusError("Unknown error")
        msg = e.user_message()
        assert "Fix:" not in msg


# ── Catch-all Pattern Test ────────────────────────────────────


class TestCatchAll:
    def test_catch_all_pattern(self):
        """Simulates what run.py does: catch AgroVisusError."""
        errors_caught = 0
        test_errors = [
            ConfigValidationError("bad config", key="x"),
            NoWeatherDataError(),
            ModelInitError("soil", "nan values"),
            DataError("missing file"),
        ]

        for err in test_errors:
            try:
                raise err
            except AgroVisusError:
                errors_caught += 1

        assert errors_caught == len(test_errors)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
