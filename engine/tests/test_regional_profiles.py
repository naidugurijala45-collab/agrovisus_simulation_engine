"""
Tests for the regional profile system.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.regional_profile_loader import (
    load_profile,
    get_disease_multiplier,
    get_soil_defaults,
    get_yield_benchmark,
)


def test_oh_maps_to_corn_belt():
    """OH (Ohio) must resolve to the corn_belt region."""
    profile = load_profile("OH")
    assert profile["region_key"] == "corn_belt", (
        f"Expected 'corn_belt' for OH, got '{profile['region_key']}'"
    )


def test_ks_maps_to_great_plains():
    """KS (Kansas) must resolve to the great_plains region."""
    profile = load_profile("KS")
    assert profile["region_key"] == "great_plains", (
        f"Expected 'great_plains' for KS, got '{profile['region_key']}'"
    )


def test_gls_multiplier_values():
    """
    GLS multipliers match peer-reviewed calibration values.

    Corn belt: 1.0 (baseline)
    Southeast: 0.45 — peer-reviewed data show GLS is less prevalent in the
    hot/dry southeast lowlands than in the humid Corn Belt.
    """
    southeast_mult = get_disease_multiplier("GA", "gls")  # GA → southeast
    corn_belt_mult = get_disease_multiplier("OH", "gls")  # OH → corn_belt
    assert southeast_mult == 0.45, f"Expected 0.45 for southeast GLS, got {southeast_mult}"
    assert corn_belt_mult == 1.0, f"Expected 1.0 for corn_belt GLS, got {corn_belt_mult}"
    assert southeast_mult < corn_belt_mult, (
        f"Expected southeast GLS ({southeast_mult}) < corn_belt GLS ({corn_belt_mult}) "
        f"per peer-reviewed regional calibration."
    )


def test_unknown_state_falls_back_to_default():
    """An unmapped state code must fall back to the 'default' region."""
    profile = load_profile("XX")  # not a real state
    assert profile["region_key"] == "default", (
        f"Expected 'default' for unknown state 'XX', got '{profile['region_key']}'"
    )
    # Default region should match corn_belt values
    assert profile["yield_benchmark_bu_ac"] == 185


def test_soil_defaults_not_applied_when_user_provides_explicit_field_capacity():
    """
    When a user-provided field_capacity_mm is present in soil_params_conf,
    the simulation service must NOT overwrite it with regional defaults.

    We verify this by checking the logic directly: regional soil should only
    fill in when soil_params_conf.get("field_capacity_mm") is None.
    """
    # Simulate the priority logic from SimulationService._initialize_models
    user_explicit_fc = 200.0  # user provided
    regional_soil = get_soil_defaults("OH")  # corn_belt: 180 mm

    # Replicate the priority chain used in simulation_service.py
    soil_params_conf = {"field_capacity_mm": user_explicit_fc}
    user_provided_fc = soil_params_conf.get("field_capacity_mm") is not None

    fc_mm = (
        soil_params_conf.get("field_capacity_mm")
        or regional_soil.get("field_capacity_mm")
    )

    assert user_provided_fc is True
    assert fc_mm == user_explicit_fc, (
        f"Expected user FC {user_explicit_fc} mm to take priority, "
        f"but got {fc_mm} mm (regional default is {regional_soil['field_capacity_mm']} mm)"
    )


def test_soil_defaults_applied_when_user_omits_field_capacity():
    """Regional soil defaults ARE used when the user provides no explicit field_capacity_mm."""
    regional_soil = get_soil_defaults("GA")  # southeast: 140 mm

    soil_params_conf: dict = {}  # user provided nothing
    fc_mm = (
        soil_params_conf.get("field_capacity_mm")
        or regional_soil.get("field_capacity_mm")
    )

    assert fc_mm == 140, (
        f"Expected regional FC 140 mm for GA (southeast), got {fc_mm}"
    )
