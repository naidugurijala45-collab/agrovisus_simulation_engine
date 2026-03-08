import json
import urllib.request

PAYLOAD_BASE = {
    "crop_template": "corn",
    "sim_days": 30,
    "start_date": "2025-06-01",
    "latitude": 40.0,
    "longitude": -88.0,
    "elevation_m": 100.0,
    "field_acres": 100,
    "treatment_cost_per_acre": 25,
    "commodity_price_usd_bu": 4.50,
    "management_schedule": [],
}


def post(state_code):
    payload = {**PAYLOAD_BASE, "state_code": state_code}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "http://localhost:8001/api/simulation/run",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


print("Posting OH (corn_belt) ...")
oh = post("OH")
print("Posting GA (southeast) ...")
ga = post("GA")

SEP = "=" * 60

for label, res in [("OH — corn_belt  (GLS multiplier 1.0)", oh),
                   ("GA — southeast  (GLS multiplier 1.5)", ga)]:
    rules = res.get("triggered_rules", [])
    print(f"\n{SEP}")
    print(f"STATE: {label}")
    print(f"  Max disease severity : {res['max_disease_severity']:.4f} %")
    print(f"  Triggered rule days  : {len(rules)}")

    if not rules:
        print("  (no rules triggered — conditions stayed within thresholds)")
    for day_entry in rules:
        for r in day_entry.get("rules", []):
            print(f"\n  [{day_entry['date']}] {r['rule_id']}")
            print(f"    severity   : {r.get('severity')}")
            print(f"    alert_type : {r.get('alert_type')}")
            print(f"    rec        : {r.get('recommendation', '')[:80]}")
            roi = r.get("roi")
            if roi:
                print(f"    ROI block  :")
                print(f"      yield_loss          = {roi['estimated_yield_loss_bu_acre']} bu/acre")
                print(f"      revenue_at_risk     = ${roi['revenue_at_risk_per_acre']}/acre  (${roi['revenue_at_risk_total']} total)")
                print(f"      treatment_cost      = ${roi['treatment_cost_total']} total")
                print(f"      roi_low/mid/high    = {roi['roi_low']}% / {roi['roi_mid']}% / {roi['roi_high']}%")
                print(f"      breakeven           = {roi['breakeven_yield_loss_percent']}% yield loss")
                print(f"      commodity_price     = ${roi['commodity_price_used']}/bu")
                print(f"      recommendation      = {roi['recommendation_strength']}")

print(f"\n{SEP}")
print("COMPARISON — max_disease_severity:")
print(f"  OH: {oh['max_disease_severity']:.4f}%")
print(f"  GA: {ga['max_disease_severity']:.4f}%")
print(f"  Ratio GA/OH: {ga['max_disease_severity'] / max(oh['max_disease_severity'], 0.0001):.2f}x")
print("(GA should be higher due to GLS 1.5x and common_rust 1.3x multipliers)")
