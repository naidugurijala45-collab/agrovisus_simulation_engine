# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AgroVisus is a full-stack AI crop simulation and diagnostics platform. It consists of:
- **`engine/`** — Python simulation engine (crop/soil/nutrient/disease models)
- **`backend/`** — FastAPI REST API that wraps the engine
- **`frontend/`** — React + Vite dashboard

## Development Setup

The project uses a Python virtualenv located at `engine/venv/`. All Python commands should use it.

### Backend
```bash
# From project root
engine\venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8001
```
Or use `start_backend.bat` on Windows.

### Frontend
```bash
cd frontend
npm install   # first time only
npm run dev   # http://localhost:5173
```
Or use `start_frontend.bat` on Windows.

Vite proxies all `/api` requests to `http://localhost:8001`, so both servers must run together.

### Engine standalone
```bash
cd engine
# Activate venv first
venv\Scripts\activate
python run.py                          # single simulation using config.json
python run.py -d 120                   # custom duration
python scenario_runner.py --all --days 90   # compare all crop templates
streamlit run dashboard.py             # interactive dashboard
```

## Tests

Engine tests live in `engine/tests/`. Run from the `engine/` directory:
```bash
cd engine
python -m pytest tests/                         # all tests
python -m pytest tests/test_validators.py       # single file
python -m pytest --cov=app tests/              # with coverage
```

## Linting (engine)

```bash
cd engine
ruff check app/
ruff format app/
```
Config is in `engine/ruff.toml` — rules E, F, W, I enabled.

## Integration test (requires backend running)
```bash
python test_api.py    # health check + crop templates + simulation POST
```
Note: `test_api.py` targets port 8000 but the backend runs on 8001 — update BASE url if needed.

## Architecture

### Data / request flow
1. Frontend (`frontend/src/api/client.js`) calls `/api/*` via axios
2. Vite proxy forwards to FastAPI at port 8001
3. `backend/routers/` handles requests — `simulation.py`, `crops.py`, `disease.py`
4. The simulation router instantiates `SimulationService` (from `engine/app/services/simulation_service.py`), writes a temp CSV, then parses it back into the response model
5. The engine is imported by inserting `engine/` into `sys.path` at runtime

### Engine internals (`engine/app/`)
`SimulationService` is the main orchestrator. Each day of simulation:
1. Applies management events (irrigation/fertilizer) from the schedule
2. Fetches daily weather via `WeatherService` (Open-Meteo API → file cache → CSV fallback → synthetic fallback)
3. Calculates ET₀ via `ET0Service` (Penman-Monteith or Hargreaves)
4. Updates `SoilModel` (multi-layer cascading bucket)
5. Updates `NutrientModel` (N cycling: urea → ammonium → nitrate)
6. Updates `DiseaseModel` (weather-driven pressure with leaf wetness)
7. Updates `CropModel` (GDD accumulation, biomass via RUE, stress factors)
8. Evaluates `RuleEvaluator` against combined state dict
9. Writes one row to the output CSV via `ReportingService`

### Crop templates
Pre-validated parameter sets for corn, wheat, rice, soybean, sorghum live in `engine/app/data/crop_templates.json`. Set `crop_model_config.crop_template` in config to use one. Individual keys in `crop_model_config` override the template.

### Configuration
`config.json` (project root) is the default config used by the backend. `engine/config.json` is the standalone engine default. The backend router's `_build_config()` merges the frontend request into the root `config.json` before passing it to `SimulationService`.

### Disease router
`backend/routers/disease.py` is currently a **stub** — it returns randomized results from a fixed catalog. CNN model integration is pending. Do not mistake stub confidence values for real model output.

### Frontend pages
- `/` — Landing (`Landing.jsx`)
- `/simulate` — Configure and run simulations, view Recharts charts (`Simulate.jsx`)
- `/disease` — Upload leaf image for diagnosis (`Disease.jsx`)
- `/reports` — Reports placeholder (`Reports.jsx`)

### Key config values
- Backend port: **8001**
- Frontend port: **5173**
- Default simulation start date hardcoded in `backend/routers/simulation.py`: `date(2024, 4, 15)`
- Weather cache directory: `engine/.weather_cache/` (gitignored)
