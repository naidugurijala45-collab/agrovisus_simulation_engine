"""
Diagnostic 1: Harvest Index application chain
Diagnostic 2: Soil water buffer capacity
Diagnosis only — no changes.
"""
import sys, json, csv, warnings
from datetime import date

warnings.filterwarnings("ignore")
sys.path.insert(0, ".")

SEP  = "=" * 68
HSEP = "-" * 68

# ── shared helpers ────────────────────────────────────────────────────────────
def pf(v, default=0.0):
    try: return float(v)
    except: return default


# ─────────────────────────────────────────────────────────────────────────────
# Diagnostic 1 — Harvest Index
# ─────────────────────────────────────────────────────────────────────────────
print()
print(SEP)
print("  DIAGNOSTIC 1: Harvest Index Application Chain")
print(SEP)

# ── 1a. Template value ────────────────────────────────────────────────────────
with open("app/data/crop_templates.json") as f:
    tmpl = json.load(f)
tmpl_hi = tmpl["corn"]["growth"]["harvest_index"]
print(f"\n  Template corn.growth.harvest_index = {tmpl_hi}")

# ── 1b. What CropModel.get_final_yield() actually uses ───────────────────────
import ast, inspect
from app.models.crop_model import CropModel
src_lines = inspect.getsource(CropModel.get_final_yield)
# strip non-ascii for Windows cp1252 console
src_lines_safe = src_lines.encode("ascii", "replace").decode("ascii")
print()
print("  CropModel.get_final_yield() source:")
for line in src_lines_safe.splitlines():
    print("    " + line)

# ── 1c. Run simulation, capture raw biomass AND final_yield ──────────────────
from app.services import simulation_pipeline as pl
from app.services.simulation_service import SimulationService

_snapshots = []
orig_crop_run = pl.CropStep.run

def patch_crop_step(self, state, svc):
    orig_crop_run(self, state, svc)
    _snapshots.append({
        "day":         state.day_num,
        "stage":       state.crop_status["current_stage"],
        "total_bio":   state.crop_status["total_biomass_kg_ha"],
        "veg_bio":     state.crop_status["vegetative_biomass_kg_ha"],
        "rep_bio":     state.crop_status["reproductive_biomass_kg_ha"],
    })

pl.CropStep.run = patch_crop_step

with open("config.json") as f:
    cfg = json.load(f)
cfg["simulation_settings"]["latitude_degrees"]              = 40.0
cfg["simulation_settings"]["longitude_degrees"]             = -89.0
cfg["simulation_settings"]["initial_moisture_fraction_awc"] = 0.4
cfg["crop_model_config"]["crop_template"]                   = "corn"
cfg["nutrient_model_config"]["initial_nitrate_N_kg_ha"]     = 20.0
cfg["et0_config"]["default_method"]                         = "penman_monteith"
cfg["management_schedule"]                                  = []

svc = SimulationService(config_data=cfg, project_root=".")
result = svc.run_simulation(
    start_date=date(2025, 5, 1),
    sim_days=120,
    output_csv_path="outputs/diag_hi_tmp.csv",
)

last = _snapshots[-1]
total_biomass_from_status  = last["total_bio"]
total_biomass_from_result  = result["total_biomass_kg_ha"]
final_yield_from_result    = result["final_yield_kg_ha"]
repro_stress_days          = svc.crop_model._repro_stress_days
grainfill_stress_days      = svc.crop_model._grainfill_stress_days

# Reconstruct the HI that was applied
derived_hi = final_yield_from_result / total_biomass_from_result if total_biomass_from_result else 0.0

print()
print(HSEP)
print("  HARVEST INDEX CHAIN — Problem Field, Day 120")
print(HSEP)
print(f"  1. CropModel.total_biomass_kg_ha          = {total_biomass_from_result:>9,.1f} kg/ha")
print(f"     (from result dict 'total_biomass_kg_ha')")
print(f"     get_status()['total_biomass_kg_ha']     = {total_biomass_from_status:>9,.1f} kg/ha")
print(f"     vegetative_biomass_kg_ha               = {last['veg_bio']:>9,.1f} kg/ha")
print(f"     reproductive_biomass_kg_ha             = {last['rep_bio']:>9,.1f} kg/ha")
print()
print(f"  2. HI used in calculation")
print(f"     Template corn.growth.harvest_index      = {tmpl_hi}")
print(f"     self.harvest_index stored in CropModel  = {svc.crop_model.harvest_index}")
print(f"     get_final_yield() base hi (hardcoded)   = 0.54")
print(f"     _repro_stress_days                      = {repro_stress_days}")
print(f"     _grainfill_stress_days                  = {grainfill_stress_days}")
if repro_stress_days > 0:
    f_repro = min(1.0, repro_stress_days / 20.0)
    hi_after_repro = 0.54 * (1 - 0.35 * f_repro)
    print(f"     HI after repro penalty: 0.54*(1-0.35*{f_repro:.2f}) = {hi_after_repro:.4f}")
if grainfill_stress_days > 0:
    f_fill = min(1.0, grainfill_stress_days / 30.0)
    hi_after_fill = hi_after_repro * (1 - 0.20 * f_fill) if repro_stress_days > 0 else 0.54 * (1 - 0.20 * f_fill)
    print(f"     HI after grain-fill penalty: × (1-0.20*{f_fill:.2f}) = {hi_after_fill:.4f}")
    print(f"     HI floor = 0.42  ->  effective HI = max(0.42, above)")
print(f"     Derived HI actually applied             = {derived_hi:.4f}  (final_yield / biomass)")
print()
print(f"  3. result['final_yield_kg_ha']             = {final_yield_from_result:>9,.1f} kg/ha")
print(f"     NOTE: this IS biomass × HI (grain yield), NOT raw biomass.")
print()
print(f"  4. Calculation chain:")
print(f"     total_biomass   {total_biomass_from_result:>9,.1f} kg/ha")
print(f"     × HI            × {derived_hi:.4f}  (template value {tmpl_hi} is STORED but IGNORED)")
print(f"     = grain_yield   {final_yield_from_result:>9,.1f} kg/ha")
print(f"     ÷ 62.77         {final_yield_from_result/62.77:>9,.1f} bu/acre")
print()

# ── diagnose: does get_final_yield() use self.harvest_index? ─────────────────
uses_self_hi = "self.harvest_index" in src_lines
print(f"  VERDICT: get_final_yield() uses self.harvest_index  = {uses_self_hi}")
print(f"  It hardcodes hi=0.54. Template's harvest_index=0.50 is stored but NEVER read.")

pl.CropStep.run = orig_crop_run  # restore


# ─────────────────────────────────────────────────────────────────────────────
# Diagnostic 2 — Soil Water Buffer
# ─────────────────────────────────────────────────────────────────────────────
print()
print()
print(SEP)
print("  DIAGNOSTIC 2: Soil Water Buffer Capacity")
print(SEP)

# ── 2a. Params used ──────────────────────────────────────────────────────────
with open("config.json") as f:
    base_cfg = json.load(f)

root_zone_depth_mm = pf(base_cfg.get("simulation_inputs", {}).get("assumed_root_zone_depth_mm", 400.0), 400.0)
sp = base_cfg.get("soil_parameters", {})
fc_mm  = pf(sp.get("field_capacity_mm"))
wp_mm  = pf(sp.get("wilting_point_mm"))
sat_v  = pf(sp.get("saturation_volumetric"), 0.45)

fc_vol = fc_mm / root_zone_depth_mm
wp_vol = wp_mm / root_zone_depth_mm

# Replicate SoilModel layer geometry
l1 = 150.0
l2 = 450.0
l3 = max(0.0, root_zone_depth_mm - 600.0)
actual_total_depth = l1 + l2 + l3

# PAW per layer (mm)
paw_l1 = (fc_vol - wp_vol) * l1
paw_l2 = (fc_vol - wp_vol) * l2
paw_l3 = (fc_vol - wp_vol) * l3
paw_total = paw_l1 + paw_l2 + paw_l3

# Initial water at AWC=0.85
def init_water(depth_mm, awc_frac):
    wp_layer = wp_vol * depth_mm
    awc_layer = (fc_vol - wp_vol) * depth_mm
    return wp_layer + awc_frac * awc_layer

init_085_l1 = init_water(l1, 0.85)
init_085_l2 = init_water(l2, 0.85)
init_085_l3 = init_water(l3, 0.85) if l3 > 0 else 0.0
init_085_total = init_085_l1 + init_085_l2 + init_085_l3
init_085_above_wp = 0.85 * paw_total

init_040_above_wp = 0.40 * paw_total

print(f"\n  Config values:")
print(f"    assumed_root_zone_depth_mm  = {root_zone_depth_mm:.0f} mm  (from simulation_inputs)")
print(f"    field_capacity_mm           = {fc_mm:.1f} mm  (absolute mm in profile)")
print(f"    wilting_point_mm            = {wp_mm:.1f} mm  (absolute mm in profile)")
print(f"    saturation_volumetric       = {sat_v:.2f}")
print()
print(f"  Derived volumetric fractions (fc_mm / root_zone_depth_mm):")
print(f"    FC  = {fc_mm:.1f} / {root_zone_depth_mm:.0f} = {fc_vol:.4f}  (volumetric m3/m3)")
print(f"    WP  = {wp_mm:.1f} / {root_zone_depth_mm:.0f} = {wp_vol:.4f}  (volumetric m3/m3)")
print(f"    SAT = {sat_v:.4f}  (volumetric m3/m3)")
print()
print(f"  SoilModel layer geometry (soil_depth_mm={root_zone_depth_mm:.0f} passed):")
print(f"    L1 depth = {l1:.0f} mm  (hardcoded)")
print(f"    L2 depth = {l2:.0f} mm  (hardcoded, ignores soil_depth_mm)")
print(f"    L3 depth = max(0, {root_zone_depth_mm:.0f}-600) = {l3:.0f} mm")
print(f"    ACTUAL total soil depth = {actual_total_depth:.0f} mm  (vs requested {root_zone_depth_mm:.0f} mm)")
print()
print(f"  Plant-Available Water (PAW) = (FC - WP) x depth:")
print(f"    L1 PAW = ({fc_vol:.4f} - {wp_vol:.4f}) x {l1:.0f} = {paw_l1:.1f} mm")
print(f"    L2 PAW = ({fc_vol:.4f} - {wp_vol:.4f}) x {l2:.0f} = {paw_l2:.1f} mm")
if l3 > 0:
    print(f"    L3 PAW = ({fc_vol:.4f} - {wp_vol:.4f}) x {l3:.0f} = {paw_l3:.1f} mm")
print(f"    Total PAW                   = {paw_total:.1f} mm")
print()
expected_paw = (0.30 - 0.14) * 1400
print(f"  EXPECTED (IL silt loam, 1400 mm rooting depth):")
print(f"    (0.30-0.14) x 1400 mm       = {expected_paw:.0f} mm")
print(f"    Shortfall: {expected_paw - paw_total:.0f} mm ({100*(expected_paw-paw_total)/expected_paw:.0f}% of expected)")
print()
print(f"  Initial total water:")
print(f"    At AWC=0.85 (Well-Managed): {init_085_total:.1f} mm total | {init_085_above_wp:.1f} mm above WP")
print(f"    At AWC=0.40 (Problem Field): {init_040_above_wp:.1f} mm above WP")
print()

# ── 2b. Days to stress with peak ETc ─────────────────────────────────────────
et0_peak    = 7.10
kc_v10      = 1.05   # from template kc_per_stage.V10
kc_vt_r1    = 1.15   # from template kc_per_stage.VT/R1
etc_v10     = et0_peak * kc_v10
etc_vt_r1   = et0_peak * kc_vt_r1
p_corn      = 0.55   # FAO-56 depletion fraction for corn
raw_total   = p_corn * paw_total

avail_085   = 0.85 * paw_total
avail_040   = 0.40 * paw_total

days_to_stress_085 = avail_085 / etc_vt_r1
days_to_stress_040 = avail_040 / etc_vt_r1

print(f"  Days to stress from peak ETc (no rain):")
print(f"    ET0_peak = {et0_peak} mm/day,  Kc(V10) = {kc_v10},  ETc = {etc_v10:.2f} mm/day")
print(f"    ET0_peak = {et0_peak} mm/day,  Kc(VT/R1) = {kc_vt_r1},  ETc = {etc_vt_r1:.2f} mm/day")
print(f"    FAO-56 RAW = p × PAW = {p_corn} × {paw_total:.1f} = {raw_total:.1f} mm")
print()
print(f"    AWC=0.85: avail={avail_085:.1f}mm -> stress in {days_to_stress_085:.1f} days at ETc={etc_vt_r1:.2f}")
print(f"    AWC=0.40: avail={avail_040:.1f}mm -> stress in {days_to_stress_040:.1f} days at ETc={etc_vt_r1:.2f}")
print()

# Expected with correct PAW
avail_085_expected = 0.85 * expected_paw
days_expected = avail_085_expected / etc_vt_r1
print(f"    EXPECTED (224mm PAW): avail={avail_085_expected:.0f}mm -> {days_expected:.1f} days before stress")
print()

# ── 2c. Daily water balance days 60-80 ───────────────────────────────────────
print()
print(HSEP)
print("  Daily water balance — Problem Field, days 60-80 (June 29 – July 18)")
print(HSEP)
print(f"  {'Day':>4}  {'Date':<11} {'Precip':>7} {'ET0':>6} {'Kc':>5} {'ETc':>6} {'Drain':>7} {'fAWC':>6}  Stage")
print(HSEP)

# day_of_year is Julian (1-365); simulation day is row index + 1
rows = list(csv.DictReader(open("outputs/diag_problem.csv")))
for sim_day, r in enumerate(rows, start=1):
    if 60 <= sim_day <= 80:
        et0v = pf(r["daily_et0_mm"])
        etcv = pf(r["daily_etc_mm"])
        kc   = etcv / et0v if et0v > 0 else 0.0
        print(
            f"  {sim_day:>4}  {r['date']:<11}"
            f" {pf(r['daily_precipitation_mm']):>7.2f}"
            f" {et0v:>6.2f}"
            f" {kc:>5.2f}"
            f" {etcv:>6.2f}"
            f" {pf(r['daily_percolation_mm']):>7.2f}"
            f" {pf(r['fraction_awc']):>6.3f}"
            f"  {r['crop_growth_stage']}"
        )
print()

# Kc check: print observed Kc by stage for days 60-80
kc_vals = {}
for sim_day, r in enumerate(rows, start=1):
    if 60 <= sim_day <= 80:
        et0v = pf(r["daily_et0_mm"])
        etcv = pf(r["daily_etc_mm"])
        stage = r["crop_growth_stage"]
        if et0v > 0:
            kc = etcv / et0v
            kc_vals.setdefault(stage, []).append(kc)

print("  Kc values observed in days 60-80 by stage:")
for stage, vals in kc_vals.items():
    avg = sum(vals)/len(vals)
    print(f"    {stage}: mean Kc = {avg:.3f}  (min={min(vals):.3f}, max={max(vals):.3f}, n={len(vals)})")
