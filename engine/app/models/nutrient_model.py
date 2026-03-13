# AGROVISUS_SIMULATION_ENGINE/app/models/nutrient_model.py

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class NutrientModel:
    def __init__(
        self,
        initial_nitrate_N_kg_ha: float,
        initial_ammonium_N_kg_ha: float,
        max_daily_urea_hydrolysis_rate: float,
        max_daily_nitrification_rate: float,
        temp_base: float,
        temp_opt: float,
        temp_max: float,
    ):
        self.nitrate_N_kg_ha = float(initial_nitrate_N_kg_ha)
        self.ammonium_N_kg_ha = float(initial_ammonium_N_kg_ha)
        self.urea_N_kg_ha = 0.0

        self.max_hydrolysis_rate = max_daily_urea_hydrolysis_rate
        self.max_nitrification_rate = max_daily_nitrification_rate

        self.temp_base = temp_base
        self.temp_opt = temp_opt
        self.temp_max = temp_max

        self.cumulative_N_uptake_kg_ha = 0.0
        self._nni = 1.0

    def add_fertilizer(self, amount_N_kg_ha: float, fertilizer_type: str = "urea"):
        # ... (this method remains the same) ...
        if amount_N_kg_ha < 0:
            logger.warning("Fertilizer amount cannot be negative.")
            return
        if fertilizer_type.lower() == "urea":
            self.urea_N_kg_ha += amount_N_kg_ha
        else:
            self.ammonium_N_kg_ha += amount_N_kg_ha

    def _get_temperature_factor(self, temp_c: float) -> float:
        """Calculates a temperature factor (0-1) for microbial activity."""
        if temp_c <= self.temp_base or temp_c >= self.temp_max:
            return 0.0
        if self.temp_base < temp_c <= self.temp_opt:
            return (temp_c - self.temp_base) / (self.temp_opt - self.temp_base)
        if self.temp_opt < temp_c < self.temp_max:
            return (self.temp_max - temp_c) / (self.temp_max - self.temp_opt)
        return 0.0  # Should not be reached

    def _get_moisture_factor(self, fraction_awc: float) -> float:
        """Calculates a moisture factor (0-1) for microbial activity."""
        # Simple linear response: activity increases with moisture.
        # This is a simplification; a more advanced model might decrease the factor at saturation.
        return max(0.0, min(1.0, fraction_awc))

    def _simulate_transformations(self, temp_c: float, fraction_awc: float):
        temp_factor = self._get_temperature_factor(temp_c)
        moisture_factor = self._get_moisture_factor(fraction_awc)
        env_factor = temp_factor * moisture_factor

        hydrolysis_rate = self.max_hydrolysis_rate * env_factor
        nitrification_rate = self.max_nitrification_rate * env_factor

        hydrolyzed_N = self.urea_N_kg_ha * hydrolysis_rate
        self.urea_N_kg_ha -= hydrolyzed_N
        self.ammonium_N_kg_ha += hydrolyzed_N

        nitrified_N = self.ammonium_N_kg_ha * nitrification_rate
        self.ammonium_N_kg_ha -= nitrified_N
        self.nitrate_N_kg_ha += nitrified_N

        logger.debug(
            f"N-Transform Factors: Temp={temp_factor:.2f}, Moist={moisture_factor:.2f}, Env={env_factor:.2f}"
        )
        logger.debug(
            f"N-Transform Rates: Hydr.={hydrolysis_rate:.2f}, Nitr.={nitrification_rate:.2f}"
        )

    def _simulate_uptake(self, crop_N_demand_kg_ha: float) -> float:
        plant_available_N = self.nitrate_N_kg_ha + self.ammonium_N_kg_ha
        uptake_possible = min(plant_available_N, crop_N_demand_kg_ha)
        nitrate_uptake = min(self.nitrate_N_kg_ha, uptake_possible)
        self.nitrate_N_kg_ha -= nitrate_uptake
        remaining_demand = uptake_possible - nitrate_uptake
        ammonium_uptake = min(self.ammonium_N_kg_ha, remaining_demand)
        self.ammonium_N_kg_ha -= ammonium_uptake
        actual_uptake = nitrate_uptake + ammonium_uptake
        self.cumulative_N_uptake_kg_ha += actual_uptake
        return actual_uptake

    def _simulate_leaching(
        self, deep_percolation_mm: float, soil_status: Dict[str, Any]
    ) -> float:
        """Simulates nitrate leaching based on deep percolation."""
        if deep_percolation_mm <= 0 or self.nitrate_N_kg_ha <= 0:
            return 0.0
        current_water_mm = soil_status.get("current_water_mm", 0)
        n_concentration = (
            self.nitrate_N_kg_ha / current_water_mm if current_water_mm > 0 else 0
        )
        n_leached_kg_ha = min(
            self.nitrate_N_kg_ha, max(0, n_concentration * deep_percolation_mm)
        )
        self.nitrate_N_kg_ha -= n_leached_kg_ha
        return n_leached_kg_ha

    def update_daily(
        self,
        crop_N_demand_kg_ha: float,
        deep_percolation_mm: float,
        avg_temp_c: float,
        soil_status: Dict[str, Any],
    ) -> float:
        soil_model_instance = soil_status  # For clarity, though we just need the dict
        fraction_awc = soil_status.get("fraction_awc", 0.5)

        self._simulate_transformations(avg_temp_c, fraction_awc)

        # Soil N mineralization (Griffin et al., Illinois silt loam)
        # Field correction ~0.4 of lab potential rate (suboptimal moisture + aggregate protection)
        Nmin_25C = 0.4  # kg N/ha/day at 25°C, 0-15cm
        Q10 = 2.0
        mineralization_today = Nmin_25C * (Q10 ** ((avg_temp_c - 25.0) / 10.0))
        mineralization_today = max(0.0, min(2.0, mineralization_today))
        self.nitrate_N_kg_ha += mineralization_today

        self._simulate_leaching(deep_percolation_mm, soil_model_instance)
        actual_uptake = self._simulate_uptake(crop_N_demand_kg_ha)
        return actual_uptake

    def compute_NNI(self, biomass_Mg_ha: float, actual_N_kg_ha: float) -> float:
        """Nitrogen Nutrition Index (Plénet & Lemaire / Djaman & Irmak 2018)."""
        if biomass_Mg_ha <= 0:
            return 1.0
        # Critical N concentration (Plénet & Lemaire model)
        Nc_g_per_kg = 34.0 * (biomass_Mg_ha ** -0.37)
        Nc_kg_ha = Nc_g_per_kg * biomass_Mg_ha  # convert to kg N/ha
        if Nc_kg_ha <= 0:
            return 1.0
        nni = actual_N_kg_ha / Nc_kg_ha
        return min(1.5, max(0.0, nni))

    def get_status(self) -> dict:
        return {
            "urea_N_kg_ha": round(self.urea_N_kg_ha, 2),
            "ammonium_N_kg_ha": round(self.ammonium_N_kg_ha, 2),
            "nitrate_N_kg_ha": round(self.nitrate_N_kg_ha, 2),
            "available_N_kg_ha": round(self.ammonium_N_kg_ha + self.nitrate_N_kg_ha, 2),
            "nitrogen_nutrition_index": round(self._nni, 3),
        }
