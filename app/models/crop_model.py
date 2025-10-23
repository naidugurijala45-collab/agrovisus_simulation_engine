# AGROVISUS_SIMULATION_ENGINE/app/models/crop_model.py

from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

class CropModel:
    def __init__(self,
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
                 current_gdd_accumulation: float = 0.0):
        
        self.current_stage = initial_stage
        self.gdd_thresholds = dict(sorted(gdd_thresholds.items(), key=lambda item: item[1]))
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
        self.total_biomass_kg_ha = 0.0

        if self.current_stage not in self.gdd_thresholds:
            raise ValueError(f"Initial stage '{initial_stage}' not found in gdd_thresholds.")

    def _calculate_daily_gdd(self, t_min_c: Optional[float], t_max_c: Optional[float]) -> float:
        if t_min_c is None or t_max_c is None: return 0.0
        t_min_adj = max(t_min_c, self.t_base_c)
        t_max_adj = max(t_max_c, self.t_base_c)
        if self.t_upper_c is not None:
            t_min_adj = min(t_min_adj, self.t_upper_c)
            t_max_adj = min(t_max_adj, self.t_upper_c)
        avg_temp_for_gdd = (t_max_adj + t_min_adj) / 2.0
        return max(0.0, avg_temp_for_gdd - self.t_base_c)

    def get_daily_n_demand(self) -> float:
        return self.n_demand_per_stage.get(self.current_stage, 0.2)

    def update_daily(self,
                     t_min_c: Optional[float],
                     t_max_c: Optional[float],
                     solar_rad_mj_m2: float,
                     actual_n_uptake_kg_ha: float,
                     soil_status: Dict[str, Any],
                     disease_stress_factor: float = 1.0):
        
        n_demand = self.get_daily_n_demand()
        self.nitrogen_stress_factor = min(1.0, actual_n_uptake_kg_ha / n_demand) if n_demand > 0 else 1.0

        fraction_awc = soil_status.get('fraction_awc', 1.0)
        drought_stress_factor = max(0.0, fraction_awc / self.water_stress_threshold) if fraction_awc < self.water_stress_threshold else 1.0
        waterlogging_stress_factor = 0.5 if fraction_awc >= self.anaerobic_stress_threshold else 1.0
        self.water_stress_factor = min(drought_stress_factor, waterlogging_stress_factor)
        
        overall_stress_factor = min(self.nitrogen_stress_factor, self.water_stress_factor, disease_stress_factor)

        potential_daily_gdd = self._calculate_daily_gdd(t_min_c, t_max_c)
        effective_daily_gdd = potential_daily_gdd * overall_stress_factor
        self.accumulated_gdd += effective_daily_gdd

        light_interception = self.light_interception_per_stage.get(self.current_stage, 0.1)
        potential_biomass_gain_g_m2 = solar_rad_mj_m2 * self.rue_g_mj * light_interception
        actual_biomass_gain_g_m2 = potential_biomass_gain_g_m2 * overall_stress_factor
        actual_biomass_gain_kg_ha = actual_biomass_gain_g_m2 * 10 # Convert g/m^2 to kg/ha
        self.total_biomass_kg_ha += actual_biomass_gain_kg_ha
        
        new_stage_reached = self.current_stage
        for stage_name in self.stage_order:
            if self.accumulated_gdd >= self.gdd_thresholds[stage_name]:
                new_stage_reached = stage_name
            else:
                break
        
        if new_stage_reached != self.current_stage:
            logger.info(f"    Crop stage advanced from '{self.current_stage}' to '{new_stage_reached}' (Accumulated GDD: {self.accumulated_gdd:.1f})")
            self.current_stage = new_stage_reached

    def get_final_yield(self) -> float:
        """Calculates final grain yield from total biomass and harvest index."""
        return self.total_biomass_kg_ha * self.harvest_index

    def get_lai(self) -> float:
        """
        Calculates Leaf Area Index (LAI) from biomass and light interception.
        Simple approximation: LAI is proportional to biomass and light interception efficiency.
        """
        light_interception = self.light_interception_per_stage.get(self.current_stage, 0.1)
        # Rough approximation: 1000 kg/ha biomass with full light interception ≈ LAI of 1.0
        # Scale by light interception (proxy for leaf area development)
        lai = (self.total_biomass_kg_ha / 1000.0) * light_interception
        return round(max(0.0, min(lai, 8.0)), 2)  # Cap at realistic maximum LAI of 8.0

    def get_status(self) -> Dict[str, Any]:
        return {
            "current_stage": self.current_stage,
            "accumulated_gdd": round(self.accumulated_gdd, 1),
            "total_biomass_kg_ha": round(self.total_biomass_kg_ha, 2),
            "lai": self.get_lai(),
            "nitrogen_stress_factor": round(self.nitrogen_stress_factor, 2),
            "water_stress_factor": round(self.water_stress_factor, 2),
            "n_demand_kg_ha_per_day": self.get_daily_n_demand()
        }
