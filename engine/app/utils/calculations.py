# AGROVISUS_SIMULATION_ENGINE/app/utils/calculations.py

import logging
from datetime import date

import pandas as pd
import pyet as et

logger = logging.getLogger(__name__)


def et0_hargreaves(
    t_avg: float, t_min: float, t_max: float, lat: float, day_of_year: date
) -> float:
    """
    Calculates daily reference ET (ET0) using the Hargreaves equation.
    This is kept as a fallback method.
    """
    try:
        # pyet requires pandas Series, so we create them for a single day calculation
        tmean = pd.Series([t_avg])
        tmax = pd.Series([t_max])
        tmin = pd.Series([t_min])

        et0_series = et.hargreaves(tmean, tmax, tmin, lat=lat)
        et0_value = et0_series.iloc[0]

        return float(et0_value) if et0_value > 0 else 0.0
    except Exception as e:
        logger.error(f"Error during Hargreaves calculation: {e}", exc_info=True)
        return 1.5  # Return a plausible default on error


def et0_penman_monteith(
    t_min: float,
    t_max: float,
    t_avg: float,
    rh_avg: float,
    rs_mj_m2: float,
    u2_m_s: float,
    lat: float,
    elevation_m: float,
    day_of_year: date,
) -> float:
    """
    Calculates daily reference ET (ET0) using the FAO-56 Penman-Monteith equation.
    """
    try:
        # Check for missing or invalid inputs, which can come from dummy data
        if any(
            v is None or pd.isna(v)
            for v in [t_min, t_max, t_avg, rh_avg, rs_mj_m2, u2_m_s]
        ):
            logger.warning(
                "Missing one or more weather variables for Penman-Monteith. Falling back to Hargreaves."
            )
            return et0_hargreaves(t_avg, t_min, t_max, lat, day_of_year)

        tmean = pd.Series([t_avg])
        tmax = pd.Series([t_max])
        tmin = pd.Series([t_min])
        rh = pd.Series([rh_avg])
        rs = pd.Series([rs_mj_m2])
        wind = pd.Series([u2_m_s])

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

        if pd.isna(et0_value) or et0_value < 0:
            logger.warning(
                f"Penman-Monteith calculation resulted in invalid value ({et0_value}). Falling back to Hargreaves."
            )
            return et0_hargreaves(t_avg, t_min, t_max, lat, day_of_year)

        return float(et0_value)
    except Exception as e:
        logger.error(f"Error during Penman-Monteith calculation: {e}", exc_info=True)
        return 2.0  # Return a plausible default on error
