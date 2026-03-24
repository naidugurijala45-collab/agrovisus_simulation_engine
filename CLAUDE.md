# CLAUDE.md — AgroVisus

Project-level instructions for Claude Code. These rules **override** all defaults.

---

## Project Overview

AgroVisus is a full-stack AI crop simulation and diagnostics platform.

| Layer | Tech | Host |
|---|---|---|
| Simulation engine | Python 3.13, FastAPI | `engine/` |
| REST API | FastAPI + Uvicorn | Render (port 8001) |
| Frontend | React 18 + Vite + Recharts | Vercel |
| Edge node (planned) | Jetson Nano, MQTT ingest | Field deployment |

---

## Repository Layout

```
engine/          Python simulation engine (models, services, tests)
backend/         FastAPI app that wraps the engine
frontend/        React + Vite dashboard
.claude/         Claude Code configuration (rules, agents, hooks)
CLAUDE.md        <- this file
config.json      Default simulation config (backend uses this as base)
```

---

## Development Commands

```bash
# Backend (from project root)
engine\venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8001

# Frontend
cd frontend && npm run dev        # http://localhost:5173

# Engine standalone
cd engine && python run.py
cd engine && python scenario_runner.py --all --days 90

# Tests (always run from engine/)
cd engine
python -m pytest tests/                     # must pass 167 tests
python -m pytest tests/ --cov=app tests/    # with coverage

# Lint
cd engine && ruff check app/ && ruff format app/
```

---

## Supported Crops

All five crops live in `engine/app/data/crop_templates.json`.
That file is the **single canonical source** for all crop parameters.

| Crop | HI | RUE veg (g/MJ) | RUE fill (g/MJ) | T_base (°C) | NO3 init (kg/ha) |
|---|---|---|---|---|---|
| corn | 0.50 | 3.8 | 3.8 | 10.0 | 40.0 |
| wheat | 0.40 | 1.6 | 1.6 | 0.0 | 15.0 |
| rice | 0.45 | 1.2 | 4.5 | 10.0 | 10.0 |
| soybean | 0.35 | 2.5 | 2.5 | 10.0 | 10.0 |
| sorghum | 0.45 | 3.2 | 3.2 | 10.0 | 15.0 |

**Corn yield target: 9-12 t/ha** (143-191 bu/acre) under well-managed IL conditions.

---

## Core Models

### Engine pipeline (`engine/app/services/simulation_pipeline.py`)

`SimulationService` orchestrates each day through 8 ordered steps:

1. `ManagementStep` — apply irrigation/fertilizer from schedule
2. `WeatherStep` — Open-Meteo API -> file cache -> CSV fallback -> synthetic
3. `SoilStep` — multi-layer cascading bucket; captures `actual_eta_mm`
4. `NutrientStep` — N cycling + NNI + stress; uses sinusoidal soil temperature
5. `DiseaseStep` — weather-driven infection pressure + leaf wetness
6. `CropStep` — GDD accumulation, RUE biomass, stage advance, stress factors
7. `RuleEvaluationStep` — pattern-matching alert engine
8. `ReportingStep` — writes one CSV row via `ReportingService`

### Model classes

| Class | File | Responsibility |
|---|---|---|
| `CropModel` | `app/models/crop_model.py` | GDD, RUE biomass, HI, stress factors |
| `SoilModel` | `app/models/soil_model.py` | 3-layer cascading bucket, PAW, WFPS |
| `NutrientModel` | `app/models/nutrient_model.py` | Urea->NH4->NO3 cycling, NNI, BNF |
| `DiseaseModel` | `app/models/disease_model.py` | Infection potential, severity, LWD |
| `RuleEvaluator` | `app/services/rule_evaluator.py` | JSON-driven alert rule engine |

---

## Critical Physics Rules

### 1. crop_templates.json is the canonical N source
- **Never** hardcode initial N in model init or test fixtures.
- The `nutrients` section of each crop template holds:
  - `initial_nitrate_N_kg_ha` — starting soil NO3
  - `initial_ammonium_N_kg_ha` — starting soil NH4
- To override in tests, use `nutrient_model_config` in the config dict.

### 2. `_resolve_n_initial()` four-tier priority chain
Defined in `engine/app/services/simulation_service.py:166`.

```
Tier 1 (highest): nutrient_model_config explicit override (programmatic / API request)
Tier 2:           crop template nutrients section  <- canonical non-request source
Tier 3:           regional_profile soil_defaults   <- location adjustment (reserved)
Tier 4 (lowest):  hardcoded fallback (NO3=40, NH4=10)
```

Do not break this order. Adding a new N source must fit into this chain.

### 3. Plenet-Lemaire NNI
Critical N concentration curve (Plénet & Lemaire / Djaman & Irmak 2018):

```
Nc (g/kg) = 34.0 * biomass_Mg_ha^(-0.37)
NNI       = actual_N_kg_ha / (Nc_g_per_kg * biomass_Mg_ha)
NNI clamped to [0.0, 1.5]
```

Defined in `NutrientModel.compute_NNI()`. Do not change coefficients 34.0 or
-0.37 without a literature citation and a new calibration test.

### 4. APSIM floored N-stress
N stress maps NNI to stress factor using a floored linear (APSIM `nfact_photo`):

```
NNI >= 1.0          -> 1.00  (no stress)
NNI in (0.4, 1.0)  -> NNI   (linear)
NNI <= 0.4          -> 0.40  (biological floor)
```

The floor is intentional. Do not remove it or lower it below 0.35.

### 5. Q10 = 2.0 for N mineralization
```python
mineralization = Nmin_25C * (2.0 ** ((soil_temp_25cm - 25.0) / 10.0))
```

Soil temperature at 25 cm uses `estimate_soil_temp_25cm()` (cosine model, peak
DOY 220, amplitude 12 degrees C). Do not substitute raw air temperature.

### 6. Soil geometry (Illinois silt loam default)
- Root zone depth: 1200 mm
- Layers: L1 = min(300, depth*0.25), L2 = min(600, depth*0.50), L3 = remainder
- theta_FC=0.30, theta_WP=0.14, theta_sat=0.45 -> PAW = 192 mm
- PAW assertion fires for profiles >= 800 mm: must be 150-400 mm.

### 7. ET0 method
Default: Penman-Monteith (FAO-56). Net radiation Rn is computed explicitly via
`ET0Service._compute_rn()` and passed as `rn=` to pyet. Never pass `rs=`.
Hargreaves is the automatic fallback when solar/wind data are missing.

---

## Test Gate

**167 tests must pass before any PR merge.**

```bash
cd engine && python -m pytest tests/ --tb=short -q
```

- Every physics change needs at least one new numerical regression test.
- Do not pytest.skip() or xfail without a tracking issue.

---

## Backend / API Notes

- Port: **8001** (Render), **5173** (Vite dev proxy)
- CORS: `allow_origin_regex` permits `localhost:*` and `*.vercel.app`
- `backend/routers/simulation.py` — `_build_config()` merges request into root `config.json`
- `backend/routers/disease.py` — stub, returns randomized results; CNN pending
- Default simulation start date: `date(2025, 5, 1)` (set in simulation router)

---

## Jetson Nano Edge Node (planned)

A Jetson Nano field unit will publish sensor readings via MQTT to a `/ingest` endpoint.
When building this:
- Payload schema: `{ "field_id", "timestamp", "soil_moisture", "soil_temp_c", "canopy_temp_c", "rainfall_mm" }`
- The ingest handler updates simulation initial conditions, not a full replay.
- Auth: device-scoped API key in `X-Device-Key` header.

---

## What NOT to Do

- Do not change Plénet-Lemaire coefficients (34.0, -0.37) without a citation.
- Do not substitute air temperature for soil temperature at 25 cm.
- Do not hardcode HI values — always read `self.harvest_index` from the template.
- Do not pass `rs=` to pyet.pm() — use `rn=` (pre-computed net radiation).
- Do not commit `engine/outputs/*.html` or `engine/venv/`.
- Do not force-push to `main`.
