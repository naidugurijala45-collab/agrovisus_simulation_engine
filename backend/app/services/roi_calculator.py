"""
ROI Calculator for crop disease and nutrient interventions.

Given a triggered rule and field parameters, estimates the economic
impact and return on investment for treatment.
"""

from typing import Dict, Any

# Default commodity prices (USD per bushel)
DEFAULT_PRICES_USD_BU: Dict[str, float] = {
    "corn": 4.50,
    "soybean": 11.00,
    "wheat": 5.50,
    "rice": 7.00,
    "sorghum": 4.00,
}

# Typical yield baselines (bushels/acre) for converting kg/ha → bu/acre
YIELD_BASELINE_BU_ACRE: Dict[str, float] = {
    "corn": 180.0,
    "soybean": 50.0,
    "wheat": 60.0,
    "rice": 100.0,
    "sorghum": 80.0,
}

# Conversion: 1 kg/ha ≈ 0.01487 bu/acre (varies by crop density; good average)
KG_HA_TO_BU_ACRE = 0.01487

# Severity → expected yield loss fraction mapping (disease-specific tuning)
# Used when yield_loss_percent is not explicitly provided
SEVERITY_YIELD_LOSS: Dict[str, float] = {
    "Low": 0.03,
    "Medium": 0.08,
    "Moderate": 0.08,
    "High": 0.15,
    "Critical": 0.25,
}


def calculate_roi(
    crop_type: str,
    yield_loss_percent: float,
    treatment_cost_per_acre: float,
    field_acres: float,
    current_commodity_price: float | None = None,
    baseline_yield_bu_acre: float | None = None,
) -> Dict[str, Any]:
    """
    Calculate ROI for a disease/nutrient treatment intervention.

    Args:
        crop_type: Crop name (e.g. "corn", "soybean", "wheat")
        yield_loss_percent: Expected yield loss without treatment (0-100)
        treatment_cost_per_acre: Cost of the intervention in USD/acre
        field_acres: Total field size in acres
        current_commodity_price: Override commodity price (USD/bu). Uses
            DEFAULT_PRICES_USD_BU if not supplied.
        baseline_yield_bu_acre: Override expected yield without disease
            (bu/acre). Uses YIELD_BASELINE_BU_ACRE if not supplied.

    Returns:
        Dict with keys:
            estimated_yield_loss_bu_acre    – yield loss in bu/acre
            revenue_at_risk_per_acre        – USD revenue at risk per acre
            revenue_at_risk_total           – USD revenue at risk for field
            treatment_cost_total            – total treatment cost for field
            roi_low                         – ROI % at 50% treatment efficacy
            roi_mid                         – ROI % at 70% treatment efficacy
            roi_high                        – ROI % at 90% treatment efficacy
            breakeven_yield_loss_percent    – minimum yield loss % where treatment pays off
            recommendation_strength         – "Strong Buy" / "Marginal" / "Monitor Only"
            commodity_price_used            – commodity price applied (USD/bu)
    """
    crop_key = crop_type.lower()

    price = current_commodity_price or DEFAULT_PRICES_USD_BU.get(crop_key, 4.50)
    baseline = baseline_yield_bu_acre or YIELD_BASELINE_BU_ACRE.get(crop_key, 150.0)

    loss_fraction = max(0.0, min(yield_loss_percent, 100.0)) / 100.0

    # Yield loss and revenue at risk
    yield_loss_bu_acre = baseline * loss_fraction
    revenue_at_risk_per_acre = yield_loss_bu_acre * price
    revenue_at_risk_total = revenue_at_risk_per_acre * field_acres
    treatment_cost_total = treatment_cost_per_acre * field_acres

    # Treatment efficacy scenarios (fraction of loss that treatment recovers)
    efficacy = {"low": 0.50, "medium": 0.70, "high": 0.90}
    roi_by_scenario: Dict[str, float] = {}
    for scenario, eff in efficacy.items():
        revenue_saved = revenue_at_risk_total * eff
        net_benefit = revenue_saved - treatment_cost_total
        roi_pct = (net_benefit / treatment_cost_total * 100.0) if treatment_cost_total > 0 else 0.0
        roi_by_scenario[scenario] = round(roi_pct, 1)

    # Breakeven: minimum yield loss % where treatment cost equals revenue saved (medium efficacy)
    eff_medium = efficacy["medium"]
    if (baseline * price * eff_medium * field_acres) > 0:
        breakeven_loss_fraction = treatment_cost_total / (baseline * price * eff_medium * field_acres)
        breakeven_yield_loss_pct = round(breakeven_loss_fraction * 100.0, 2)
    else:
        breakeven_yield_loss_pct = 0.0

    # Recommendation strength
    medium_roi = roi_by_scenario["medium"]
    if medium_roi >= 50.0:
        recommendation_strength = "Strong Buy"
    elif medium_roi >= 0.0:
        recommendation_strength = "Marginal"
    else:
        recommendation_strength = "Monitor Only"

    return {
        "estimated_yield_loss_bu_acre": round(yield_loss_bu_acre, 2),
        "revenue_at_risk_per_acre": round(revenue_at_risk_per_acre, 2),
        "revenue_at_risk_total": round(revenue_at_risk_total, 2),
        "treatment_cost_total": round(treatment_cost_total, 2),
        "roi_low": roi_by_scenario["low"],
        "roi_mid": roi_by_scenario["medium"],
        "roi_high": roi_by_scenario["high"],
        "breakeven_yield_loss_percent": breakeven_yield_loss_pct,
        "recommendation_strength": recommendation_strength,
        "commodity_price_used": round(price, 2),
    }


def enrich_rule_with_roi(
    rule: Dict[str, Any],
    crop_type: str,
    field_acres: float,
    treatment_cost_per_acre: float = 25.0,
    current_commodity_price: float | None = None,
    baseline_yield_bu_acre: float | None = None,
) -> Dict[str, Any]:
    """
    Add an `roi` block to a triggered rule dict.

    Yield loss is inferred from the rule's severity field when present,
    otherwise defaults to medium (8 %).
    """
    severity = rule.get("severity", "Medium")
    # Use per-rule yield_impact_percent if present (set in rules.json per rule);
    # fall back to the severity-level lookup table.
    yield_loss_pct = (
        rule.get("yield_impact_percent")
        or SEVERITY_YIELD_LOSS.get(severity, SEVERITY_YIELD_LOSS["Medium"]) * 100.0
    )

    roi = calculate_roi(
        crop_type=crop_type,
        yield_loss_percent=yield_loss_pct,
        treatment_cost_per_acre=treatment_cost_per_acre,
        field_acres=field_acres,
        current_commodity_price=current_commodity_price,
        baseline_yield_bu_acre=baseline_yield_bu_acre,
    )
    return {**rule, "roi": roi}
