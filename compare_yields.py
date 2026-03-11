"""
compare_yields.py
-----------------
Runs two parallel 120-day corn simulations starting May 1 for Illinois and
prints final yields side by side:

  1. AgroVisus engine  — corn template, SandyLoam, IL weather, realistic
                         N management (180 kg N/ha: starter + sidedress + topdress)
  2. AquaCrop-OSPy     — Maize, SandyLoam, Champaign IL climate file, rainfed
                         at field capacity (upper-bound / no disease)

Usage:
    python compare_yields.py      (system Python with aquacrop installed)
"""

import json
import logging
import os
import sys
import tempfile
from datetime import date

import pandas as pd
from aquacrop import AquaCropModel, Crop, InitialWaterContent, Soil
from aquacrop.utils import prepare_weather

# ── Silence engine / pyet noise ──────────────────────────────────────────────
logging.disable(logging.CRITICAL)
import warnings
warnings.filterwarnings("ignore")

# ── Common settings ───────────────────────────────────────────────────────────
SIM_YEAR  = 2018      # latest year in champion_climate.txt (for AquaCrop)
SIM_DAYS  = 120
START_DATE_ENGINE = date(SIM_YEAR, 5, 1)
PLANT_DATE_AQUA   = f"{SIM_YEAR}/05/01"

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ENGINE_ROOT  = os.path.join(PROJECT_ROOT, "engine")

# ── AgroVisus engine setup ────────────────────────────────────────────────────
sys.path.insert(0, ENGINE_ROOT)
from app.services.simulation_service import SimulationService   # noqa: E402

# Build config: corn template + realistic Illinois N management
# (180 kg N/ha total: starter at planting, sidedress at V6, topdress at VT)
cfg = json.load(open(os.path.join(PROJECT_ROOT, "config.json")))
cfg["crop_model_config"]["crop_template"] = "corn"
cfg["management_schedule"] = [
    # ── Nitrogen: 180 kg N/ha total (starter + sidedress + topdress) ──────────
    {"day":  5, "type": "fertilizer", "fertilizer_type": "urea", "amount_kg_ha": 40.0},
    {"day": 35, "type": "fertilizer", "fertilizer_type": "urea", "amount_kg_ha": 100.0},
    {"day": 70, "type": "fertilizer", "fertilizer_type": "urea", "amount_kg_ha": 40.0},
    # ── Irrigation: 25-30 mm every 7-10 days to maintain moisture ────────────
    {"day": 10, "type": "irrigation", "amount_mm": 25.0},
    {"day": 20, "type": "irrigation", "amount_mm": 25.0},
    {"day": 30, "type": "irrigation", "amount_mm": 25.0},
    {"day": 40, "type": "irrigation", "amount_mm": 25.0},
    {"day": 50, "type": "irrigation", "amount_mm": 30.0},
    {"day": 60, "type": "irrigation", "amount_mm": 30.0},
    {"day": 68, "type": "irrigation", "amount_mm": 30.0},
    {"day": 76, "type": "irrigation", "amount_mm": 30.0},   # VT — critical
    {"day": 83, "type": "irrigation", "amount_mm": 30.0},   # R1 — critical
    {"day": 90, "type": "irrigation", "amount_mm": 30.0},   # R1 — critical
    {"day": 97, "type": "irrigation", "amount_mm": 30.0},   # R3
    {"day": 104, "type": "irrigation", "amount_mm": 25.0},  # R3
    {"day": 111, "type": "irrigation", "amount_mm": 25.0},  # R3/R6
]

# ── Run AgroVisus ─────────────────────────────────────────────────────────────
print("Running AgroVisus engine simulation ...")
print(f"  Template : corn (IL profile)")
print(f"  Soil     : SandyLoam (regional defaults)")
print(f"  N mgmt   : 40+100+40 kg N/ha urea (starter/sidedress/topdress = 180 kg N/ha)")
print(f"  Irrig    : 25-30 mm every 7-10 d through grain fill (~385 mm seasonal)")
print(f"  Period   : {START_DATE_ENGINE}  ({SIM_DAYS} days)")
print()

with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
    tmp_path = tmp.name

try:
    svc = SimulationService(config_data=cfg, project_root=ENGINE_ROOT, state_code="IL")
    result = svc.run_simulation(
        start_date=START_DATE_ENGINE,
        sim_days=SIM_DAYS,
        output_csv_path=tmp_path,
    )
    df_engine = pd.read_csv(tmp_path)
finally:
    os.unlink(tmp_path)

agrovisus_yield_kg = result["final_yield_kg_ha"]
agrovisus_biomass  = result["total_biomass_kg_ha"]
engine_stage_dist  = df_engine["crop_growth_stage"].value_counts().to_dict()
engine_gdd         = df_engine["gdd_accumulated"].iloc[-1]
engine_final_stage = df_engine["crop_growth_stage"].iloc[-1]
n_stress_mean      = df_engine["nitrogen_stress_factor"].mean()
water_stress_mean  = df_engine["water_stress_factor"].mean()

# ── AquaCrop-OSPy setup ───────────────────────────────────────────────────────
aq_data_dir  = os.path.join(os.path.dirname(__import__("aquacrop").__file__), "data")
weather_path = os.path.join(aq_data_dir, "champion_climate.txt")
if not os.path.exists(weather_path):
    print(f"ERROR: champion_climate.txt not found at {weather_path}")
    sys.exit(1)

weather_df = prepare_weather(weather_path)

print("Running AquaCrop-OSPy simulation ...")
print(f"  Location : Champaign, Illinois (champion_climate.txt)")
print(f"  Soil     : SandyLoam")
print(f"  Crop     : Maize (corn)")
print(f"  Period   : {PLANT_DATE_AQUA}  ({SIM_DAYS}-day window)")
print()

aquacrop_model = AquaCropModel(
    sim_start_time=PLANT_DATE_AQUA,
    sim_end_time=f"{SIM_YEAR}/10/31",   # generous end; auto-terminates at harvest
    weather_df=weather_df,
    soil=Soil("SandyLoam"),
    crop=Crop("Maize", planting_date="05/01"),
    initial_water_content=InitialWaterContent(value=["FC"]),
)
aquacrop_model.run_model(till_termination=True)

crop_growth = aquacrop_model.get_crop_growth()
row_120 = crop_growth[crop_growth["dap"] == SIM_DAYS]
if row_120.empty:
    row_120 = crop_growth[crop_growth["dap"] <= SIM_DAYS].iloc[[-1]]
aquacrop_yield_day120_kg = float(row_120["DryYield"].iloc[0]) * 1000

harvest_results = aquacrop_model.get_simulation_results()
if not harvest_results.empty:
    harvest_yield_kg = float(harvest_results["Dry yield (tonne/ha)"].iloc[0]) * 1000
    harvest_date     = str(harvest_results["Harvest Date (YYYY/MM/DD)"].iloc[0])[:10]
    harvest_dap      = int(harvest_results["Harvest Date (Step)"].iloc[0])
else:
    harvest_yield_kg, harvest_date, harvest_dap = None, "N/A", None

# ── Print comparison ──────────────────────────────────────────────────────────
diff_kg  = agrovisus_yield_kg - aquacrop_yield_day120_kg
diff_pct = (diff_kg / aquacrop_yield_day120_kg) * 100 if aquacrop_yield_day120_kg else 0
direction = "higher" if diff_kg >= 0 else "lower"

print("=" * 66)
print(f"  {'Source':<40} {'Yield (kg/ha)':>14}")
print("-" * 66)
print(f"  {'AgroVisus engine  (stressed, 120 d)':<40} {agrovisus_yield_kg:>14,.0f}")
print(f"  {'AquaCrop-OSPy     (rainfed/FC, day 120)':<40} {aquacrop_yield_day120_kg:>14,.0f}")
print("-" * 66)
print(f"  {'Difference  (AgroVisus - AquaCrop)':<40} {diff_kg:>+14,.0f}")
print(f"  {'Relative difference':<40} {diff_pct:>+13.1f}%")
print("=" * 66)

if harvest_yield_kg is not None:
    print(f"\n  AquaCrop full-maturity yield (day {harvest_dap}, {harvest_date}): "
          f"{harvest_yield_kg:,.0f} kg/ha")

print()
print(f"  AgroVisus details (120 d):")
print(f"    Total biomass      : {agrovisus_biomass:,.0f} kg/ha")
print(f"    Final stage        : {engine_final_stage}   GDD: {engine_gdd:.0f}")
print(f"    N-stress (mean)    : {n_stress_mean:.2f}")
print(f"    Water-stress (mean): {water_stress_mean:.2f}")
print(f"    Stage distribution : {engine_stage_dist}")
print()
print(f"AgroVisus is {abs(diff_pct):.1f}% {direction} than AquaCrop at day 120.")
print("AquaCrop upper-bound: rainfed at FC, no disease, no N limitation.")
print("AgroVisus applies real weather stress, disease pressure, and N cycling.")
