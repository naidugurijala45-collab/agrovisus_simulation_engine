"""
Regional Profile Loader

Maps US state codes to agronomic regional profiles that carry:
  - yield benchmarks
  - disease risk multipliers
  - soil defaults
  - GDD adjustments
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_PROFILES_PATH = Path(__file__).parent.parent / "data" / "regional_profiles.json"

# Module-level cache so the JSON is read only once per process
_profiles_cache: Optional[Dict[str, Any]] = None

# Canonical disease name normaliser — handles variations like
# "NCLB_Risk", "northern_corn_leaf_blight", "nclb" → "nclb"
_DISEASE_ALIASES: Dict[str, str] = {
    "nclb": "nclb",
    "northern_corn_leaf_blight": "nclb",
    "nclb_risk": "nclb",
    "gls": "gls",
    "gray_leaf_spot": "gls",
    "gls_risk": "gls",
    "common_rust": "common_rust",
    "common_rust_risk": "common_rust",
}


def _load_profiles() -> Dict[str, Any]:
    global _profiles_cache
    if _profiles_cache is None:
        with open(_PROFILES_PATH, "r", encoding="utf-8") as f:
            _profiles_cache = json.load(f)["regions"]
    return _profiles_cache


def _region_for_state(state_code: str) -> tuple[str, Dict[str, Any]]:
    """Return (region_key, region_dict) for the given state code."""
    profiles = _load_profiles()
    state_upper = state_code.upper().strip() if state_code else ""
    for region_key, region in profiles.items():
        if region_key == "default":
            continue
        if state_upper in region.get("states", []):
            return region_key, region
    return "default", profiles["default"]


def load_profile(state_code: str) -> Dict[str, Any]:
    """
    Return the full regional profile dict for *state_code*.
    Falls back to "default" region if the state is unmapped.
    """
    region_key, region = _region_for_state(state_code)
    logger.info(
        "Regional profile loaded: %s (%s)",
        region_key,
        state_code.upper() if state_code else "unknown",
    )
    return {"region_key": region_key, **region}


def get_disease_multiplier(state_code: str, disease_id: str) -> float:
    """
    Return the risk multiplier (float) for *disease_id* in *state_code*'s region.

    disease_id is normalised to a canonical key via _DISEASE_ALIASES.
    Returns 1.0 if the disease is not found in the profile.
    """
    _, region = _region_for_state(state_code)
    canonical = _DISEASE_ALIASES.get(disease_id.lower().replace("-", "_"), disease_id.lower())
    multiplier = region.get("disease_risk_multipliers", {}).get(canonical, 1.0)
    return float(multiplier)


def get_soil_defaults(state_code: str) -> Dict[str, Any]:
    """Return the soil_defaults dict for *state_code*'s region."""
    _, region = _region_for_state(state_code)
    return dict(region.get("soil_defaults", {}))


def get_yield_benchmark(state_code: str, crop_type: str = "corn") -> float:
    """
    Return the yield benchmark in bu/acre for *state_code*.

    Currently only corn benchmarks are regionalised; other crops fall back
    to the default region value.
    """
    _, region = _region_for_state(state_code)
    # Regional benchmarks are corn-specific; future crops can extend this
    return float(region.get("yield_benchmark_bu_ac", 185))
