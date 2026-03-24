"""
Full dual-scenario diagnostic.
Reports ET0, stress, yield, alerts, and yield gap.
"""
import sys, json, csv, warnings
from datetime import date, timedelta
from collections import defaultdict

warnings.filterwarnings("ignore")
sys.path.insert(0, ".")

from app.services.simulation_service import SimulationService

# ── helpers ──────────────────────────────────────────────────────────────────
def run_scenario(label, no3, awc, management, csv_path):
    with open("config.json") as f:
        cfg = json.load(f)
    cfg["simulation_settings"]["latitude_degrees"]             = 40.0
    cfg["simulation_settings"]["longitude_degrees"]            = -89.0
    cfg["simulation_settings"]["initial_moisture_fraction_awc"] = awc
    cfg["crop_model_config"]["crop_template"]                  = "corn"
    cfg["nutrient_model_config"]["initial_nitrate_N_kg_ha"]    = no3
    cfg["et0_config"]["default_method"]                        = "penman_monteith"
    cfg["management_schedule"]                                 = management

    svc = SimulationService(config_data=cfg, project_root=".")
    result = svc.run_simulation(
        start_date=date(2025, 5, 1),
        sim_days=120,
        output_csv_path=csv_path,
    )
    return result, cfg


def load_csv(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def parse_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _load_rule_severity_map():
    """Return {rule_id: severity} from rules.json."""
    try:
        with open("rules.json") as f:
            data = json.load(f)
        return {r["id"]: r["result"].get("severity", "").lower() for r in data.get("rules", [])}
    except Exception:
        return {}

_RULE_SEV = _load_rule_severity_map()

def count_alerts(rows):
    """CSV stores triggered_rules as comma-separated rule IDs."""
    high = mod = low = 0
    unique_rules = set()
    for r in rows:
        raw = r.get("triggered_rules", "").strip()
        if not raw or raw in ("[]", ""):
            continue
        rule_ids = [rid.strip() for rid in raw.split(",") if rid.strip()]
        for rid in rule_ids:
            unique_rules.add(rid)
            sev = _RULE_SEV.get(rid, "").lower()
            if sev == "high":
                high += 1
            elif sev == "moderate":
                mod += 1
            elif sev == "low":
                low += 1
    return high, mod, low, unique_rules


# ── run scenarios ─────────────────────────────────────────────────────────────
print("Running Problem Field  (N=20 kg/ha, AWC=0.40, no management)...")
res1, _ = run_scenario(
    "PROBLEM FIELD",
    no3=20.0, awc=0.40, management=[],
    csv_path="outputs/diag_problem.csv",
)

print("Running Well-Managed Field  (N=90 kg/ha, AWC=0.85, day-7 urea)...")
res2, _ = run_scenario(
    "WELL-MANAGED",
    no3=90.0, awc=0.85,
    management=[{"day": 7, "type": "fertilizer", "amount_kg_ha": 120,
                 "fertilizer_type": "urea"}],
    csv_path="outputs/diag_wellmanaged.csv",
)

rows1 = load_csv("outputs/diag_problem.csv")
rows2 = load_csv("outputs/diag_wellmanaged.csv")

# ── soil setup diagnostics ─────────────────────────────────────────────────
from app.models.soil_model import SoilModel
from app.services.simulation_pipeline import estimate_soil_temp_25cm

def paw_for_config(cfg):
    sp = cfg.get("soil_parameters", {})
    dp = cfg["simulation_inputs"]["assumed_root_zone_depth_mm"]
    fc = sp.get("field_capacity_mm", 100.0)
    wp = sp.get("wilting_point_mm",   48.0)
    sat = sp.get("saturation_volumetric", 0.43)
    theta_fc  = fc  / dp
    theta_wp  = wp  / dp
    soil = SoilModel(
        soil_type_name="diag",
        soil_depth_mm=dp,
        custom_soil_params={"fc": theta_fc, "wp": theta_wp, "sat": sat},
    )
    return sum(l.awc_mm for l in soil.layers), soil.layers

with open("config.json") as _f:
    _base_cfg = json.load(_f)

_paw, _layers = paw_for_config(_base_cfg)
_layer_depths = [l.depth_mm for l in _layers]

# Soil temp on Day 1 (DOY 121 = May 1), use ~15 C air temp as proxy
_tsoil_may1 = estimate_soil_temp_25cm(doy=121, tair_mean=15.0)

print()
print("SOIL SETUP (from config.json):")
print(f"  Root zone depth : {_base_cfg['simulation_inputs']['assumed_root_zone_depth_mm']:.0f} mm")
print(f"  Layer depths    : {_layer_depths}")
print(f"  Total PAW       : {_paw:.1f} mm")
print(f"  Soil T 25cm May1: {_tsoil_may1:.1f} C  (tair=15 C proxy)")
print()

# ── ET0 extraction ────────────────────────────────────────────────────────────
def get_et0_series(rows):
    return [(r["date"], parse_float(r["daily_et0_mm"])) for r in rows]

et0_1 = get_et0_series(rows1)
et0_2 = get_et0_series(rows2)

# Day 1  (May 1)
et0_day1_prob = et0_1[0][1]
et0_day1_well = et0_2[0][1]

# Peak summer: dates in July (month 7)
july_et0_1 = [v for d, v in et0_1 if "-07-" in d]
july_et0_2 = [v for d, v in et0_2 if "-07-" in d]
peak_et0_1 = max(july_et0_1) if july_et0_1 else None
peak_et0_2 = max(july_et0_2) if july_et0_2 else None
avg_et0_july_1 = (sum(july_et0_1) / len(july_et0_1)) if july_et0_1 else None
avg_et0_july_2 = (sum(july_et0_2) / len(july_et0_2)) if july_et0_2 else None

# ── stress factors ─────────────────────────────────────────────────────────────
def stress_profile(rows):
    dates, wsf, nsf, osf, awc = [], [], [], [], []
    for r in rows:
        dates.append(r["date"])
        wsf.append(parse_float(r["water_stress_factor"], 1.0))
        nsf.append(parse_float(r["nitrogen_stress_factor"], 1.0))
        osf.append(parse_float(r["overall_stress_factor"], 1.0))
        awc.append(parse_float(r["fraction_awc"]))
    return dates, wsf, nsf, osf, awc

d1, wsf1, nsf1, osf1, awc1 = stress_profile(rows1)
d2, wsf2, nsf2, osf2, awc2 = stress_profile(rows2)

# ── yield ─────────────────────────────────────────────────────────────────────
def get_yield(result, rows):
    y_kg = result.get("final_yield_kg_ha") or result.get("total_biomass_kg_ha", 0) * 0.5
    bu   = y_kg / 62.77
    return y_kg, bu

y1_kg, y1_bu = get_yield(res1, rows1)
y2_kg, y2_bu = get_yield(res2, rows2)

# ── alerts ────────────────────────────────────────────────────────────────────
h1, m1, l1, u1 = count_alerts(rows1)
h2, m2, l2, u2 = count_alerts(rows2)

# ── print report ─────────────────────────────────────────────────────────────
SEP = "=" * 64
HSEP = "-" * 64

print()
print(SEP)
print("  DUAL SCENARIO DIAGNOSTIC REPORT  --  2025-05-01 start, 120 days")
print(SEP)

for label, et0d1, peak_et0, avg_july, y_kg, y_bu, h, m, l, uniq, wsf, nsf, awc_s in [
    ("PROBLEM FIELD  (N=20, AWC=0.40, no mgmt)",
     et0_day1_prob, peak_et0_1, avg_et0_july_1,
     y1_kg, y1_bu, h1, m1, l1, u1, wsf1, nsf1, awc1),
    ("WELL-MANAGED   (N=90, AWC=0.85, day-7 urea)",
     et0_day1_well, peak_et0_2, avg_et0_july_2,
     y2_kg, y2_bu, h2, m2, l2, u2, wsf2, nsf2, awc2),
]:
    print()
    print(f"  {label}")
    print(HSEP)

    # ET0
    print(f"  ET0")
    print(f"    Day 1 (May 1):        {et0d1:>6.2f} mm/day")
    if peak_et0 is not None:
        print(f"    Peak (July):          {peak_et0:>6.2f} mm/day")
        print(f"    Avg  (July):          {avg_july:>6.2f} mm/day")
    else:
        print("    (No July days in 120-day window)")

    # Yield
    print(f"  Yield")
    print(f"    Final biomass-based:  {y_kg:>8,.0f} kg/ha")
    print(f"    Grain (HI=0.5):       {y_kg:>8,.0f} kg/ha  ({y_bu:>5.1f} bu/acre)")

    # Alerts
    print(f"  Alerts  (trigger-days, not unique rules)")
    print(f"    HIGH:     {h:>4}   MODERATE: {m:>4}   LOW: {l:>4}")
    print(f"    Unique rule IDs fired: {len(uniq)}")

    # Stress profile summary
    wsf_mean = sum(wsf)/len(wsf) if wsf else 1.0
    nsf_mean = sum(nsf)/len(nsf) if nsf else 1.0
    wsf_min  = min(wsf) if wsf else 1.0
    nsf_min  = min(nsf) if nsf else 1.0
    awc_mean = sum(awc_s)/len(awc_s) if awc_s else 0.0
    awc_min  = min(awc_s) if awc_s else 0.0

    # Stress days (factor < 0.90 = meaningful stress)
    wsf_stress_days = sum(1 for v in wsf if v < 0.90)
    nsf_stress_days = sum(1 for v in nsf if v < 0.90)

    print(f"  Stress factors  (1.0 = no stress)")
    print(f"    Water:    mean={wsf_mean:.3f}  min={wsf_min:.3f}  days<0.90: {wsf_stress_days}")
    print(f"    Nitrogen: mean={nsf_mean:.3f}  min={nsf_min:.3f}  days<0.90: {nsf_stress_days}")
    print(f"  Soil moisture")
    print(f"    Avg fraction AWC: {awc_mean:.3f}   Min fraction AWC: {awc_min:.3f}")

print()
print(SEP)
gap_kg = y2_kg - y1_kg
gap_bu = y2_bu - y1_bu
print(f"  YIELD GAP")
print(f"    {gap_kg:>8,.0f} kg/ha  ({gap_bu:.1f} bu/acre)")
print(f"    ROI at $4.50/bu x 100 acres: ${gap_bu * 4.50 * 100:,.0f}")
print(SEP)

# ── Stress chart profile (text sparkline by 10-day buckets) ─────────────────
print()
print("  WATER STRESS FACTOR PROFILE — 10-day buckets (1.0=no stress, <0.7=severe)")
print(HSEP)
BUCKETS = 12
n = len(wsf1)
bucket = max(1, n // BUCKETS)

def bar(v, width=20):
    filled = int(round(v * width))
    return "[" + "#" * filled + "." * (width - filled) + f"] {v:.2f}"

header = "  Day range      PROBLEM  (wsf)                WELL-MANAGED  (wsf)"
print(header)
for i in range(0, n, bucket):
    chunk1 = wsf1[i:i+bucket]
    chunk2 = wsf2[i:i+bucket]
    if not chunk1:
        continue
    avg1 = sum(chunk1)/len(chunk1)
    avg2 = sum(chunk2)/len(chunk2) if chunk2 else 1.0
    day_s = i+1
    day_e = min(i+bucket, n)
    date_s = d1[i]
    print(f"  {day_s:>3}-{day_e:<3}  ({date_s})  {bar(avg1)}   {bar(avg2)}")

print()
print("  NITROGEN STRESS FACTOR PROFILE — 10-day buckets")
print(HSEP)
print(header.replace("wsf", "nsf"))
for i in range(0, n, bucket):
    chunk1 = nsf1[i:i+bucket]
    chunk2 = nsf2[i:i+bucket]
    if not chunk1:
        continue
    avg1 = sum(chunk1)/len(chunk1)
    avg2 = sum(chunk2)/len(chunk2) if chunk2 else 1.0
    day_s = i+1
    day_e = min(i+bucket, n)
    date_s = d1[i]
    print(f"  {day_s:>3}-{day_e:<3}  ({date_s})  {bar(avg1)}   {bar(avg2)}")

print()
print("  FRACTION AWC PROFILE — 10-day buckets")
print(HSEP)
print("  Day range      PROBLEM  (awc)                WELL-MANAGED  (awc)")
for i in range(0, n, bucket):
    chunk1 = awc1[i:i+bucket]
    chunk2 = awc2[i:i+bucket]
    if not chunk1:
        continue
    avg1 = sum(chunk1)/len(chunk1)
    avg2 = sum(chunk2)/len(chunk2) if chunk2 else 0.0
    day_s = i+1
    day_e = min(i+bucket, n)
    date_s = d1[i]
    print(f"  {day_s:>3}-{day_e:<3}  ({date_s})  {bar(avg1)}   {bar(avg2)}")

print()
