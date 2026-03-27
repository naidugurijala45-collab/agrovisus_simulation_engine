"""
Crops Router — returns available crop templates.
"""
import json
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

ENGINE_ROOT = Path(__file__).parent.parent.parent / "engine"
sys.path.insert(0, str(ENGINE_ROOT))

router = APIRouter()

TEMPLATES_PATH = ENGINE_ROOT / "app" / "data" / "crop_templates.json"


@router.get("/templates")
def get_crop_templates():
    """Return all available crop templates with full details."""
    try:
        with open(TEMPLATES_PATH, "r") as f:
            data = json.load(f)
        templates = []
        for key, val in data.items():
            if key.startswith("_"):
                continue
            
            growth = val.get("growth", {})
            soil = val.get("soil", {})
            irrigation = val.get("irrigation", {})
            nutrients = val.get("nutrients", {})
            diseases_raw = val.get("diseases", [])
            
            # Only return disease id + name (not full config)
            diseases = [{"id": d.get("id"), "name": d.get("name")} for d in diseases_raw]
            
            templates.append({
                "id": key,
                "name": val.get("crop_name", key),
                "crop_type": val.get("crop_type"),
                "season": val.get("season"),
                "t_base_c": growth.get("t_base_c"),
                "harvest_index": growth.get("harvest_index"),
                "total_gdd_to_maturity": growth.get("total_gdd_to_maturity"),
                "gdd_thresholds": growth.get("gdd_thresholds", {}),
                "stage_labels": list(growth.get("gdd_thresholds", {}).keys()),
                "soil": {
                    "preferred_type": soil.get("preferred_type"),
                    "field_capacity_mm": soil.get("field_capacity_mm"),
                    "wilting_point_mm": soil.get("wilting_point_mm"),
                    "drainage": soil.get("drainage"),
                },
                "irrigation": {
                    "strategy": irrigation.get("strategy"),
                    "trigger_awc_fraction": irrigation.get("trigger_awc_fraction"),
                    "max_seasonal_mm": irrigation.get("max_seasonal_mm"),
                    "method": irrigation.get("method"),
                },
                "diseases": diseases,
                "total_N_kg_ha": nutrients.get("total_N_kg_ha"),
            })
        return {"templates": templates}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Crop templates file not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

