"""
Direct 90-day corn crop simulation runner — bypasses FastAPI.
"""
import json
import sys
import csv
import os
import tempfile
from pathlib import Path
from datetime import date

# ── Engine path setup ──────────────────────────────────────────────────────
ROOT = Path(r"c:\Users\Naidu Gurijala\CropDiagnosisPlatform")
ENGINE_ROOT = ROOT / "agrovisus_simulation_engine"
sys.path.insert(0, str(ENGINE_ROOT))

from app.services.simulation_service import SimulationService

# ── Config ─────────────────────────────────────────────────────────────────
with open(ENGINE_ROOT / "config.json") as f:
    config = json.load(f)

config["simulation_settings"]["latitude_degrees"]  = 40.0
config["simulation_settings"]["longitude_degrees"] = -88.0
config["simulation_settings"]["elevation_m"]       = 100.0
config["crop_model_config"]["crop_template"]       = "corn"

SIM_DAYS   = 90
START_DATE = date(2024, 4, 15)

print("=" * 65)
print("  AgroVisus — 90-Day Corn Crop Simulation")
print(f"  Start: {START_DATE}  |  Days: {SIM_DAYS}  |  Crop: Corn")
print(f"  Location: 40.0°N, 88.0°W  |  Elevation: 100m")
print("=" * 65)

# ── Run ────────────────────────────────────────────────────────────────────
service = SimulationService(config_data=config, project_root=str(ENGINE_ROOT))

with tempfile.NamedTemporaryFile(mode='w', suffix=".csv", delete=False) as tmp:
    tmp_path = tmp.name

result = service.run_simulation(
    start_date=START_DATE,
    sim_days=SIM_DAYS,
    output_csv_path=tmp_path,
)

# ── Parse CSV ──────────────────────────────────────────────────────────────
rows = []
with open(tmp_path, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader, 1):
        def g(k):
            try: return float(row.get(k, 0) or 0)
            except: return 0.0
        rows.append({
            "day":            i,
            "date":           row.get("date", ""),
            "stage":          row.get("crop_growth_stage", "unknown"),
            "biomass":        g("total_biomass_kg_ha"),
            "soil_moisture":  g("fraction_awc"),
            "disease":        g("disease_severity_percent"),
            "water_stress":   g("water_stress_factor"),
            "n_stress":       g("nitrogen_stress_factor"),
            "irrigation_mm":  g("daily_irrigation_mm"),
            "precip_mm":      g("daily_precipitation_mm"),
            "temp_c":         g("daily_avg_temp_c"),
        })
os.unlink(tmp_path)

# ── Summary KPIs ───────────────────────────────────────────────────────────
total_biomass   = result.get("total_biomass_kg_ha", rows[-1]["biomass"] if rows else 0)
final_yield     = result.get("final_yield_kg_ha", total_biomass * 0.45)
total_irr       = sum(r["irrigation_mm"] for r in rows)
total_precip    = sum(r["precip_mm"] for r in rows)
max_disease     = max(r["disease"] for r in rows) if rows else 0
triggered_rules = result.get("triggered_rules", [])

print(f"\n{'─'*65}")
print("  SUMMARY KPIs")
print(f"{'─'*65}")
print(f"  Total Biomass (dry matter) : {total_biomass:>10,.1f}  kg/ha")
print(f"  Estimated Grain Yield      : {final_yield:>10,.1f}  kg/ha")
print(f"  Total Irrigation Applied   : {total_irr:>10,.1f}  mm")
print(f"  Total Precipitation        : {total_precip:>10,.1f}  mm")
print(f"  Peak Disease Severity      : {max_disease:>10,.2f}  %")
print(f"  Advisory Rules Triggered   : {len(triggered_rules):>10}")

# ── Stage timeline ─────────────────────────────────────────────────────────
print(f"\n{'─'*65}")
print("  CROP STAGE PROGRESSION  (every 10 days)")
print(f"{'─'*65}")
print(f"  {'Day':>4}  {'Date':>12}  {'Stage':>18}  {'Biomass':>10}  {'Moisture':>9}  {'Temp°C':>7}")
print(f"  {'---':>4}  {'----':>12}  {'-----':>18}  {'-------':>10}  {'--------':>9}  {'------':>7}")
for r in rows:
    if r["day"] % 10 == 0 or r["day"] == 1 or r["day"] == len(rows):
        print(f"  {r['day']:>4}  {r['date']:>12}  {r['stage']:>18}  {r['biomass']:>10,.0f}  {r['soil_moisture']:>9.3f}  {r['temp_c']:>7.1f}")

# ── Daily stress summary (every 15 days) ──────────────────────────────────
print(f"\n{'─'*65}")
print("  STRESS FACTORS  (every 15 days)")
print(f"{'─'*65}")
print(f"  {'Day':>4}  {'Water Stress':>13}  {'N Stress':>9}  {'Disease%':>9}  {'Irr mm':>7}")
print(f"  {'---':>4}  {'------------':>13}  {'--------':>9}  {'--------':>9}  {'------':>7}")
for r in rows:
    if r["day"] % 15 == 0 or r["day"] == 1:
        ws_bar = "█" * int(r["water_stress"] * 10) + "░" * (10 - int(r["water_stress"] * 10))
        print(f"  {r['day']:>4}  {ws_bar} {r['water_stress']:>4.2f}  {r['n_stress']:>9.3f}  {r['disease']:>9.2f}  {r['irrigation_mm']:>7.1f}")

# ── Triggered rules ────────────────────────────────────────────────────────
if triggered_rules:
    print(f"\n{'─'*65}")
    print(f"  ⚡ ADVISORY RULES TRIGGERED ({len(triggered_rules)} events)")
    print(f"{'─'*65}")
    for event in triggered_rules[:10]:
        rules = event.get("rules", [])
        for rule in rules:
            print(f"  [{event.get('date','?')}]  {rule.get('name', rule.get('rule_id','?'))}")

# ── Save CSV ───────────────────────────────────────────────────────────────
out_csv = ROOT / "outputs" / "corn_90day_simulation.csv"
out_csv.parent.mkdir(exist_ok=True)
fieldnames = ["day","date","stage","biomass","soil_moisture","disease","water_stress","n_stress","irrigation_mm","precip_mm","temp_c"]
with open(out_csv, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"\n{'─'*65}")
print(f"  ✅ Simulation complete! {len(rows)} days of daily data.")
print(f"  📄 CSV saved to: outputs/corn_90day_simulation.csv")
print(f"{'─'*65}\n")
