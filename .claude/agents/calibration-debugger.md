# Calibration Debugger Agent

Specialist agent for diagnosing yield, NNI, and stress-factor issues in the
AgroVisus simulation engine. Invoke when yield is outside the expected range
or when stress factors look wrong.

---

## Trigger Conditions

Use this agent when:
- Corn grain yield is outside 9-12 t/ha under well-managed conditions
- NNI stays < 0.5 throughout the season despite adequate N application
- Water stress factor is unexpectedly flat (always 1.0 or always < 0.5)
- ET0 values look wrong (< 2 mm/day in summer, or > 10 mm/day)
- Biomass accumulation stalls before maturity
- Yield gap between scenarios is < 20 or > 150 bu/acre

---

## Diagnostic Protocol

### Step 1 — Soil water buffer check
```python
# Verify PAW is physically realistic
from app.models.soil_model import SoilModel
soil = SoilModel("test", soil_depth_mm=1200.0)
paw = sum(l.awc_mm for l in soil.layers)
# Expected: 150-210 mm for IL silt loam
# If < 100: check theta_FC and theta_WP in config.json
# If using mm values as theta: divide by depth
```

### Step 2 — N initialization chain
```python
# Check what N init value was actually used
import logging
logging.basicConfig(level=logging.DEBUG)
# Re-run simulation — look for "N-init ... tier-N" debug lines
# Tier-1 override? Check nutrient_model_config in config dict
# Tier-2 template? Check crop_templates.json nutrients section
```

### Step 3 — ET0 sanity check
Run `engine/diag_et0_inputs.py` (or equivalent):
- Day 1 (May 1, 40N): expected 3.5-5.0 mm/day
- Peak July: expected 6.0-8.5 mm/day
- If 2.0 every day: ET0 is returning the fallback value
  -> Check pyet DatetimeIndex on all Series
  -> Check lat is in radians, not degrees
  -> Check `rn=` not `rs=` is passed to et.pm()

### Step 4 — NNI deep dive
```python
# Check NNI at key dates by reading the output CSV
import csv
rows = list(csv.DictReader(open("outputs/diag_wellmanaged.csv")))
for r in rows[:10]:
    print(r["date"], "NNI=", r.get("nitrogen_nutrition_index","?"),
          "NO3=", r["soil_nitrate_kg_ha"],
          "biomass=", r["total_biomass_kg_ha"])
# NNI < 0.3 at germination is normal (low biomass, denominator issue)
# NNI < 0.3 at V6 (day 25-35) with 90+ kg/ha NO3 is a bug
```

### Step 5 — Stress factor timeline
Plot or print `water_stress_factor` and `nitrogen_stress_factor` in 10-day buckets.
Run `engine/diag_scenarios.py` — it produces ASCII sparklines automatically.

Key diagnostics:
- Water stress flat at 1.0 all season with low AWC init -> soil depth too shallow (check root_zone_depth_mm in config)
- N stress flat at 0.1 all season with high NO3 -> NNI denominator exploding (biomass unit mismatch: must be Mg/ha not kg/ha)
- Both stress factors 1.0 all season but low yield -> check HI (should be 0.50 for corn, not 0.54)

---

## Common Root Causes & Fixes

| Symptom | Likely Cause | Fix |
|---|---|---|
| ET0 = 2.0 every day | pyet fallback; DatetimeIndex missing | Ensure pd.DatetimeIndex on all Series |
| ET0 too low (< 3) | lat in degrees passed to pyet | `math.radians(lat_deg)` |
| NNI = 1.5 all season | biomass in kg/ha instead of Mg/ha | Divide by 1000 before compute_NNI |
| NNI = 0.0 all season | actual_N = 0; check urea not mineralizing | Check soil_temp > 5C; Q10 path |
| Yield = biomass * 0.54 | Old hardcoded HI still in code | Read `self.harvest_index` from template |
| PAW = 78 mm | root_zone_depth_mm = 400 in config | Set to 1200 mm in config.json |
| Water stress never fires | PAW too large OR stress threshold wrong | Check water_stress_threshold_awc |
| BNF = 0 always (soybean) | WFPS path broken or not passed | Check DiseaseStep wiring in pipeline |
| Soil temp = air temp | estimate_soil_temp_25cm not called | Check NutrientStep call site |

---

## Reference Values for Corn (Illinois, May 1 start)

```
PAW (1200mm IL silt loam):   192 mm
Soil T on May 1 (25 cm):     ~11 C
ET0 Day 1:                   3.5-5.0 mm/day
ET0 peak July:               6.0-8.5 mm/day
Peak biomass (120d):         18,000-24,000 kg/ha
Grain yield (well-managed):  9,000-12,000 kg/ha (143-191 bu/acre)
Yield gap (good vs problem): 40-90 bu/acre
NNI peak (well-managed):     0.7-1.1 by July
N stress factor (well-mgd):  0.5-1.0 (improves after day-7 urea)
Water stress days (<0.9):    0-5 days (adequate PAW)
```

---

## Files to Read When Debugging

1. `engine/app/services/simulation_service.py` — `_resolve_n_initial()` (line 166)
2. `engine/app/models/nutrient_model.py` — `compute_NNI()`, `update_daily()`
3. `engine/app/models/crop_model.py` — `_nni_to_stress_factor()`, `get_final_yield()`
4. `engine/app/services/et0_service.py` — `_calculate_penman_monteith()`, `_compute_rn()`
5. `engine/app/services/simulation_pipeline.py` — `NutrientStep`, `SoilStep`
6. `engine/config.json` — `assumed_root_zone_depth_mm`, `field_capacity_mm`, `wilting_point_mm`
7. `engine/diag_scenarios.py` — run this first for a quick dual-scenario report
