"""
ET0 (Reference Evapotranspiration) Calculation Service

Provides a unified interface for calculating ET0 using different methods.
Supports both Penman-Monteith and Hargreaves methods with configurable selection.
"""

import logging
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

        # pyet requires a plain integer day-of-year, not a date/Timestamp
        if isinstance(day_of_year, int):
            doy = day_of_year
        else:
            doy = day_of_year.timetuple().tm_yday

        try:
            if use_method == "hargreaves":
                return self._calculate_hargreaves(weather_data, location, doy)
            else:
                return self._calculate_penman_monteith(weather_data, location, doy)
        except Exception as e:
            logger.error(f"ET0 calculation failed: {e}", exc_info=True)
            return self.fallback_value
    
    def _calculate_hargreaves(
        self,
        weather_data: Dict[str, float],
        location: Dict[str, float],
        day_of_year: int
    ) -> float:
        """
        Calculate ET0 using Hargreaves equation.
        
        Requires: t_min, t_max, t_avg, lat
        """
        try:
            t_min = weather_data["t_min"]
            t_max = weather_data["t_max"]
            t_avg = weather_data["t_avg"]
            lat = location["lat"]
            
            # pyet requires pandas Series
            tmean = pd.Series([t_avg])
            tmax = pd.Series([t_max])
            tmin = pd.Series([t_min])
            
            et0_series = et.hargreaves(tmean, tmax, tmin, lat=lat)
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
        day_of_year: int
    ) -> float:
        """
        Calculate ET0 using FAO-56 Penman-Monteith equation.
        
        Requires: t_min, t_max, t_avg, rh_avg, rs_mj_m2, u2_m_s, lat, elevation_m
        Falls back to Hargreaves if data is incomplete.
        """
        try:
            # Check for required variables
            required = ["t_min", "t_max", "t_avg", "rh_avg", "rs_mj_m2", "u2_m_s"]
            missing = [var for var in required if var not in weather_data or pd.isna(weather_data[var])]
            
            if missing:
                logger.warning(
                    f"Missing variables for Penman-Monteith: {missing}. "
                    "Falling back to Hargreaves."
                )
                return self._calculate_hargreaves(weather_data, location, day_of_year)
            
            # Extract values
            t_min = weather_data["t_min"]
            t_max = weather_data["t_max"]
            t_avg = weather_data["t_avg"]
            rh_avg = weather_data["rh_avg"]
            rs_mj_m2 = weather_data["rs_mj_m2"]
            u2_m_s = weather_data["u2_m_s"]
            elevation_m = location["elevation_m"]
            lat = location["lat"]
            
            # Convert to pandas Series for pyet
            tmean = pd.Series([t_avg])
            tmax = pd.Series([t_max])
            tmin = pd.Series([t_min])
            rh = pd.Series([rh_avg])
            rs = pd.Series([rs_mj_m2])
            wind = pd.Series([u2_m_s])
            
            # Calculate using pyet
            et0_series = et.pm(
                tmean,
                wind,
                rs=rs,
                elevation=elevation_m,
                lat=lat,
                tmax=tmax,
                tmin=tmin,
                rh=rh,
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
