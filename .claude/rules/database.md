# Database Rules — crop_templates.json Discipline

Rules for reading, editing, and extending `engine/app/data/crop_templates.json`.

---

## The File is the Database

There is no SQL database. `crop_templates.json` is the single source of truth
for all crop parameters. Treat it with the same discipline you would a migration.

File path: `engine/app/data/crop_templates.json`
Loaded by: `engine/app/services/crop_template_loader.py`

---

## Schema — Top-Level Sections per Crop

Each crop entry has these mandatory sections:

```
crop_name         str
crop_type         str  ("cereal" | "legume" | "grain")
season            str  ("warm" | "cool" | "tropical")
growth            dict  (GDD thresholds, HI, RUE, T_base, root params, stages)
soil              dict  (preferred FC/WP, root zone depth, drainage)
irrigation        dict  (strategy, trigger AWC, max seasonal mm)
nutrients         dict  (N/P/K totals, initial soil N, application schedule)
diseases          list  (disease objects with pathogen params)
pests             list  (pest objects)
rue               dict  (vegetative, grain_fill, grain_fill_stage, k_extinction)
```

---

## Calibration Parameters Table

These values are locked for calibration stability. Changes require a
literature citation in the commit message and a new test with a numerical bound.

| Param | Corn | Wheat | Rice | Soybean | Sorghum | Reference |
|---|---|---|---|---|---|---|
| `growth.harvest_index` | 0.50 | 0.40 | 0.45 | 0.35 | 0.45 | DSSAT defaults |
| `rue.vegetative` (g/MJ) | 3.8 | 1.6 | 1.2 | 2.5 | 3.2 | Monteith 1977 |
| `rue.grain_fill` (g/MJ) | 3.8 | 1.6 | 4.5 | 2.5 | 3.2 | Spitters 1990 |
| `growth.t_base_c` | 10.0 | 0.0 | 10.0 | 10.0 | 10.0 | USDA / FAO |
| `nutrients.initial_nitrate_N_kg_ha` | 40.0 | 15.0 | 10.0 | 10.0 | 15.0 | ISWS soil survey |
| `nutrients.initial_ammonium_N_kg_ha` | 10.0 | 5.0 | 15.0 | 5.0 | 5.0 | ISWS soil survey |
| NNI coefficient a | 34.0 | — | — | — | — | Plénet & Lemaire 1999 |
| NNI exponent b | -0.37 | — | — | — | — | Plénet & Lemaire 1999 |
| Q10 (mineralization) | 2.0 | same | same | same | same | Van't Hoff |

---

## Adding a New Crop

1. Copy the `sorghum` block as a starting template.
2. Fill every mandatory section — no `null` values allowed for calibration params.
3. Add at least one disease entry with full pathogen parameters.
4. Add the crop to `CropTemplateLoader` validation if it enforces an allowed-list.
5. Run all tests: `cd engine && python -m pytest tests/test_crop_templates.py -v`
6. Add a scenario test: `python scenario_runner.py --crop <name> --days 90`

## Editing Existing Values

- **HI, RUE, T_base** — require agronomic justification + test update.
- **Initial soil N** — change only if regional calibration data supports it.
  Use `_resolve_n_initial()` tier-3 (regional profile) instead of baking
  region-specific values into the base template.
- **GDD thresholds** — do not change without verifying stage-progression tests still pass.
- **Disease params** — changing `max_severity_rate` or `initial_inoculum` affects
  the disease stress factor and therefore final yield. Rerun scenario diagnostics.

## What Must NOT Change

- The `_metadata` block at the top of the file.
- The `nutrients.initial_nitrate_N_kg_ha` and `nutrients.initial_ammonium_N_kg_ha`
  keys — these are referenced by name in `_resolve_n_initial()`.
- The `rue.grain_fill_stage` key — the pipeline reads this to switch RUE mid-season.

## Validation

`crop_template_loader.py` validates templates on load. Run:
```bash
cd engine && python -m pytest tests/test_crop_templates.py -v
```

All 17 template tests must pass after any edit.

## JSON Style

- Indent: 4 spaces.
- Floats: include the decimal point (write `10.0`, not `10`).
- Lists: one element per line for disease/pest arrays longer than 2 items.
- Do not add trailing commas (JSON spec).
