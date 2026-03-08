"""Tests for the flat ROI calculator output structure."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.services.roi_calculator import calculate_roi, enrich_rule_with_roi, SEVERITY_YIELD_LOSS

FLAT_KEYS = {
    "estimated_yield_loss_bu_acre",
    "revenue_at_risk_per_acre",
    "revenue_at_risk_total",
    "treatment_cost_total",
    "roi_low",
    "roi_mid",
    "roi_high",
    "breakeven_yield_loss_percent",
    "recommendation_strength",
    "commodity_price_used",
}


def test_flat_structure():
    result = calculate_roi(
        crop_type="corn",
        yield_loss_percent=8.0,
        treatment_cost_per_acre=25.0,
        field_acres=100.0,
    )
    assert set(result.keys()) == FLAT_KEYS
    assert "treatment_roi" not in result


def test_roi_values_are_floats():
    result = calculate_roi("corn", 8.0, 25.0, 100.0)
    for key in ("roi_low", "roi_mid", "roi_high"):
        assert isinstance(result[key], float), f"{key} should be float"


def test_roi_ordering():
    result = calculate_roi("corn", 8.0, 25.0, 100.0)
    assert result["roi_low"] <= result["roi_mid"] <= result["roi_high"]


def test_commodity_price_used_default():
    result = calculate_roi("corn", 8.0, 25.0, 100.0)
    assert result["commodity_price_used"] == 4.50


def test_commodity_price_used_override():
    result = calculate_roi("corn", 8.0, 25.0, 100.0, current_commodity_price=6.00)
    assert result["commodity_price_used"] == 6.00


def test_recommendation_strong_buy():
    # High yield loss, low treatment cost → strong positive ROI
    result = calculate_roi("corn", 25.0, 5.0, 100.0)
    assert result["recommendation_strength"] == "Strong Buy"
    assert result["roi_mid"] >= 50.0


def test_recommendation_monitor_only():
    # Tiny yield loss, very high treatment cost → negative ROI
    result = calculate_roi("corn", 0.5, 200.0, 100.0)
    assert result["recommendation_strength"] == "Monitor Only"
    assert result["roi_mid"] < 0.0


def test_zero_yield_loss():
    result = calculate_roi("corn", 0.0, 25.0, 100.0)
    assert result["estimated_yield_loss_bu_acre"] == 0.0
    assert result["revenue_at_risk_total"] == 0.0
    assert result["roi_mid"] < 0.0  # treatment cost with no revenue recovered


def test_revenue_at_risk_total_equals_per_acre_times_acres():
    result = calculate_roi("corn", 8.0, 25.0, 200.0)
    assert abs(result["revenue_at_risk_total"] - result["revenue_at_risk_per_acre"] * 200.0) < 0.01


def test_treatment_cost_total():
    result = calculate_roi("corn", 8.0, 25.0, 150.0)
    assert result["treatment_cost_total"] == 25.0 * 150.0


def test_enrich_rule_has_flat_roi():
    rule = {"rule_id": "NCLB_HIGH", "severity": "High", "alert_type": "disease"}
    enriched = enrich_rule_with_roi(rule, crop_type="corn", field_acres=100.0, treatment_cost_per_acre=25.0)
    assert "roi" in enriched
    assert set(enriched["roi"].keys()) == FLAT_KEYS


def test_moderate_severity_in_lookup():
    """'Moderate' must not fall back to 'Medium' — both map to 8% but Moderate is explicit."""
    result = calculate_roi("corn", 8.0, 25.0, 100.0)   # uses Medium fallback
    moderate = calculate_roi("corn", SEVERITY_YIELD_LOSS["Moderate"] * 100, 25.0, 100.0)
    assert moderate["estimated_yield_loss_bu_acre"] == result["estimated_yield_loss_bu_acre"]


def test_per_rule_yield_impact_overrides_severity():
    """A rule with yield_impact_percent set should use that, not its severity level."""
    rule_with_impact = {
        "rule_id": "LOW_N", "severity": "High",  # High → 15% by severity
        "yield_impact_percent": 12.0,              # but rule says 12%
        "alert_type": "nutrient",
    }
    enriched = enrich_rule_with_roi(rule_with_impact, crop_type="corn", field_acres=100.0, treatment_cost_per_acre=25.0)
    # 12% of 180 bu/acre = 21.6
    assert abs(enriched["roi"]["estimated_yield_loss_bu_acre"] - 21.6) < 0.1


def test_different_rules_different_roi():
    """Rules with different yield_impact_percent must produce different ROI numbers."""
    drought_rule = {"rule_id": "DROUGHT", "severity": "High", "yield_impact_percent": 18.0, "alert_type": "stress"}
    nitrogen_rule = {"rule_id": "LOW_N",  "severity": "Moderate", "yield_impact_percent": 12.0, "alert_type": "nutrient"}
    foliar_rule   = {"rule_id": "FOLIAR", "severity": "Low", "yield_impact_percent": 3.0,  "alert_type": "disease"}

    kwargs = dict(crop_type="corn", field_acres=100.0, treatment_cost_per_acre=25.0)
    d = enrich_rule_with_roi(drought_rule, **kwargs)["roi"]
    n = enrich_rule_with_roi(nitrogen_rule, **kwargs)["roi"]
    f = enrich_rule_with_roi(foliar_rule, **kwargs)["roi"]

    assert d["estimated_yield_loss_bu_acre"] > n["estimated_yield_loss_bu_acre"] > f["estimated_yield_loss_bu_acre"]


def test_soybean_defaults():
    result = calculate_roi("soybean", 8.0, 15.0, 50.0)
    assert result["commodity_price_used"] == 11.00


def test_unknown_crop_fallback():
    result = calculate_roi("millet", 8.0, 25.0, 100.0)
    # Should not raise; falls back to defaults
    assert result["commodity_price_used"] == 4.50
    assert result["estimated_yield_loss_bu_acre"] > 0
