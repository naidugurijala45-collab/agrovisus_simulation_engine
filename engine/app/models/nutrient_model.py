# AGROVISUS_SIMULATION_ENGINE/app/models/nutrient_model.py

import logging
from typing import Any, Dict, Optional

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
        bnf_config=None,
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

        # ── BNF (biological nitrogen fixation — soybean only) ─────────────────
        self._has_bnf = (bnf_config is not None) and bool(bnf_config.get("enabled", False))
        if self._has_bnf:
            self._bnf_nmax       = float(bnf_config.get("nmax_fixpot", 0.03))
            tr = bnf_config.get("temperature_response", {})
            self._bnf_t_min      = float(tr.get("t_min",       5.0))
            self._bnf_t_opt_low  = float(tr.get("t_opt_low",  20.0))
            self._bnf_t_opt_high = float(tr.get("t_opt_high", 35.0))
            self._bnf_t_max      = float(tr.get("t_max",      44.0))
            wr = bnf_config.get("water_response", {})
            self._bnf_wf_lower     = float(wr.get("wf_lower",               0.2))
            self._bnf_wf_upper     = float(wr.get("wf_upper",               0.8))
            self._bnf_flooded_wfps = float(wr.get("flooded_threshold_wfps", 0.90))
            sr = bnf_config.get("stage_response", {})
            self._bnf_nds_min      = float(sr.get("nds_min",      0.1))
            self._bnf_nds_opt_low  = float(sr.get("nds_opt_low",  0.3))
            self._bnf_nds_opt_high = float(sr.get("nds_opt_high", 0.7))
            self._bnf_nds_max      = float(sr.get("nds_max",      0.9))
            mn = bnf_config.get("mineral_n_inhibition", {})
            thresholds = mn.get("no3_kg_ha_thresholds", {"low": 50, "moderate": 100})
            fractions  = mn.get("inhibition_fractions",  {"low": 0.9, "moderate": 0.55, "high": 0.2})
            self._bnf_no3_low      = float(thresholds.get("low",      50.0))
            self._bnf_no3_moderate = float(thresholds.get("moderate", 100.0))
            self._bnf_f_low        = float(fractions.get("low",      0.9))
            self._bnf_f_moderate   = float(fractions.get("moderate", 0.55))
            self._bnf_f_high       = float(fractions.get("high",     0.2))
        self._last_bnf_kg_ha = 0.0

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

    # ── BNF response functions ─────────────────────────────────────────────────

    def _bnf_f_temperature(self, t_soil: float) -> float:
        """Trapezoidal temperature response (0–1) for nodule activity."""
        if t_soil <= self._bnf_t_min or t_soil >= self._bnf_t_max:
            return 0.0
        if t_soil <= self._bnf_t_opt_low:
            return (t_soil - self._bnf_t_min) / (self._bnf_t_opt_low - self._bnf_t_min)
        if t_soil <= self._bnf_t_opt_high:
            return 1.0
        return (self._bnf_t_max - t_soil) / (self._bnf_t_max - self._bnf_t_opt_high)

    def _bnf_f_water(self, wf: float, wfps: Optional[float] = None) -> float:
        """Water response: drought floor at wf_lower, flood shutdown at wfps threshold."""
        if wfps is not None and wfps >= self._bnf_flooded_wfps:
            return 0.0  # anaerobic — kills nodules
        if wf <= self._bnf_wf_lower:
            return 0.0
        if wf >= self._bnf_wf_upper:
            return 1.0
        return (wf - self._bnf_wf_lower) / (self._bnf_wf_upper - self._bnf_wf_lower)

    def _bnf_f_stage(self, nds: float) -> float:
        """NDS-based trapezoidal stage response (0–1) for BNF."""
        if nds <= self._bnf_nds_min or nds >= self._bnf_nds_max:
            return 0.0
        if nds <= self._bnf_nds_opt_low:
            return (nds - self._bnf_nds_min) / (self._bnf_nds_opt_low - self._bnf_nds_min)
        if nds <= self._bnf_nds_opt_high:
            return 1.0
        return (self._bnf_nds_max - nds) / (self._bnf_nds_max - self._bnf_nds_opt_high)

    def _bnf_f_mineral_n(self, no3_kg_ha: float) -> float:
        """Stepwise mineral-N inhibition of BNF (high soil NO₃ suppresses nodules)."""
        if no3_kg_ha <= self._bnf_no3_low:
            return self._bnf_f_low
        if no3_kg_ha <= self._bnf_no3_moderate:
            return self._bnf_f_moderate
        return self._bnf_f_high

    def compute_daily_bnf(
        self,
        root_dm_g_m2: float,
        t_soil: float,
        wf: float,
        nds: float,
        no3_kg_ha: float,
        wfps: Optional[float] = None,
    ) -> float:
        """Compute daily BNF (kg N/ha). Returns 0.0 when BNF is not enabled.

        Formula: bnf = nmax × root_dm × f_T × f_W × f_S × f_N
        Args:
            root_dm_g_m2: nodule-bearing fine root DM (g/m²)
            t_soil:       soil temperature at 25 cm (°C)
            wf:           fraction of available water capacity (0–1)
            nds:          normalised development stage (accumulated_gdd / max_gdd)
            no3_kg_ha:    soil NO₃-N (kg/ha) for mineral-N inhibition
            wfps:         water-filled pore space (0–1) for flood detection
        """
        if not self._has_bnf:
            self._last_bnf_kg_ha = 0.0
            return 0.0
        nfix_pot  = self._bnf_nmax * root_dm_g_m2
        f_temp    = self._bnf_f_temperature(t_soil)
        f_water   = self._bnf_f_water(wf, wfps)
        f_stage   = self._bnf_f_stage(nds)
        f_mineral = self._bnf_f_mineral_n(no3_kg_ha)
        bnf = nfix_pot * f_temp * f_water * f_stage * f_mineral
        self._last_bnf_kg_ha = bnf
        logger.debug(
            "BNF: pot=%.3f, f_T=%.3f, f_W=%.3f, f_S=%.3f, f_N=%.3f → %.4f kg N/ha",
            nfix_pot, f_temp, f_water, f_stage, f_mineral, bnf,
        )
        return bnf

    def update_daily(
        self,
        crop_N_demand_kg_ha: float,
        deep_percolation_mm: float,
        avg_temp_c: float,
        soil_status: Dict[str, Any],
        root_dm_g_m2: float = 50.0,
        soil_temp_25cm: float = 22.0,
        nds: float = 0.5,
        wfps: Optional[float] = None,
    ) -> float:
        fraction_awc = soil_status.get("fraction_awc", 0.5)

        self._simulate_transformations(avg_temp_c, fraction_awc)

        # Soil N mineralization (Griffin et al., Illinois silt loam)
        # Field correction ~0.4 of lab potential rate (suboptimal moisture + aggregate protection)
        Nmin_25C = 0.4  # kg N/ha/day at 25°C, 0-15cm
        Q10 = 2.0
        mineralization_today = Nmin_25C * (Q10 ** ((avg_temp_c - 25.0) / 10.0))
        mineralization_today = max(0.0, min(2.0, mineralization_today))
        self.nitrate_N_kg_ha += mineralization_today

        self._simulate_leaching(deep_percolation_mm, soil_status)
        soil_uptake = self._simulate_uptake(crop_N_demand_kg_ha)

        # BNF: symbiotic N fixed directly by the crop — bypasses the soil N pool.
        # Increments cumulative_N_uptake_kg_ha so NNI and stress see the full supply.
        bnf_today = self.compute_daily_bnf(
            root_dm_g_m2=root_dm_g_m2,
            t_soil=soil_temp_25cm,
            wf=fraction_awc,
            nds=nds,
            no3_kg_ha=self.nitrate_N_kg_ha,
            wfps=wfps,
        )
        self.cumulative_N_uptake_kg_ha += bnf_today
        return soil_uptake + bnf_today

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
            "bnf_today_kg_ha": round(self._last_bnf_kg_ha, 4),
        }
