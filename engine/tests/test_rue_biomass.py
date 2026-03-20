"""Regression tests for RUE-driven daily biomass accumulation (Beer-Lambert).

Covers:
  - test_rue_corn_no_stress          : delta_biomass in expected range under no stress
  - test_rue_corn_water_stress_moderate : moderate water stress reduces RUE by 0.85x
  - test_rue_rice_stage_switch       : vegetative→grain-fill RUE switch at PanicleInitiation
  - test_rue_soybean_n_stress_severe : severe N stress (NNI=0.5) reduces RUE by 0.65x
"""

import pytest
from app.models.crop_model import CropModel

# ── Shared RUE stress block ─────────────────────────────────────────────────
_STRESS = {
    "water_moderate": 0.85,
    "water_severe":   0.60,
    "n_moderate":     0.80,
    "n_severe":       0.65,
}


# ── Model factories ──────────────────────────────────────────────────────────

def _corn_model() -> CropModel:
    return CropModel(
        initial_stage="VE",
        gdd_thresholds={
            "VE": 0, "V2": 120, "V6": 400, "V10": 650,
            "VT": 850, "R1": 1000, "R3": 1300, "R6": 1700,
        },
        t_base_c=10.0,
        t_upper_c=30.0,
        n_demand_per_stage={
            "VE": 0.3, "V2": 0.6, "V6": 1.1, "V10": 3.0,
            "VT": 5.0, "R1": 2.7, "R3": 1.5, "R6": 0.0,
        },
        water_stress_threshold_awc=0.5,
        anaerobic_stress_threshold_awc=0.9,
        radiation_use_efficiency_g_mj=3.5,  # legacy; overridden by rue_config
        light_interception_per_stage={
            "VE": 0.10, "V2": 0.30, "V6": 0.70, "V10": 0.95,
            "VT": 1.00, "R1": 1.00, "R3": 0.90, "R6": 0.70,
        },
        harvest_index=0.50,
        vegetative_stages=["VE", "V2", "V6", "V10"],
        reproductive_stages=["VT", "R1", "R3", "R6"],
        rue_config={
            "vegetative": 3.8, "grain_fill": 3.8,
            "grain_fill_stage": "R1", "basis": "APAR",
            "k_extinction": 0.45, "stress": _STRESS,
        },
    )


def _rice_model() -> CropModel:
    """Minimal rice-like model with PanicleInitiation stage for the switch test."""
    return CropModel(
        initial_stage="Tillering",
        gdd_thresholds={
            "Tillering": 0, "PanicleInitiation": 700, "GrainFilling": 1500,
        },
        t_base_c=10.0,
        t_upper_c=35.0,
        n_demand_per_stage={
            "Tillering": 1.0, "PanicleInitiation": 2.0, "GrainFilling": 1.5,
        },
        water_stress_threshold_awc=0.5,
        anaerobic_stress_threshold_awc=0.9,
        radiation_use_efficiency_g_mj=2.5,
        light_interception_per_stage={
            "Tillering": 0.60, "PanicleInitiation": 0.90, "GrainFilling": 0.85,
        },
        harvest_index=0.45,
        vegetative_stages=["Tillering"],
        reproductive_stages=["PanicleInitiation", "GrainFilling"],
        rue_config={
            "vegetative": 1.2, "grain_fill": 4.5,
            "grain_fill_stage": "PanicleInitiation", "basis": "APAR",
            "k_extinction": 0.45, "stress": _STRESS,
        },
    )


def _soybean_model() -> CropModel:
    return CropModel(
        initial_stage="VE",
        gdd_thresholds={
            "VE": 0, "V2": 100, "V6": 350,
            "R1": 600, "R3": 850, "R5": 1050, "R7": 1300, "R8": 1500,
        },
        t_base_c=10.0,
        t_upper_c=30.0,
        n_demand_per_stage={
            "VE": 0.2, "V2": 0.5, "V6": 1.0, "R1": 2.0,
            "R3": 2.5, "R5": 2.0, "R7": 1.0, "R8": 0.3,
        },
        water_stress_threshold_awc=0.5,
        anaerobic_stress_threshold_awc=0.9,
        radiation_use_efficiency_g_mj=1.8,
        light_interception_per_stage={
            "VE": 0.08, "V2": 0.25, "V6": 0.65, "R1": 0.90,
            "R3": 0.95, "R5": 0.90, "R7": 0.70, "R8": 0.50,
        },
        harvest_index=0.35,
        vegetative_stages=["VE", "V2", "V6"],
        reproductive_stages=["R1", "R3", "R5", "R7", "R8"],
        rue_config={
            "vegetative": 2.5, "grain_fill": 2.5,
            "grain_fill_stage": "R5", "basis": "APAR",
            "k_extinction": 0.45, "stress": _STRESS,
        },
    )


# ── Tests ────────────────────────────────────────────────────────────────────

def test_rue_corn_no_stress():
    """Corn at V6 (pre-grain-fill), solar=20 MJ/m², LAI=2.5, no stress.

    Expected APAR = 20 * 0.45 * (1 - exp(-0.45*2.5)) ≈ 6.08 MJ/m²/day
    Expected delta_biomass = 3.8 * 6.08 ≈ 23.1 g/m²/day → within [18, 30]
    """
    model = _corn_model()
    model.current_stage = "V6"

    apar = model._compute_apar(solar_radiation_mj=20.0, lai=2.5)
    rue_eff, rue_base = model._compute_rue_effective(
        stage="V6", soil_water_factor=1.0, nni=1.0
    )
    delta_biomass = rue_eff * apar

    assert rue_base == pytest.approx(3.8)
    assert rue_eff == pytest.approx(3.8)       # no stress → no reduction
    assert 18 < delta_biomass < 30, f"delta_biomass={delta_biomass:.2f} outside [18, 30]"


def test_rue_corn_water_stress_moderate():
    """Corn V6, soil_water_factor=0.55 (moderate) → RUE_effective = 3.8 * 0.85."""
    model = _corn_model()
    model.current_stage = "V6"

    apar = model._compute_apar(solar_radiation_mj=20.0, lai=2.5)

    rue_eff_none, _ = model._compute_rue_effective("V6", soil_water_factor=1.0, nni=1.0)
    rue_eff_mod, _  = model._compute_rue_effective("V6", soil_water_factor=0.55, nni=1.0)

    assert rue_eff_mod == pytest.approx(3.8 * 0.85, rel=1e-6)

    delta_none = rue_eff_none * apar
    delta_mod  = rue_eff_mod  * apar
    assert delta_mod == pytest.approx(delta_none * 0.85, rel=1e-6)


def test_rue_rice_stage_switch():
    """Tillering → vegetative RUE=1.2; PanicleInitiation → grain-fill RUE=4.5."""
    model = _rice_model()

    _, rue_veg = model._compute_rue_effective(
        "Tillering", soil_water_factor=1.0, nni=1.0
    )
    _, rue_gf = model._compute_rue_effective(
        "PanicleInitiation", soil_water_factor=1.0, nni=1.0
    )

    assert rue_veg == pytest.approx(1.2)
    assert rue_gf  == pytest.approx(4.5)


def test_rue_soybean_n_stress_severe():
    """Soybean with NNI=0.5 (< 0.7) → n_factor=0.65 → RUE_effective = 2.5 * 0.65."""
    model = _soybean_model()
    model.current_stage = "V6"

    rue_eff, _ = model._compute_rue_effective(
        "V6", soil_water_factor=1.0, nni=0.5
    )
    assert rue_eff == pytest.approx(2.5 * 0.65, rel=1e-6)
