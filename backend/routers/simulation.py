"""
Simulation Router — runs crop simulations and returns time-series results.
"""
import json
import os
import sys
import tempfile
import csv
import logging
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

ENGINE_ROOT = Path(__file__).parent.parent.parent / "agrovisus_simulation_engine"
sys.path.insert(0, str(ENGINE_ROOT))

from app.services.simulation_service import SimulationService
from app.utils.exceptions import ConfigValidationError, ModelInitError, SimulationError

logger = logging.getLogger(__name__)
router = APIRouter()

DEFAULT_CONFIG_PATH = ENGINE_ROOT / "config.json"


def _load_default_config() -> Dict[str, Any]:
    with open(DEFAULT_CONFIG_PATH, "r") as f:
        return json.load(f)


# ── Request / Response models ──────────────────────────────────────────────

class ManagementEvent(BaseModel):
    day: int
    type: str  # "irrigation" or "fertilizer"
    amount_mm: Optional[float] = None
    amount_kg_ha: Optional[float] = None
    fertilizer_type: Optional[str] = "urea"


class SimulationRequest(BaseModel):
    crop_template: str = "corn"
    sim_days: int = 91
    latitude: float = 40.0
    longitude: float = -88.0
    elevation_m: float = 100.0
    management_schedule: List[ManagementEvent] = []


class DailyDataPoint(BaseModel):
    day: int
    date: str
    crop_stage: str
    biomass_kg_ha: float
    yield_kg_ha: float
    soil_moisture: float
    disease_severity: float
    water_stress: float
    nitrogen_stress: float
    irrigation_mm: float
    precipitation_mm: float
    avg_temp_c: float


class SimulationResult(BaseModel):
    total_biomass_kg_ha: float
    final_yield_kg_ha: float
    total_irrigation_mm: float
    total_precipitation_mm: float
    max_disease_severity: float
    daily_data: List[DailyDataPoint]
    triggered_rules: List[Dict[str, Any]]


# ── Helpers ────────────────────────────────────────────────────────────────

def _build_config(req: SimulationRequest) -> Dict[str, Any]:
    cfg = _load_default_config()
    cfg["simulation_settings"]["latitude_degrees"] = req.latitude
    cfg["simulation_settings"]["longitude_degrees"] = req.longitude
    cfg["simulation_settings"]["elevation_m"] = req.elevation_m
    cfg["crop_model_config"]["crop_template"] = req.crop_template

    # Build management schedule
    if req.management_schedule:
        events = []
        for e in req.management_schedule:
            ev: Dict[str, Any] = {"day": e.day, "type": e.type}
            if e.type == "irrigation":
                ev["amount_mm"] = e.amount_mm or 0.0
            elif e.type == "fertilizer":
                ev["amount_kg_ha"] = e.amount_kg_ha or 0.0
                ev["fertilizer_type"] = e.fertilizer_type or "urea"
            events.append(ev)
        cfg["management_schedule"] = events

    return cfg


def _parse_csv(csv_path: str) -> List[DailyDataPoint]:
    points = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            def g(k, default=0.0):
                try:
                    return float(row.get(k, default) or default)
                except (ValueError, TypeError):
                    return default

            points.append(DailyDataPoint(
                day=idx,
                date=row.get("date", ""),
                crop_stage=row.get("crop_growth_stage", "unknown"),
                biomass_kg_ha=g("total_biomass_kg_ha"),
                yield_kg_ha=g("total_biomass_kg_ha") * 0.5,  # approx until harvest
                soil_moisture=g("fraction_awc"),
                disease_severity=g("disease_severity_percent"),
                water_stress=g("water_stress_factor"),
                nitrogen_stress=g("nitrogen_stress_factor"),
                irrigation_mm=g("daily_irrigation_mm"),
                precipitation_mm=g("daily_precipitation_mm"),
                avg_temp_c=g("daily_avg_temp_c"),
            ))
    return points


# ── Routes ─────────────────────────────────────────────────────────────────

@router.post("/run", response_model=SimulationResult)
def run_simulation(req: SimulationRequest):
    """Run a full crop simulation and return daily time-series data."""
    logger.info(f"Running simulation: crop={req.crop_template}, days={req.sim_days}")
    try:
        config = _build_config(req)
        service = SimulationService(config_data=config, project_root=str(ENGINE_ROOT))

        start_date = date(2024, 4, 15)
        with tempfile.NamedTemporaryFile(mode='w', suffix=".csv", delete=False) as tmp:
            tmp_path = tmp.name

        result = service.run_simulation(
            start_date=start_date,
            sim_days=req.sim_days,
            output_csv_path=tmp_path,
        )

        daily_data = _parse_csv(tmp_path)
        os.unlink(tmp_path)

        total_irr = sum(d.irrigation_mm for d in daily_data)
        total_precip = sum(d.precipitation_mm for d in daily_data)
        max_disease = max((d.disease_severity for d in daily_data), default=0.0)

        # If crop hasn't reached reproductive stage, estimate yield from biomass
        actual_yield = result.get("final_yield_kg_ha", 0.0)
        if actual_yield == 0.0 and result.get("total_biomass_kg_ha", 0.0) > 0:
            # Use the crop template's harvest index for estimation
            harvest_index = config.get("crop_model_config", {}).get("harvest_index", 0.5)
            actual_yield = result.get("total_biomass_kg_ha", 0.0) * harvest_index

        return SimulationResult(
            total_biomass_kg_ha=result.get("total_biomass_kg_ha", 0.0),
            final_yield_kg_ha=actual_yield,
            total_irrigation_mm=total_irr,
            total_precipitation_mm=total_precip,
            max_disease_severity=max_disease,
            daily_data=daily_data,
            triggered_rules=result.get("triggered_rules", []),
        )

    except (ConfigValidationError, ModelInitError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"Simulation failed with {type(e).__name__}: {e}\n{tb}")
        print(f"\n{'='*60}\nSIMULATION ERROR:\n{tb}\n{'='*60}\n", flush=True)
        raise HTTPException(status_code=500, detail=f"Simulation error ({type(e).__name__}): {str(e)}")


@router.get("/default-config")
def get_default_config():
    """Return the default simulation configuration."""
    return _load_default_config()
