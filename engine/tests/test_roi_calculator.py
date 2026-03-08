"""Tests for the flat ROI calculator output structure."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.services.roi_calculator import calculate_roi, enrich_rule_with_roi

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


def test_soybean_defaults():
    result = calculate_roi("soybean", 8.0, 15.0, 50.0)
    assert result["commodity_price_used"] == 11.00


def test_unknown_crop_fallback():
    result = calculate_roi("millet", 8.0, 25.0, 100.0)
    # Should not raise; falls back to defaults
    assert result["commodity_price_used"] == 4.50
    assert result["estimated_yield_loss_bu_acre"] > 0
