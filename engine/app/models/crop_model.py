# AGROVISUS_SIMULATION_ENGINE/app/models/crop_model.py

import logging
import math
from typing import Any, Dict, List, Optional, Set

from app.utils.exceptions import ConfigValidationError

logger = logging.getLogger(__name__)


class CropModel:
    def __init__(
        self,
        initial_stage: str,
        gdd_thresholds: Dict[str, float],
        t_base_c: float,
        n_demand_per_stage: Dict[str, float],
        water_stress_threshold_awc: float,
        anaerobic_stress_threshold_awc: float,
        radiation_use_efficiency_g_mj: float,
        light_interception_per_stage: Dict[str, float],
        harvest_index: float,
        t_upper_c: Optional[float] = None,
        current_gdd_accumulation: float = 0.0,
        max_root_depth_mm: float = 1200.0,
        daily_root_growth_rate_mm: float = 15.0,
        vegetative_stages: Optional[List[str]] = None,
        reproductive_stages: Optional[List[str]] = None,
        rue_config: Optional[Dict[str, Any]] = None,
    ):
        # ── Validate inputs ─────────────────────────────────
        if not gdd_thresholds:
            raise ConfigValidationError(
                "gdd_thresholds cannot be empty",
                key="crop_model_config.gdd_thresholds",
            )
        if initial_stage not in gdd_thresholds:
            raise ConfigValidationError(
                f"initial_stage '{initial_stage}' not in gdd_thresholds",
                key="crop_model_config.initial_stage",
                suggestion=f"Available stages: {list(gdd_thresholds.keys())}",
            )
        if radiation_use_efficiency_g_mj <= 0:
            raise ConfigValidationError(
                f"radiation_use_efficiency must be positive, got {radiation_use_efficiency_g_mj}",
                key="crop_model_config.radiation_use_efficiency_g_mj",
            )
        if not (0 < harvest_index < 1):
            raise ConfigValidationError(
                f"harvest_index must be between 0 and 1, got {harvest_index}",
                key="crop_model_config.harvest_index",
            )

        self.current_stage = initial_stage
        self.gdd_thresholds = dict(
            sorted(gdd_thresholds.items(), key=lambda item: item[1])
        )
        self.n_demand_per_stage = n_demand_per_stage
        self.light_interception_per_stage = light_interception_per_stage
        self.water_stress_threshold = float(water_stress_threshold_awc)
        self.anaerobic_stress_threshold = float(anaerobic_stress_threshold_awc)
        self.rue_g_mj = float(radiation_use_efficiency_g_mj)
        self.harvest_index = float(harvest_index)
        self.t_base_c = float(t_base_c)
        self.t_upper_c = float(t_upper_c) if t_upper_c is not None else None
        self.accumulated_gdd = float(current_gdd_accumulation)
        self.stage_order = list(self.gdd_thresholds.keys())

        self.nitrogen_stress_factor = 1.0
        self.water_stress_factor = 1.0
        
        # Biomass Pools & Roots
        self.total_biomass_kg_ha = 0.0
        self.vegetative_biomass_kg_ha = 0.0
        self.reproductive_biomass_kg_ha = 0.0

        # Stress-day counters for dynamic harvest index
        self._veg_stress_days = 0
        self._repro_stress_days = 0      # VT / R1 (pollination)
        self._grainfill_stress_days = 0  # R3 (grain fill)
        
        self.root_depth_mm = 50.0
        self.max_root_depth_mm = float(max_root_depth_mm)
        self.daily_root_growth_rate_mm = float(daily_root_growth_rate_mm)

        # Stage classification — use template arrays or derive from stage_order
        if vegetative_stages:
            self.vegetative_stages: Set[str] = set(vegetative_stages)
        else:
            # Fallback: first half of stages are vegetative
            half = len(self.stage_order) // 2
            self.vegetative_stages = set(self.stage_order[:half])
        if reproductive_stages:
            self.reproductive_stages: Set[str] = set(reproductive_stages)
        else:
            # Fallback: stages named Flowering, GrainFilling, Maturation
            self.reproductive_stages = {"Flowering", "GrainFilling", "Maturation"}

        # ── RUE (Beer-Lambert) params ───────────────────────────────────────
        _default_stress = {
            "water_moderate": 0.85, "water_severe": 0.60,
            "n_moderate": 0.80, "n_severe": 0.65,
        }
        self._has_rue_config = rue_config is not None
        if rue_config:
            self.rue_veg         = float(rue_config["vegetative"])
            self.rue_grain_fill  = float(rue_config["grain_fill"])
            self.k_ext           = float(rue_config.get("k_extinction", 0.45))
            self.rue_stress      = rue_config.get("stress", _default_stress)
            self.grain_fill_stage: Optional[str] = rue_config.get("grain_fill_stage")
        else:
            # Legacy fallback: single RUE value, no stage split
            self.rue_veg         = float(radiation_use_efficiency_g_mj)
            self.rue_grain_fill  = float(radiation_use_efficiency_g_mj)
            self.k_ext           = 0.45
            self.rue_stress      = _default_stress
            self.grain_fill_stage = None

        # Last-day RUE diagnostic outputs (populated by update_daily)
        self._last_rue_base      = self.rue_veg
        self._last_rue_effective = self.rue_veg
        self._last_apar_daily    = 0.0
        self._last_delta_biomass = 0.0

    def _calculate_daily_gdd(
        self, t_min_c: Optional[float], t_max_c: Optional[float]
    ) -> float:
        if t_min_c is None or t_max_c is None:
            return 0.0
        t_min_adj = max(t_min_c, self.t_base_c)
        t_max_adj = max(t_max_c, self.t_base_c)
        if self.t_upper_c is not None:
            t_min_adj = min(t_min_adj, self.t_upper_c)
            t_max_adj = min(t_max_adj, self.t_upper_c)
        avg_temp_for_gdd = (t_max_adj + t_min_adj) / 2.0
        return max(0.0, avg_temp_for_gdd - self.t_base_c)

    def _stage_gte(self, current: str, target: str) -> bool:
        """Return True if *current* is at or after *target* in stage_order."""
        if target not in self.stage_order or current not in self.stage_order:
            return False
        return self.stage_order.index(current) >= self.stage_order.index(target)

    def _compute_apar(self, solar_radiation_mj: float, lai: float) -> float:
        """Absorbed PAR via Beer-Lambert: APAR = I₀ · k · (1 − e^{−k · LAI})"""
        return solar_radiation_mj * self.k_ext * (1.0 - math.exp(-self.k_ext * lai))

    def _compute_rue_effective(
        self,
        stage: str,
        soil_water_factor: float,
        nni: float,
    ):
        """Return (rue_effective, rue_base) with water and N stress applied."""
        rue_base = (
            self.rue_grain_fill
            if (self.grain_fill_stage and self._stage_gte(stage, self.grain_fill_stage))
            else self.rue_veg
        )

        # Water stress multiplier (piecewise, based on fraction_awc)
        if soil_water_factor >= 0.7:
            w_factor = 1.0
        elif soil_water_factor >= 0.5:
            w_factor = self.rue_stress["water_moderate"]
        else:
            w_factor = self.rue_stress["water_severe"]

        # N stress multiplier (NNI-based)
        if nni >= 0.9:
            n_factor = 1.0
        elif nni >= 0.7:
            n_factor = self.rue_stress["n_moderate"]
        else:
            n_factor = self.rue_stress["n_severe"]

        return rue_base * w_factor * n_factor, rue_base

    def get_daily_n_demand(self) -> float:
        return self.n_demand_per_stage.get(self.current_stage, 0.2)

    def update_daily(
        self,
        t_min_c: Optional[float],
        t_max_c: Optional[float],
        solar_rad_mj_m2: float,
        actual_n_uptake_kg_ha: float,
        soil_status: Dict[str, Any],
        disease_stress_factor: float = 1.0,
        nitrogen_stress_override: Optional[float] = None,
        nni: float = 1.0,
    ):
        n_demand = self.get_daily_n_demand()
        if nitrogen_stress_override is not None:
            self.nitrogen_stress_factor = max(0.0, min(1.0, nitrogen_stress_override))
        else:
            self.nitrogen_stress_factor = (
                min(1.0, actual_n_uptake_kg_ha / n_demand) if n_demand > 0 else 1.0
            )

        fraction_awc = soil_status.get("fraction_awc", 1.0)
        drought_stress_factor = (
            max(0.0, fraction_awc / self.water_stress_threshold)
            if fraction_awc < self.water_stress_threshold
            else 1.0
        )
        waterlogging_stress_factor = (
            0.5 if fraction_awc >= self.anaerobic_stress_threshold else 1.0
        )
        self.water_stress_factor = min(
            drought_stress_factor, waterlogging_stress_factor
        )

        overall_stress_factor = min(
            self.nitrogen_stress_factor, self.water_stress_factor, disease_stress_factor
        )

        # --- GDD accumulation and stage advance ---
        # Stage must advance BEFORE biomass partitioning so that the day GDD
        # crosses a threshold the correct (new) stage is used for partitioning
        # and light-interception lookup.  GDD is driven by temperature only —
        # stress never changes air temperature, so no stress scalar here.
        self.accumulated_gdd += self._calculate_daily_gdd(t_min_c, t_max_c)

        new_stage_reached = self.current_stage
        for stage_name in self.stage_order:
            if self.accumulated_gdd >= self.gdd_thresholds[stage_name]:
                new_stage_reached = stage_name
            else:
                break

        if new_stage_reached != self.current_stage:
            logger.info(
                f"    Crop stage advanced from '{self.current_stage}' to '{new_stage_reached}' (Accumulated GDD: {self.accumulated_gdd:.1f})"
            )
            self.current_stage = new_stage_reached

        # --- Stress-day counters for dynamic harvest index ---
        # Threshold < 0.25: only count genuinely severe stress (near wilting point).
        # Moderate deficit (0.25–0.50) does not significantly reduce HI per Djaman et al.
        if self.water_stress_factor < 0.15:
            if self.current_stage in self.vegetative_stages:
                self._veg_stress_days += 1
            elif self.current_stage in {"VT", "R1"}:
                self._repro_stress_days += 1
            elif self.current_stage == "R3":
                self._grainfill_stress_days += 1

        # --- Root Growth ---
        # Roots grow during vegetative stages, stop at reproductive stages
        if self.current_stage in self.vegetative_stages:
            growth_today = self.daily_root_growth_rate_mm * overall_stress_factor
            self.root_depth_mm = min(self.max_root_depth_mm, self.root_depth_mm + growth_today)

        # ── Biomass accumulation ─────────────────────────────────────────────
        fraction_awc = soil_status.get("fraction_awc", 1.0)
        if self._has_rue_config:
            # Beer-Lambert RUE path.
            # Use tabulated light-interception as a minimum-LAI floor so the
            # canopy can bootstrap from zero initial biomass.  The inverse of
            # APAR_factor = k*(1-exp(-k*LAI)) gives LAI_floor when APAR_factor
            # equals the tabulated fraction (clamped below k so ln stays valid).
            li_stage = self.light_interception_per_stage.get(self.current_stage, 0.1)
            li_clamp  = min(li_stage, self.k_ext * 0.999)
            lai_floor = -math.log(1.0 - li_clamp / self.k_ext) / self.k_ext
            lai = max(self.get_lai(), lai_floor)
            apar = self._compute_apar(solar_rad_mj_m2, lai)
            rue_effective, rue_base = self._compute_rue_effective(
                self.current_stage, fraction_awc, nni
            )
            delta_biomass_g_m2 = rue_effective * apar * disease_stress_factor
        else:
            # Legacy path: solar × RUE × tabulated light-interception
            light_interception = self.light_interception_per_stage.get(
                self.current_stage, 0.1
            )
            potential_g_m2 = solar_rad_mj_m2 * self.rue_g_mj * light_interception
            delta_biomass_g_m2 = potential_g_m2 * overall_stress_factor
            rue_base      = self.rue_g_mj
            rue_effective = self.rue_g_mj * overall_stress_factor
            apar          = solar_rad_mj_m2 * light_interception

        actual_biomass_gain_kg_ha = delta_biomass_g_m2 * 10  # g/m² → kg/ha

        # Store for get_status() / ReportingService
        self._last_rue_base      = rue_base
        self._last_rue_effective = rue_effective
        self._last_apar_daily    = apar
        self._last_delta_biomass = delta_biomass_g_m2

        # --- Biomass Partitioning ---
        # Before reproductive stages: all to vegetative pool.
        # From VT onward: all to reproductive pool.
        if self.current_stage in self.reproductive_stages:
            self.reproductive_biomass_kg_ha += actual_biomass_gain_kg_ha
        else:
            self.vegetative_biomass_kg_ha += actual_biomass_gain_kg_ha

        self.total_biomass_kg_ha = self.vegetative_biomass_kg_ha + self.reproductive_biomass_kg_ha

    def get_final_yield(self) -> float:
        """Calculates final grain yield using a dynamic harvest index.

        Base HI = 0.54 (peer-reviewed Illinois corn average).
        HI is reduced by severe water stress (water_stress_factor < 0.5) during:
          - Pollination (VT/R1): up to -50% of HI reduction
          - Grain fill  (R3):    up to -30% of HI reduction
        HI floor = 0.30 (catastrophic stress).

        Stress has already been applied daily to biomass accumulation; HI here
        separates grain from total crop mass without double-counting stress.
        """
        hi = 0.54
        if self._repro_stress_days > 0:
            # Max −35% for full pollination failure (≥20 severe-stress days at VT/R1).
            # Djaman: rainfed HI ~0.49 vs irrigated ~0.57 → ~14% typical seasonal drop.
            f_repro = min(1.0, self._repro_stress_days / 20.0)
            hi = hi * (1 - 0.35 * f_repro)
        if self._grainfill_stress_days > 0:
            # Max −20% for full grain-fill failure (≥30 severe-stress days at R3).
            f_fill = min(1.0, self._grainfill_stress_days / 30.0)
            hi = hi * (1 - 0.20 * f_fill)
        hi = max(0.42, hi)
        return self.total_biomass_kg_ha * hi

    def get_lai(self) -> float:
        """
        Calculates Leaf Area Index (LAI) from VEGETATIVE biomass and light interception.
        """
        light_interception = self.light_interception_per_stage.get(
            self.current_stage, 0.1
        )
        # Use VEGETATIVE biomass for LAI proxy, not total (grain doesn't have leaves)
        # Fallback to total if veg is 0 (init)
        mass_for_lai = self.vegetative_biomass_kg_ha if self.vegetative_biomass_kg_ha > 0 else self.total_biomass_kg_ha
        
        lai = (mass_for_lai / 1000.0) * light_interception
        return round(max(0.0, min(lai, 8.0)), 2)  # Cap at realistic maximum LAI of 8.0

    def get_status(self) -> Dict[str, Any]:
        return {
            "current_stage": self.current_stage,
            "accumulated_gdd": round(self.accumulated_gdd, 1),
            "total_biomass_kg_ha": round(self.total_biomass_kg_ha, 2),
            "vegetative_biomass_kg_ha": round(self.vegetative_biomass_kg_ha, 2),
            "reproductive_biomass_kg_ha": round(self.reproductive_biomass_kg_ha, 2),
            "root_depth_mm": round(self.root_depth_mm, 1),
            "lai": self.get_lai(),
            "nitrogen_stress_factor": round(self.nitrogen_stress_factor, 2),
            "water_stress_factor": round(self.water_stress_factor, 2),
            "n_demand_kg_ha_per_day": self.get_daily_n_demand(),
            "repro_stress_days": self._repro_stress_days,
            "grainfill_stress_days": self._grainfill_stress_days,
            # RUE daily diagnostics
            "rue_base": round(self._last_rue_base, 4),
            "rue_effective": round(self._last_rue_effective, 4),
            "apar_daily": round(self._last_apar_daily, 4),
            "delta_biomass": round(self._last_delta_biomass, 4),
        }
