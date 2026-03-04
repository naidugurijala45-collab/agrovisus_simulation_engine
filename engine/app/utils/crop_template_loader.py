"""
Crop Template Loader — loads, validates, and merges crop parameter templates.

Templates are stored in app/data/crop_templates.json (v2 format).
V2 nests growth parameters under a "growth" key and adds soil, irrigation,
nutrients, diseases, and pests sections per crop.

Usage:
    loader = CropTemplateLoader()
    config = loader.load_template("corn")
    config = loader.merge_with_overrides("corn", user_overrides)
    soil   = loader.get_soil_defaults("corn")
    diseases = loader.get_diseases("corn")
"""

import copy
import json
import logging
import os
from typing import Any, Dict, List, Optional

from app.utils.exceptions import ConfigValidationError

logger = logging.getLogger(__name__)

# Default templates file path (relative to this file)
_TEMPLATES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "crop_templates.json"
)

# Required fields every crop template's growth section must have
_REQUIRED_GROWTH_FIELDS = [
    "initial_stage",
    "t_base_c",
    "radiation_use_efficiency_g_mj",
    "harvest_index",
    "gdd_thresholds",
    "light_interception_per_stage",
    "N_demand_kg_ha_per_stage",
]

# Valid ranges for numeric crop parameters
_PARAM_RANGES = {
    "t_base_c": (-5.0, 20.0),
    "t_upper_c": (20.0, 50.0),
    "water_stress_threshold_awc": (0.1, 0.9),
    "anaerobic_stress_threshold_awc": (0.8, 1.0),
    "radiation_use_efficiency_g_mj": (0.5, 6.0),
    "harvest_index": (0.1, 0.7),
    "max_root_depth_mm": (200.0, 3000.0),
    "daily_root_growth_rate_mm": (3.0, 30.0),
}


class CropTemplateLoader:
    """Loads and validates crop parameter templates."""

    def __init__(self, templates_path: Optional[str] = None):
        self._path = templates_path or _TEMPLATES_PATH
        self._templates: Dict[str, Any] = {}
        self._load_templates()

    def _load_templates(self) -> None:
        """Load templates from JSON file."""
        resolved = os.path.abspath(self._path)
        if not os.path.exists(resolved):
            raise ConfigValidationError(
                f"Crop templates file not found: {resolved}",
                key="crop_templates",
                suggestion="Ensure app/data/crop_templates.json exists.",
            )
        try:
            with open(resolved, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigValidationError(
                f"Invalid JSON in crop templates: {e}",
                key="crop_templates",
            ) from e

        # Filter out metadata keys (start with _)
        self._templates = {
            k: v for k, v in data.items() if not k.startswith("_")
        }
        logger.info(
            f"Loaded {len(self._templates)} crop templates: "
            f"{', '.join(self._templates.keys())}"
        )

    def _get_template(self, crop_name: str) -> Dict[str, Any]:
        """Internal: get raw template by name, raises if not found."""
        key = crop_name.lower().strip()
        if key not in self._templates:
            available = ", ".join(self.list_available_crops())
            raise ConfigValidationError(
                f"Unknown crop template: '{crop_name}'",
                key="crop_model_config.crop_template",
                suggestion=f"Available templates: {available}",
            )
        return self._templates[key]

    def _flatten_growth(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """
        Flatten v2 template for CropModel compatibility.
        
        V2 templates nest growth params under "growth". This extracts them
        to the top level (alongside crop_name) so CropModel can consume
        them directly.
        """
        flat = {}
        # Copy top-level metadata
        for key in ("crop_name", "crop_type", "season"):
            if key in template:
                flat[key] = template[key]

        # Flatten growth section into top level
        growth = template.get("growth", {})
        flat.update(growth)

        return flat

    def list_available_crops(self) -> List[str]:
        """Return list of available template names."""
        return sorted(self._templates.keys())

    def load_template(self, crop_name: str) -> Dict[str, Any]:
        """
        Load a full crop template by name (v2 format with all sections).

        Returns a deep copy so callers can modify without affecting templates.

        Raises:
            ConfigValidationError: If crop_name is not found.
        """
        return copy.deepcopy(self._get_template(crop_name))

    def merge_with_overrides(
        self, crop_name: str, overrides: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Load a template, flatten growth params, and apply user overrides.

        Dict-type fields (gdd_thresholds, kc_per_stage, etc.) are merged
        key-by-key so users can override individual stages without
        re-specifying the entire dict.

        Args:
            crop_name: Template name (e.g. "corn").
            overrides: User-provided config values to apply on top.

        Returns:
            Flattened + merged config dict ready for CropModel.
        """
        raw = self.load_template(crop_name)
        base = self._flatten_growth(raw)

        # Keys to skip from overrides (not crop params)
        skip_keys = {"crop_template", "description"}

        for key, value in overrides.items():
            if key in skip_keys:
                continue
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                # Merge dicts (e.g., override specific GDD stages)
                base[key].update(value)
                logger.info(f"  Override merged into '{key}': {list(value.keys())}")
            else:
                if key in base:
                    logger.info(f"  Override: {key} = {value} (was {base[key]})")
                base[key] = value

        return base

    # ----------------------------------------------------------------
    # New v2 accessor methods
    # ----------------------------------------------------------------

    def get_soil_defaults(self, crop_name: str) -> Dict[str, Any]:
        """
        Return the soil section for a given crop.

        Returns an empty dict if the crop has no soil defaults.
        """
        template = self.load_template(crop_name)
        return template.get("soil", {})

    def get_diseases(self, crop_name: str) -> List[Dict[str, Any]]:
        """
        Return the diseases array for a given crop.

        Each disease dict contains id, name, pathogen, climate thresholds,
        susceptibility_by_stage, yield_loss, and management info.
        """
        template = self.load_template(crop_name)
        return template.get("diseases", [])

    def get_irrigation_strategy(self, crop_name: str) -> Dict[str, Any]:
        """
        Return the irrigation section for a given crop.

        Includes strategy type, trigger thresholds, amounts, critical stages.
        """
        template = self.load_template(crop_name)
        return template.get("irrigation", {})

    def get_nutrient_schedule(self, crop_name: str) -> Dict[str, Any]:
        """
        Return the nutrients section for a given crop.

        Includes total N/P/K, initial soil N, and application schedule.
        """
        template = self.load_template(crop_name)
        return template.get("nutrients", {})

    # ----------------------------------------------------------------
    # Validation
    # ----------------------------------------------------------------

    def validate_crop_config(self, config: Dict[str, Any]) -> List[str]:
        """
        Validate a (flattened) crop config dict against physical constraints.

        Returns:
            List of warning messages (empty if all valid).

        Raises:
            ConfigValidationError: If critical validation fails.
        """
        errors = []
        warnings = []

        # Check required fields
        for field in _REQUIRED_GROWTH_FIELDS:
            if field not in config:
                errors.append(f"Missing required field: '{field}'")

        if errors:
            raise ConfigValidationError(
                f"Crop config validation failed:\n  " + "\n  ".join(errors),
                key="crop_model_config",
                suggestion="Check crop_templates.json or config.json for missing fields.",
            )

        # Range checks
        for param, (lo, hi) in _PARAM_RANGES.items():
            if param in config:
                val = config[param]
                if val is not None and not (lo <= val <= hi):
                    warnings.append(
                        f"{param}={val} outside expected range [{lo}, {hi}]"
                    )

        # GDD thresholds should be monotonically increasing
        gdd = config.get("gdd_thresholds", {})
        if gdd:
            values = list(gdd.values())
            for i in range(1, len(values)):
                if values[i] <= values[i - 1]:
                    stage_names = list(gdd.keys())
                    warnings.append(
                        f"GDD thresholds not increasing: "
                        f"{stage_names[i-1]}={values[i-1]} >= "
                        f"{stage_names[i]}={values[i]}"
                    )

        # Initial stage must be in gdd_thresholds
        initial = config.get("initial_stage")
        if initial and initial not in gdd:
            errors.append(
                f"initial_stage '{initial}' not found in gdd_thresholds"
            )

        # Consistent stage sets
        stage_keys = set(gdd.keys()) if gdd else set()
        for field in ["kc_per_stage", "light_interception_per_stage", "N_demand_kg_ha_per_stage"]:
            if field in config:
                field_keys = set(config[field].keys())
                missing = stage_keys - field_keys
                if missing:
                    warnings.append(
                        f"{field} missing stages: {missing}"
                    )

        if errors:
            raise ConfigValidationError(
                f"Crop config validation failed:\n  " + "\n  ".join(errors),
                key="crop_model_config",
            )

        for w in warnings:
            logger.warning(f"Crop config warning: {w}")

        return warnings
