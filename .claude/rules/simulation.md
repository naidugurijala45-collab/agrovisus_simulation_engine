# Simulation Model Rules

Rules that apply whenever you touch `engine/app/models/` or `engine/app/services/`.

---

## Before Changing Any Model

1. **Read the file first.** Never propose a change to code you haven't read.
2. **Run the tests first.** Confirm the baseline is 167 passing before you start.
3. **Add a test.** Every physics change needs at least one numerical regression test.

---

## CropModel (`crop_model.py`)

- `self.harvest_index` is set from the template. **Never hardcode HI** in
  `get_final_yield()` or anywhere else.
- The APSIM N-stress floor is **0.40** at NNI ≤ 0.4. Do not lower it below 0.35.
- `_repro_stress_days` and `_grainfill_stress_days` accumulate when
  `water_stress_factor < 0.5` during reproductive/grain-fill stages. These reduce HI.
- GDD stages: `VE → V2 → V6 → V10 → VT → R1 → R3 → R6`. Stage boundaries come
  from `gdd_thresholds` in the template's `growth` section.
- RUE switches from `growth.rue.vegetative` to `growth.rue.grain_fill` at
  `growth.rue.grain_fill_stage` (template-defined). Verify this switch point when
  editing biomass logic.

## SoilModel (`soil_model.py`)

- Three layers, **proportional** to `soil_depth_mm`:
  ```
  L1 = min(300, depth * 0.25)
  L2 = min(600, depth * 0.50)
  L3 = depth - L1 - L2
  ```
- `custom_soil_params` uses volumetric fraction keys: `{"fc": θ, "wp": θ, "sat": θ}`.
  Do **not** pass mm values.
- PAW assertion: for profiles ≥ 800 mm, assert `150 < total_paw < 400`.
  If you change FC/WP defaults, verify this assertion still passes.
- `update_daily()` returns `{"actual_eta_mm": ..., "deep_percolation_mm": ..., "runoff_mm": ...}`.
  Do not discard `actual_eta_mm` — it is captured in `SoilStep` and reported in the CSV.

## NutrientModel (`nutrient_model.py`)

- N cycling order per day: mineralization → nitrification → denitrification → leaching → crop uptake.
- Q10 = 2.0 is locked. Do not change it.
- Soil temperature must come from `estimate_soil_temp_25cm()`. Do **not** pass
  `avg_temp_c` directly as `soil_temp_25cm`.
- BNF (soybean only) is suppressed at WFPS ≥ 0.90 (anaerobic). WFPS must come
  from `SoilModel.get_soil_moisture_status()["wfps"]`.
- `compute_NNI(biomass_Mg_ha, actual_N_kg_ha)` — biomass in **Mg/ha**, N in **kg/ha**.
  Unit mix-ups silently produce wrong NNI values.

## ET0Service (`et0_service.py`)

- Default method: `penman_monteith`. Falls back to `hargreaves` if solar/wind data missing.
- Always pass `rn=rn_series` to `et.pm()`, **not** `rs=rs`. Net radiation Rn is
  pre-computed by `_compute_rn()` (FAO-56 Eqs. 21, 37–39).
- `lat` must be in **radians** when passed to pyet. `location["lat"]` is in degrees —
  always convert with `math.radians()`.
- All `pd.Series` passed to pyet must have a `pd.DatetimeIndex`.

## DiseaseModel

- Disease stress factor directly reduces daily biomass in `CropStep`.
- Leaf wetness duration (LWD) must come from `WeatherStep` hourly data, not a
  constant. Check `DiseaseStep` wiring if disease severity is unexpectedly flat.

## Pipeline (`simulation_pipeline.py`)

- `DayState` is the mutable state bag. Add new daily outputs as fields here first,
  then propagate through the relevant Step(s).
- Step order is strict — do not reorder without checking data dependencies.
- `estimate_soil_temp_25cm()` is a module-level function. It uses a cosine formula
  (peak at DOY 220). Do not replace with a sine formula.

---

## Numerical Targets (corn, IL, 120-day run)

| Metric | Expected range |
|---|---|
| ET₀ May 1 | 3.5 – 5.0 mm/day |
| ET₀ peak July | 6.0 – 8.5 mm/day |
| Grain yield (well-managed) | 9 – 12 t/ha (143 – 191 bu/acre) |
| PAW (1200 mm IL silt loam) | 150 – 210 mm |
| Soil T at 25 cm on May 1 | 8 – 14 °C |
