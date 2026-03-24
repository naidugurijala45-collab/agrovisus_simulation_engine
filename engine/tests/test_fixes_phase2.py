"""
Tests for Phase-2 fixes:
  Fix 1 — soil PAW and layer geometry at 1200 mm rooting depth
  Fix 2 — harvest index reads self.harvest_index (not hardcoded 0.54)
  Fix 4 — ET0Service._compute_rn() net radiation range
  Fix 5 — estimate_soil_temp_25cm() sinusoidal lag model
  Fix 3 — SoilModel.update_daily() returns positive actual_eta_mm
"""
import sys
import os
import math
import pytest

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app.models.soil_model import SoilModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_IL_SILT_LOAM = {"fc": 0.30, "wp": 0.14, "sat": 0.45}


def _make_soil(depth_mm: float, params: dict = None) -> SoilModel:
    return SoilModel(
        soil_type_name="Test Silt Loam",
        soil_depth_mm=depth_mm,
        initial_moisture_fraction_awc=0.80,
        custom_soil_params=params or _IL_SILT_LOAM,
    )


# ---------------------------------------------------------------------------
# Fix 1 — Soil PAW and layer geometry
# ---------------------------------------------------------------------------

def test_soil_paw_range_1200mm():
    """PAW for 1200 mm IL silt loam profile must be 150-210 mm."""
    soil = _make_soil(1200.0)
    total_paw = sum(layer.awc_mm for layer in soil.layers)
    assert 150 < total_paw < 210, (
        f"PAW={total_paw:.1f} mm outside 150-210 mm; "
        "check layer geometry or FC/WP params"
    )


def test_soil_layer_geometry_1200mm():
    """Depth=1200 mm: L1=300, L2=600, L3=300, sum=1200."""
    soil = _make_soil(1200.0)
    depths = [layer.depth_mm for layer in soil.layers]
    assert len(depths) == 3, f"Expected 3 layers, got {len(depths)}"
    assert depths[0] == pytest.approx(300.0, abs=1.0), f"L1={depths[0]}"
    assert depths[1] == pytest.approx(600.0, abs=1.0), f"L2={depths[1]}"
    assert depths[2] == pytest.approx(300.0, abs=1.0), f"L3={depths[2]}"
    assert sum(depths) == pytest.approx(1200.0, abs=1.0)


# ---------------------------------------------------------------------------
# Fix 2 — Harvest Index from template
# ---------------------------------------------------------------------------

def test_harvest_index_uses_template():
    """CropModel must store and use the template HI (corn=0.50), not 0.54."""
    from app.models.crop_model import CropModel

    # Minimal corn-like instantiation with HI=0.50
    crop = CropModel(
        initial_stage="germination",
        gdd_thresholds={
            "germination": 0,
            "vegetative": 150,
            "reproductive": 600,
            "grain_fill": 900,
            "maturity": 1200,
        },
        t_base_c=10.0,
        n_demand_per_stage={
            "germination": 1.0,
            "vegetative": 2.5,
            "reproductive": 2.0,
            "grain_fill": 1.5,
            "maturity": 0.5,
        },
        water_stress_threshold_awc=0.5,
        anaerobic_stress_threshold_awc=0.9,
        radiation_use_efficiency_g_mj=1.8,
        light_interception_per_stage={
            "germination": 0.1,
            "vegetative": 0.6,
            "reproductive": 0.9,
            "grain_fill": 0.85,
            "maturity": 0.5,
        },
        harvest_index=0.50,
    )

    # Attribute must be stored correctly
    assert crop.harvest_index == pytest.approx(0.50, abs=0.001), (
        f"harvest_index stored as {crop.harvest_index}, expected 0.50"
    )

    # get_final_yield() must use it (no stress → yield = biomass * 0.50)
    crop.total_biomass_kg_ha = 10000.0
    yield_kg_ha = crop.get_final_yield()

    # With no stress days, yield <= biomass * 0.50
    assert yield_kg_ha <= 10000.0 * 0.50 * 1.01, (
        f"Yield {yield_kg_ha:.1f} > biomass*0.50 ({10000*0.50:.1f})"
    )
    # Must NOT equal the old hardcoded 0.54 result
    old_hardcoded = 10000.0 * 0.54
    assert abs(yield_kg_ha - old_hardcoded) > 100, (
        f"Yield {yield_kg_ha:.1f} suspiciously close to old hardcoded 0.54 result "
        f"({old_hardcoded:.1f})"
    )


# ---------------------------------------------------------------------------
# Fix 4 — ET0Service._compute_rn() net radiation range
# ---------------------------------------------------------------------------

def test_rn_computation_june_illinois():
    """Rn for a clear June day in Illinois should be in 12-18 MJ/m2/day.

    Reference: FAO-56 Example 16 (lat=45 N, mid-July ~13 MJ/m2/day).
    At 40 N with Rs=22 MJ/m2/day on summer solstice, 12-18 is physically sound.
    """
    from app.services.et0_service import ET0Service
    svc = ET0Service()

    rn = svc._compute_rn(
        rs_mj_m2=22.0,
        t_max_c=28.0,
        t_min_c=18.0,
        ea_kpa=1.80,
        lat_rad=math.radians(40.0),
        doy=172,
        elevation_m=200.0,
    )
    assert 12.0 <= rn <= 18.0, (
        f"Rn={rn:.3f} MJ/m2/day outside expected 12-18 MJ/m2/day range"
    )


# ---------------------------------------------------------------------------
# Fix 5 — estimate_soil_temp_25cm() sinusoidal model
# ---------------------------------------------------------------------------

def test_soil_temp_spring_lag():
    """On DOY 121 (May 1), soil at 25 cm lags warming air.

    tair=15 C on May 1 with t_mean_annual=12 C:
    soil T should be 8-14 C (below air T due to thermal lag).
    """
    from app.services.simulation_pipeline import estimate_soil_temp_25cm
    t_soil = estimate_soil_temp_25cm(doy=121, tair_mean=15.0)
    assert 8.0 <= t_soil <= 14.0, (
        f"Soil temp on May 1 = {t_soil:.1f} C; expected spring lag (8-14 C)"
    )


def test_soil_temp_summer_peak():
    """On DOY 200 (July 19), soil at 25 cm is near seasonal peak (20-27 C)."""
    from app.services.simulation_pipeline import estimate_soil_temp_25cm
    t_soil = estimate_soil_temp_25cm(doy=200, tair_mean=25.0)
    assert 20.0 <= t_soil <= 27.0, (
        f"Soil temp on DOY 200 = {t_soil:.1f} C; expected summer peak (20-27 C)"
    )


# ---------------------------------------------------------------------------
# Fix 3 — actual_eta_mm reported non-zero
# ---------------------------------------------------------------------------

def test_etc_reported_nonzero():
    """SoilModel.update_daily() must return positive actual_eta_mm when ET0>0."""
    soil = _make_soil(1200.0)
    result = soil.update_daily(
        precipitation_mm=0.0,
        irrigation_mm=0.0,
        et0_mm=5.0,
        crop_coefficient_kc=1.0,
        root_depth_mm=600.0,
    )
    eta = result["actual_eta_mm"]
    assert eta > 0.0, (
        f"actual_eta_mm={eta:.4f}; expected > 0 with ET0=5 mm/day and 80% AWC soil"
    )
    assert eta <= 5.0, (
        f"actual_eta_mm={eta:.4f} exceeds potential ET0=5 mm/day (physically impossible)"
    )
