# app/services/reporting_service.py


class ReportingService:
    def __init__(
        self,
        data_manager,
        soil_model,
        crop_model,
        nutrient_model,
        disease_model,
        rule_evaluator,
    ):
        self.data_manager = data_manager
        self.soil_model = soil_model
        self.crop_model = crop_model
        self.nutrient_model = nutrient_model
        self.disease_model = disease_model
        self.rule_evaluator = rule_evaluator
        # Potentially store initial config for context, if needed for reporting metadata later

    def get_daily_report_data(
        self,
        current_date,
        daily_weather,
        daily_irrigation_mm,
        daily_fertilization_events,
        triggered_rules_for_day,
        actual_eta_mm: float = 0.0,
        kc_used: float = 0.0,
    ):
        """
        Collects all relevant daily data from the models for reporting.
        """
        # Ensure all models have processed for the current_date before calling this

        # NOTE: You'll need to pass 'daily_weather', 'daily_irrigation_mm',
        # 'daily_fertilization_events', and 'triggered_rules_for_day' as arguments
        # because these aren't necessarily attributes of the models directly.

        data = {
            "date": current_date.strftime("%Y-%m-%d"),
            "day_of_year": current_date.timetuple().tm_yday,
            # Weather Data (from daily_weather dict passed in)
            "daily_avg_temp_c": daily_weather.get(
                "avg_temp_c"
            ),  # Use .get() for safety
            "daily_min_temp_c": daily_weather.get("min_temp_c"),
            "daily_max_temp_c": daily_weather.get("max_temp_c"),
            "daily_precipitation_mm": daily_weather.get("precipitation_mm"),
            "daily_solar_radiation_mj_m2": daily_weather.get("solar_radiation_mj_m2"),
            "daily_avg_humidity_percent": daily_weather.get("avg_humidity_percent"),
            "daily_et0_mm": daily_weather.get("et0_mm"),
            # Crop Model Data
            "gdd_accumulated": self.crop_model.accumulated_gdd,
            "crop_growth_stage": self.crop_model.current_stage,
            "total_biomass_kg_ha": self.crop_model.total_biomass_kg_ha,
            "leaf_area_index": self.crop_model.get_lai(),
            "crop_nitrogen_demand_kg_ha": self.crop_model.get_daily_n_demand(),
            # Soil Model Data
            "fraction_awc": self.soil_model.get_soil_moisture_status()["fraction_awc"],
            "daily_etc_mm": actual_eta_mm,
            "kc_used": kc_used,
            "daily_percolation_mm": 0.0,  # Returned from update_daily, not stored
            "daily_runoff_mm": 0.0,  # Returned from update_daily, not stored
            # Management Data (passed in or queried from a management_schedule object)
            "daily_irrigation_mm": daily_irrigation_mm,
            "daily_fertilization_kg_ha": sum(
                f["amount_kg_ha"] for f in daily_fertilization_events
            )
            if daily_fertilization_events
            else 0.0,
            # You might want to break down fertilization by type, or just sum it here.
            # Nutrient Model Data
            "soil_urea_kg_ha": self.nutrient_model.urea_N_kg_ha,
            "soil_ammonium_kg_ha": self.nutrient_model.ammonium_N_kg_ha,
            "soil_nitrate_kg_ha": self.nutrient_model.nitrate_N_kg_ha,
            "crop_nitrogen_uptake_kg_ha": 0.0,  # Returned from update_daily, not stored
            "nitrogen_daily_leaching_kg_ha": 0.0,  # Returned from _simulate_leaching, not stored
            # Stress Factors
            "overall_stress_factor": min(
                self.crop_model.nitrogen_stress_factor,
                self.crop_model.water_stress_factor,
                self.disease_model.get_disease_stress_factor(),
            ),
            "water_stress_factor": self.crop_model.water_stress_factor,
            "nitrogen_stress_factor": self.crop_model.nitrogen_stress_factor,
            "disease_stress_factor": self.disease_model.get_disease_stress_factor(),
            # Disease Model Data
            "disease_severity_percent": self.disease_model.disease_severity,
            # Add other disease specific outputs like infection_potential if you want
            # RUE daily diagnostics
            "rue_base": self.crop_model._last_rue_base,
            "rue_effective": self.crop_model._last_rue_effective,
            "apar_daily": self.crop_model._last_apar_daily,
            "delta_biomass": self.crop_model._last_delta_biomass,
            # BNF daily diagnostics
            "bnf_today_kg_ha": self.nutrient_model._last_bnf_kg_ha,
            # Rule Evaluator Data
            "triggered_rules": ", ".join(triggered_rules_for_day)
            if triggered_rules_for_day
            else "",
        }
        return data
