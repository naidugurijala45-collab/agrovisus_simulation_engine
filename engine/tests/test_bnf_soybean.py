"""Regression tests for the BNF (biological nitrogen fixation) submodule.

BNF is soybean-only; all other crops return 0.0 from compute_daily_bnf().

Covers:
  - test_bnf_peak_conditions            : BNF in [0.8, 3.5] kg N/ha/day at optimal conditions
  - test_bnf_cold_shutdown              : t_soil=4 (< t_min=5) → 0.0
  - test_bnf_flooded_shutdown           : wfps=0.95 (≥ threshold=0.90) → 0.0
  - test_bnf_high_mineral_n_suppression : no3=160 → f_mineral=0.20; ratio ≤ 0.25
  - test_bnf_stage_boundaries           : nds=0.05→0, nds=0.55→1.0, nds=0.92→0
  - test_bnf_seasonal_total             : 120-day integration → 80–160 kg N/ha
"""

import pytest
from app.models.nutrient_model import NutrientModel

# ── Shared BNF config (mirrors soybean crop_templates.json entry) ─────────────
_BNF_CONFIG = {
    "enabled": True,
    "nmax_fixpot": 0.03,
    "temperature_response": {
        "t_min": 5, "t_opt_low": 20, "t_opt_high": 35, "t_max": 44,
    },
    "water_response": {
        "wf_lower": 0.2, "wf_upper": 0.8, "flooded_threshold_wfps": 0.90,
    },
    "stage_response": {
        "nds_min": 0.1, "nds_opt_low": 0.3, "nds_opt_high": 0.7, "nds_max": 0.9,
    },
    "mineral_n_inhibition": {
        "no3_kg_ha_thresholds": {"low": 50, "moderate": 100, "high": 150},
        "inhibition_fractions": {"low": 0.9, "moderate": 0.55, "high": 0.2},
    },
}


def _soybean_nutrient_model() -> NutrientModel:
    return NutrientModel(
        initial_nitrate_N_kg_ha=40.0,
        initial_ammonium_N_kg_ha=10.0,
        max_daily_urea_hydrolysis_rate=0.30,
        max_daily_nitrification_rate=0.15,
        temp_base=5.0,
        temp_opt=25.0,
        temp_max=40.0,
        bnf_config=_BNF_CONFIG,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_bnf_peak_conditions():
    """Optimal conditions: root_dm=100 g/m², t=27°C, wf=0.85, nds=0.55, no3=20.

    Expected:
      nfix_pot = 0.03 × 100 = 3.0
      f_T = 1.0  (20 ≤ 27 ≤ 35)
      f_W = 1.0  (0.85 ≥ wf_upper=0.8)
      f_S = 1.0  (0.3 ≤ 0.55 ≤ 0.7)
      f_N = 0.9  (20 ≤ no3_low=50)
      BNF = 3.0 × 0.9 = 2.7 kg N/ha/day  →  within [0.8, 3.5]
    """
    model = _soybean_nutrient_model()
    bnf = model.compute_daily_bnf(
        root_dm_g_m2=100.0, t_soil=27.0, wf=0.85, nds=0.55, no3_kg_ha=20.0
    )
    assert 0.8 < bnf < 3.5, f"BNF={bnf:.4f} outside (0.8, 3.5)"
    assert model._last_bnf_kg_ha == pytest.approx(bnf)


def test_bnf_cold_shutdown():
    """t_soil=4 < t_min=5 → f_T=0 → BNF=0.0."""
    model = _soybean_nutrient_model()
    bnf = model.compute_daily_bnf(
        root_dm_g_m2=80.0, t_soil=4.0, wf=0.7, nds=0.5, no3_kg_ha=20.0
    )
    assert bnf == pytest.approx(0.0)


def test_bnf_flooded_shutdown():
    """wfps=0.95 ≥ flooded_threshold=0.90 → f_W=0 → BNF=0.0."""
    model = _soybean_nutrient_model()
    bnf = model.compute_daily_bnf(
        root_dm_g_m2=80.0, t_soil=27.0, wf=0.95, nds=0.5,
        no3_kg_ha=20.0, wfps=0.95,
    )
    assert bnf == pytest.approx(0.0)


def test_bnf_high_mineral_n_suppression():
    """High soil NO₃ (160 kg/ha) suppresses BNF to ≤ 25% of low-N rate.

    Expected:
      f_mineral(20 kg NO3)  = 0.90  (≤ low threshold 50)
      f_mineral(160 kg NO3) = 0.20  (> moderate threshold 100)
      ratio = 0.20 / 0.90 = 0.222  ≤ 0.25  ✓
    """
    model = _soybean_nutrient_model()
    # Verify f_mineral directly
    assert model._bnf_f_mineral_n(160.0) == pytest.approx(0.20)

    # Full BNF comparison at identical conditions except NO₃
    bnf_low_n = model.compute_daily_bnf(
        root_dm_g_m2=50.0, t_soil=27.0, wf=1.0, nds=0.5, no3_kg_ha=20.0
    )
    bnf_high_n = model.compute_daily_bnf(
        root_dm_g_m2=50.0, t_soil=27.0, wf=1.0, nds=0.5, no3_kg_ha=160.0
    )
    assert bnf_low_n > 0
    assert bnf_high_n / bnf_low_n <= 0.25, (
        f"ratio={bnf_high_n/bnf_low_n:.3f} exceeds 0.25"
    )


def test_bnf_stage_boundaries():
    """Stage response function hits correct values at NDS boundary points."""
    model = _soybean_nutrient_model()

    # nds=0.05 < nds_min=0.10 → f_stage=0.0
    assert model._bnf_f_stage(0.05) == pytest.approx(0.0)

    # nds=0.55 in optimal plateau [0.3, 0.7] → f_stage=1.0
    assert model._bnf_f_stage(0.55) == pytest.approx(1.0)

    # nds=0.92 > nds_max=0.90 → f_stage=0.0
    assert model._bnf_f_stage(0.92) == pytest.approx(0.0)


def test_bnf_seasonal_total():
    """120-day integration with root_dm ramp 5→50→15 g/m², NDS 0.40→0.87.

    Constant inputs: t_soil=27°C, wf=1.0 (optimal), no3=20 kg/ha.
    Stress factors: f_T=1.0, f_W=1.0, f_N=0.9.
    Expected seasonal total ≈ 85 kg N/ha → within [80, 160].
    """
    model = _soybean_nutrient_model()
    total_bnf = 0.0
    for i in range(120):
        nds = 0.40 + (0.87 - 0.40) * i / 119           # NDS: 0.40 → 0.87
        if i < 60:
            root_dm = 5.0 + 45.0 * i / 59              # 5 → 50 g/m²
        else:
            root_dm = 50.0 - 35.0 * (i - 60) / 59     # 50 → 15 g/m²
        total_bnf += model.compute_daily_bnf(
            root_dm_g_m2=root_dm, t_soil=27.0, wf=1.0,
            nds=nds, no3_kg_ha=20.0,
        )
    assert 80 < total_bnf < 160, (
        f"Seasonal BNF={total_bnf:.1f} kg N/ha outside expected range (80, 160)"
    )
