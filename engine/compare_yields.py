"""
compare_yields.py — compare AgroVisus corn yield against AquaCrop benchmark.

AquaCrop 8,992 kg/ha is the published Illinois corn yield for a 120-day
simulation at lat=40, lon=-88 with typical management (150 kg N/ha total,
one pre-plant + one side-dress application, rain-fed).

Run from engine/:
    python compare_yields.py
"""
import sys
import io
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np
from datetime import date, timedelta

from app.models.crop_model import CropModel
from app.models.nutrient_model import NutrientModel
from app.models.soil_model import SoilModel
from app.utils.crop_template_loader import CropTemplateLoader
from app.services.weather_service import WeatherService

AQUACROP_BENCHMARK_KG_HA = 8_992   # AquaCrop Illinois corn reference
TARGET_LOW  = 6_000
TARGET_HIGH = 8_000
SIM_DAYS    = 120
LAT         = 40.0
LON         = -88.0
START_DATE  = date(2024, 4, 15)     # canonical spring planting date

# Management: typical Illinois corn — pre-plant + side-dress
FERT_SCHEDULE = [
    {"day":  7, "amount_kg_ha": 40.0, "fert_type": "urea"},   # pre-plant
    {"day": 40, "amount_kg_ha": 80.0, "fert_type": "urea"},   # side-dress V6
    {"day": 60, "amount_kg_ha": 30.0, "fert_type": "urea"},   # top-dress
]
IRRIG_SCHEDULE = []   # rain-fed

N_RUNS = 5   # average over multiple synthetic-weather seeds to reduce noise

# ──────────────────────────────────────────────────────────────────────────────
def make_model(seed):
    np.random.seed(seed)

    loader = CropTemplateLoader()
    cfg = loader.merge_with_overrides("corn", {
        "crop_template": "corn",
        "initial_stage": "VE",
        "t_base_c": 10.0,
        "t_upper_c": 30.0,
        "water_stress_threshold_awc": 0.4,
        "anaerobic_stress_threshold_awc": 1.0,
        "radiation_use_efficiency_g_mj": 3.5,
        "harvest_index": 0.5,
        "gdd_thresholds": {
            "VE": 0, "V2": 120, "V6": 400, "V10": 650,
            "VT": 850, "R1": 1000, "R3": 1300, "R6": 1800,
        },
        "light_interception_per_stage": {
            "VE": 0.1, "V2": 0.3, "V6": 0.7, "V10": 0.95,
            "VT": 1.0, "R1": 1.0, "R3": 0.9, "R6": 0.7,
        },
        "N_demand_kg_ha_per_stage": {
            "VE": 0.3, "V2": 0.7, "V6": 2.0, "V10": 3.0,
            "VT": 3.5, "R1": 2.5, "R3": 1.5, "R6": 0.5,
        },
    })

    crop = CropModel(
        initial_stage=cfg["initial_stage"],
        gdd_thresholds=cfg["gdd_thresholds"],
        t_base_c=10.0, t_upper_c=30.0,
        n_demand_per_stage=cfg["N_demand_kg_ha_per_stage"],
        water_stress_threshold_awc=0.4,
        anaerobic_stress_threshold_awc=1.0,
        radiation_use_efficiency_g_mj=3.5,
        light_interception_per_stage=cfg["light_interception_per_stage"],
        harvest_index=0.5,
        max_root_depth_mm=1200.0,
        daily_root_growth_rate_mm=15.0,
        vegetative_stages=cfg["vegetative_stages"],
        reproductive_stages=cfg["reproductive_stages"],
    )

    nutrient = NutrientModel(
        initial_nitrate_N_kg_ha=40.0,
        initial_ammonium_N_kg_ha=10.0,
        max_daily_urea_hydrolysis_rate=0.35,
        max_daily_nitrification_rate=0.20,
        temp_base=2.0, temp_opt=30.0, temp_max=45.0,
    )

    soil = SoilModel(
        soil_type_name="Silt Loam",
        soil_depth_mm=600.0,
        initial_moisture_fraction_awc=0.6,
        custom_soil_params={
            "fc": 120.0 / 600.0,
            "wp": 55.0  / 600.0,
            "sat": 0.45,
            "description": "Silt Loam",
        },
    )

    ws_cfg = {"weather_service": {"cache_enabled": False, "preferred_source": "auto"}}
    ws = WeatherService(ws_cfg, ".")

    # Build management event dict keyed by day
    mgmt: dict = {}
    for ev in FERT_SCHEDULE:
        mgmt.setdefault(ev["day"], []).append(ev)
    for ev in IRRIG_SCHEDULE:
        mgmt.setdefault(ev["day"], []).append(ev)

    transitions = []
    prev_stage = crop.current_stage

    for d in range(SIM_DAYS):
        day_num = d + 1
        cdate = START_DATE + timedelta(days=d)
        wx = ws._generate_synthetic_daily(LAT, cdate)

        # Management
        irrig_mm = 0.0
        for ev in mgmt.get(day_num, []):
            if "amount_mm" in ev:
                irrig_mm += ev["amount_mm"]
            if "amount_kg_ha" in ev:
                nutrient.add_fertilizer(ev["amount_kg_ha"], ev.get("fert_type", "urea"))

        soil.update_daily(
            precipitation_mm=wx["total_precip_mm"],
            irrigation_mm=irrig_mm,
            et0_mm=4.0,
            crop_coefficient_kc=0.8,
            root_depth_mm=crop.root_depth_mm,
        )
        soil_status = soil.get_soil_moisture_status()

        n_demand = crop.get_daily_n_demand()
        actual_n = nutrient.update_daily(n_demand, 0.0, wx["avg_temp_c"], soil_status)

        crop.update_daily(
            wx["min_temp_c"], wx["max_temp_c"],
            wx["total_solar_rad_mj_m2"],
            actual_n, soil_status, 1.0,
        )

        if crop.current_stage != prev_stage:
            transitions.append((day_num, prev_stage, crop.current_stage, crop.accumulated_gdd))
            prev_stage = crop.current_stage

    return crop, transitions


# ──────────────────────────────────────────────────────────────────────────────
print("=" * 65)
print("  AgroVisus vs AquaCrop Yield Comparison")
print(f"  Corn, {SIM_DAYS}-day sim, lat={LAT}, start={START_DATE}")
print(f"  Management: {sum(e['amount_kg_ha'] for e in FERT_SCHEDULE):.0f} kg N/ha total")
print("=" * 65)

yields = []
biomasses = []

for seed in range(N_RUNS):
    crop, transitions = make_model(seed)
    y = crop.get_final_yield()
    b = crop.total_biomass_kg_ha
    yields.append(y)
    biomasses.append(b)

    repro_pct = (crop.reproductive_biomass_kg_ha / b * 100) if b else 0
    trans_str = "  ".join(f"{f}->{t}@d{d}" for d, f, t, _ in transitions)
    print(f"  Seed {seed}: stage={crop.current_stage:<3}  GDD={crop.accumulated_gdd:>6.0f}"
          f"  biomass={b:>7,.0f}  yield={y:>7,.0f}  repro={repro_pct:.0f}%")
    if transitions:
        print(f"         stages: {trans_str}")

avg_yield    = sum(yields) / len(yields)
avg_biomass  = sum(biomasses) / len(biomasses)
pct_vs_aquacrop = (avg_yield / AQUACROP_BENCHMARK_KG_HA - 1) * 100

print()
print("=" * 65)
print(f"  Average yield    : {avg_yield:>8,.0f} kg/ha")
print(f"  Average biomass  : {avg_biomass:>8,.0f} kg/ha")
print(f"  AquaCrop target  : {AQUACROP_BENCHMARK_KG_HA:>8,} kg/ha")
print(f"  Difference       : {pct_vs_aquacrop:>+8.1f}%")
print()
if TARGET_LOW <= avg_yield <= TARGET_HIGH:
    print(f"  PASS  AgroVisus yield is within target range "
          f"[{TARGET_LOW:,}–{TARGET_HIGH:,} kg/ha]")
elif avg_yield > TARGET_HIGH:
    print(f"  HIGH  Yield above target — RUE or management may need tuning")
else:
    print(f"  LOW   Yield below target — check N supply or stress factors")
print("=" * 65)
