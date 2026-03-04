"""
AgroVisus Custom Exception Hierarchy.

Provides structured, user-friendly exceptions with actionable suggestions.
All exceptions inherit from AgroVisusError for unified catch-all handling.

Hierarchy:
    AgroVisusError (base)
    ├── ConfigValidationError    - Bad config values
    ├── WeatherDataError         - Weather fetch failures
    │   ├── NoWeatherDataError   - All sources failed
    │   └── WeatherQualityError  - Data quality issues
    ├── SimulationError          - Simulation runtime errors
    │   ├── ModelInitError       - Model initialization failures
    │   └── NumericalError       - NaN, overflow, etc.
    └── DataError                - Input data problems
"""


class AgroVisusError(Exception):
    """Base exception for all AgroVisus errors.

    Attributes:
        suggestion: Actionable fix the user can apply.
    """

    def __init__(self, message: str, suggestion: str = ""):
        super().__init__(message)
        self.suggestion = suggestion

    def user_message(self) -> str:
        """Return a formatted message suitable for end-user display."""
        parts = [f"ERROR: {self}"]
        if self.suggestion:
            parts.append(f"  Fix: {self.suggestion}")
        return "\n".join(parts)


# ── Configuration ──────────────────────────────────────────────


class ConfigValidationError(AgroVisusError):
    """Raised when configuration values are invalid or missing."""

    def __init__(self, message: str, key: str = "", suggestion: str = ""):
        if not suggestion and key:
            suggestion = f"Check the '{key}' value in your config.json file."
        super().__init__(message, suggestion)
        self.key = key


# ── Weather ────────────────────────────────────────────────────


class WeatherDataError(AgroVisusError):
    """Raised when weather data cannot be fetched or is unusable."""

    pass


class NoWeatherDataError(WeatherDataError):
    """Raised when no weather data could be obtained from any source."""

    def __init__(self, message: str = "No weather data available from any source.", suggestion: str = ""):
        if not suggestion:
            suggestion = (
                "Ensure you have either: (1) a valid OpenWeatherMap API key in "
                "config.json, (2) a CSV file at the path specified in "
                "historical_data_paths.hourly_weather_csv, or (3) internet "
                "access for the Open-Meteo fallback API."
            )
        super().__init__(message, suggestion)


class WeatherQualityError(WeatherDataError):
    """Raised when weather data fails quality checks (outliers, gaps)."""

    pass


# ── Simulation ─────────────────────────────────────────────────


class SimulationError(AgroVisusError):
    """Raised during simulation execution."""

    pass


class ModelInitError(SimulationError):
    """Raised when a simulation model fails to initialize."""

    def __init__(self, model_name: str, reason: str, suggestion: str = ""):
        if not suggestion:
            suggestion = f"Check the '{model_name}' configuration section in config.json."
        super().__init__(
            f"Failed to initialize {model_name}: {reason}",
            suggestion,
        )
        self.model_name = model_name


class NumericalError(SimulationError):
    """Raised on NaN, Inf, or other numerical instabilities."""

    def __init__(self, message: str = "Numerical instability detected.", suggestion: str = ""):
        if not suggestion:
            suggestion = (
                "This usually indicates extreme input values. Check weather "
                "data and soil parameters for unrealistic values."
            )
        super().__init__(message, suggestion)


# ── Data ───────────────────────────────────────────────────────


class DataError(AgroVisusError):
    """Raised when input data files are missing or malformed."""

    pass
