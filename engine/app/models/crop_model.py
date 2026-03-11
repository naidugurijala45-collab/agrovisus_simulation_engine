# AGROVISUS_SIMULATION_ENGINE/app/models/crop_model.py

import logging
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
    ):
        n_demand = self.get_daily_n_demand()
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

        potential_daily_gdd = self._calculate_daily_gdd(t_min_c, t_max_c)
        # GDD is thermal time driven by temperature only — stress never changes
        # air temperature, so no stress scalar here. Stress is applied to
        # biomass accumulation below (the single correct place).
        effective_daily_gdd = potential_daily_gdd
        self.accumulated_gdd += effective_daily_gdd
        
        # --- Root Growth ---
        # Roots grow during vegetative stages, stop at reproductive stages
        if self.current_stage in self.vegetative_stages:
            growth_today = self.daily_root_growth_rate_mm * overall_stress_factor
            self.root_depth_mm = min(self.max_root_depth_mm, self.root_depth_mm + growth_today)

        light_interception = self.light_interception_per_stage.get(
            self.current_stage, 0.1
        )
        potential_biomass_gain_g_m2 = (
            solar_rad_mj_m2 * self.rue_g_mj * light_interception
        )
        actual_biomass_gain_g_m2 = potential_biomass_gain_g_m2 * overall_stress_factor
        actual_biomass_gain_kg_ha = (
            actual_biomass_gain_g_m2 * 10
        )  # Convert g/m^2 to kg/ha
        
        # --- Biomass Partitioning ---
        # Before reproductive: all to Veg. After: all to Rep.
        if self.current_stage in self.reproductive_stages:
            # In reproductive phase, stress hits yield directly
            # We can also add a "Pollination Failure" penalty here if stress is extremely high during Flowering
            self.reproductive_biomass_kg_ha += actual_biomass_gain_kg_ha
        else:
            self.vegetative_biomass_kg_ha += actual_biomass_gain_kg_ha

        # Total is sum
        self.total_biomass_kg_ha = self.vegetative_biomass_kg_ha + self.reproductive_biomass_kg_ha

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

    def get_final_yield(self) -> float:
        """Calculates final grain yield using harvest index (DSSAT/AquaCrop approach).

        harvest_index partitions biomass into grain fraction.  Stress has
        already been applied to daily biomass accumulation; applying HI here
        does NOT double-count stress — it separates grain from total crop mass.
        """
        if self.reproductive_biomass_kg_ha > 0:
            return self.reproductive_biomass_kg_ha * self.harvest_index
        # Crop never reached flowering — scale total biomass as fallback estimate
        return self.total_biomass_kg_ha * self.harvest_index

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
        }
