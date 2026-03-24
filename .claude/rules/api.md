# API Rules — FastAPI / Render

Rules that apply when touching `backend/` or adding new endpoints.

---

## General FastAPI Conventions

- All routers live in `backend/routers/`. One file per domain.
- Register routers in `backend/main.py` with an explicit `prefix` and `tags`.
- Response models live inline or in `backend/models/` — not in routers.
- Use `HTTPException` for all client errors (4xx). Do not return bare dicts for errors.
- Log with `logging.getLogger(__name__)`, never `print()`.

## Simulation Endpoint

File: `backend/routers/simulation.py`

Key function: `_build_config(request) -> dict`
- Loads root `config.json` as the base.
- Merges request fields on top.
- Returns the merged dict to `SimulationService`.
- Do not add logic to `SimulationService.__init__` that belongs here.

Default start date: `date(2025, 5, 1)` — change here if the demo date shifts.

ROI is computed at this layer (not in the engine) because it needs
`field_acres` and commodity price from the request.

## /ingest Endpoint (planned — Jetson Nano)

When implementing, follow this schema exactly:

```python
class IngestPayload(BaseModel):
    field_id: str
    timestamp: datetime
    soil_moisture: float        # volumetric fraction 0-1
    soil_temp_c: float          # measured at sensor depth
    canopy_temp_c: float        # optional, use None if not available
    rainfall_mm: float          # since last reading

class IngestResponse(BaseModel):
    field_id: str
    accepted: bool
    next_expected_s: int        # seconds until next expected reading
```

Auth: check `X-Device-Key` header against a device registry.
Do not accept unauthenticated ingest payloads.

## CORS

Configured in `backend/main.py`:
```python
allow_origin_regex=r"https?://localhost:.*|https://.*\.vercel\.app"
```

Do not widen to `allow_origins=["*"]` — this breaks production security.
For a new staging URL, extend the regex pattern.

## Render Deployment

- Entry point: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- `sys.path.insert(0, str(PROJECT_ROOT))` is required so `from backend...` works on Render.
- Environment variables are set in the Render dashboard, not in code.
- `engine/` is imported at runtime by inserting it into `sys.path` — keep this path insert.

## Stub Endpoints

`backend/routers/disease.py` returns **randomized** stub results.
Do not treat its confidence values as real model output.
Mark any stub endpoint with a `# STUB` comment and a TODO note.

## Error Handling

- Validation errors (bad config, missing crop) -> `422 Unprocessable Entity`
- Weather fetch failures -> fall back silently to synthetic weather, do not 500
- Simulation crashes -> catch in the router, return `500` with a structured message:
  ```json
  { "error": "simulation_failed", "detail": "<message>" }
  ```

## Versioning

Current API has no versioning prefix. When adding `/v2/` routes, do not rename
existing routes — add new ones alongside. The frontend hardcodes `/api/simulate`.
