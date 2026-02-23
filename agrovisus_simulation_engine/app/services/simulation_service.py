import os
import csv
import logging
import json
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional

# Import models and services (adjusting paths for internal service usage)
from app.models.rule_evaluator import RuleEvaluator
from app.services.data_manager import DataManager
from app.services.weather_service import WeatherService
from app.services.reporting_service import ReportingService
from app.services.et0_service import ET0Service
from app.utils.leaf_wetness_model import calculate_leaf_wetness_duration
from app.models.soil_model import SoilModel
from app.models.crop_model import CropModel
from app.models.nutrient_model import NutrientModel
from app.models.disease_model import DiseaseModel
from app.utils.validators import validate_config_value, validate_positive, validate_range
from app.utils.exceptions import ConfigValidationError, ModelInitError, SimulationError
from app.utils.crop_template_loader import CropTemplateLoader

class SimulationService:
    def __init__(self, config_data: Dict[str, Any], project_root: str):
        self.config = config_data
        self.project_root = project_root
        self.logger = logging.getLogger(__name__)
        
        # Validate and load sub-configs
        self.logger.info("Validating configuration...")
        self._validate_config()
        
        self.sim_settings_conf = self.config.get("simulation_settings", {})
        self.soil_params_conf = self.config.get("soil_parameters", {})
        self.sim_inputs_conf = self.config.get("simulation_inputs", {})
        self.historical_paths_conf = self.config.get("historical_data_paths", {})
        self.crop_config_conf = self.config.get("crop_model_config", {})
        self.nutrient_config = self.config.get("nutrient_model_config", {})
        self.disease_config = self.config.get("disease_model_config", {})
        
        # Parse Management Schedule
        self.management_schedule_list = self.config.get("management_schedule", [])
        self.management_events: Dict[int, List[Dict[str, Any]]] = {}
        for event in self.management_schedule_list:
            day = event.get("day")
            if day is not None:
                if day not in self.management_events:
                    self.management_events[day] = []
                self.management_events[day].append(event)
        self.logger.info(f"Loaded {len(self.management_schedule_list)} management events from config.")

        # Initialize Models
        self._initialize_models()
    
    def _validate_config(self):
        """Validate critical configuration values."""
        try:
            # Validate simulation settings
            validate_config_value(
                self.config, "simulation_settings.latitude_degrees", float,
                default=40.0, min_val=-90.0, max_val=90.0
            )
            validate_config_value(
                self.config, "simulation_settings.elevation_m", float,
                default=100.0, min_val=-500.0, max_val=9000.0
            )
            initial_moisture = validate_config_value(
                self.config, "simulation_settings.initial_moisture_fraction_awc", float,
                default=0.5, min_val=0.0, max_val=1.0
            )
            
            # Validate critical soil parameters
            fc_mm = validate_config_value(
                self.config, "soil_parameters.field_capacity_mm", float
            )
            wp_mm = validate_config_value(
                self.config, "soil_parameters.wilting_point_mm", float
            )
            validate_positive(fc_mm, "Field capacity")
            validate_positive(wp_mm, "Wilting point")
            
            # Validate FC > WP relationship
            if fc_mm <= wp_mm:
                raise ValueError(
                    f"Field capacity ({fc_mm} mm) must be greater than "
                    f"wilting point ({wp_mm} mm)"
                )
            
            sat_vol = validate_config_value(
                self.config, "soil_parameters.saturation_volumetric", float,
                default=0.45, min_val=0.0, max_val=1.0
            )
            
            # Validate root zone depth
            root_depth = validate_config_value(
                self.config, "simulation_inputs.assumed_root_zone_depth_mm", float,
                default=400.0, min_val=50.0, max_val=5000.0
            )
            
            # Validate crop model parameters
            validate_config_value(
                self.config, "crop_model_config.t_base_c", float,
                min_val=0.0, max_val=30.0
            )
            validate_config_value(
                self.config, "crop_model_config.t_upper_c", float,
                min_val=15.0, max_val=50.0
            )
            validate_config_value(
                self.config, "crop_model_config.water_stress_threshold_awc", float,
                min_val=0.0, max_val=1.0
            )
            validate_config_value(
                self.config, "crop_model_config.radiation_use_efficiency_g_mj", float,
                min_val=0.1, max_val=10.0
            )
            validate_config_value(
                self.config, "crop_model_config.harvest_index", float,
                min_val=0.0, max_val=1.0
            )
            
            self.logger.info("Configuration validation passed")
            
        except ValueError as e:
            self.logger.error(f"Configuration validation failed: {e}")
            raise ConfigValidationError(
                f"Invalid configuration: {e}",
                suggestion="Review the config.json values flagged above."
            ) from e

    def _safe_float(self, x: Optional[Any], default: Optional[float] = None) -> Optional[float]:
        if x is None:
            return default
        try:
            return float(x)
        except (ValueError, TypeError):
            return default

    def _resolve_path(self, file_path: str) -> str:
        if os.path.isabs(file_path):
            return file_path
        return os.path.join(self.project_root, file_path)

    def _resolve_crop_config(self) -> Dict[str, Any]:
        """
        Resolve crop config: if crop_template is set, load template and
        merge user overrides on top. Otherwise use raw config as-is.
        """
        template_name = self.crop_config_conf.get("crop_template")
        
        if template_name:
            loader = CropTemplateLoader()
            self.logger.info(f"Loading crop template: '{template_name}'")
            resolved = loader.merge_with_overrides(template_name, self.crop_config_conf)
            warnings = loader.validate_crop_config(resolved)
            for w in warnings:
                self.logger.warning(f"Crop config: {w}")
            self.logger.info(
                f"Crop template '{template_name}' loaded: "
                f"{resolved.get('crop_name', template_name)}"
            )
            return resolved
        else:
            self.logger.info("No crop_template set, using raw config values")
            return dict(self.crop_config_conf)

    def _initialize_models(self):
        try:
            # Weather Service (new unified service)
            self.weather_service = WeatherService(self.config, self.project_root)

            # Data Manager (kept for backward compatibility with reporting)
            hourly_weather_path = self.historical_paths_conf.get("hourly_weather_csv", "data/hourly_weather.csv")
            resolved_weather_path = self._resolve_path(hourly_weather_path)
            self.data_manager = DataManager(resolved_weather_path)
            self.df_weather = self.data_manager.df_historical_weather

            if self.df_weather is None or self.df_weather.empty:
                self.logger.warning("Historical weather data is missing or empty. WeatherService will provide fallback data.")

            # Crop Model — resolve template + overrides
            resolved_crop_config = self._resolve_crop_config()
            self.crop_model = CropModel(
                initial_stage=resolved_crop_config.get("initial_stage"), 
                gdd_thresholds=resolved_crop_config.get("gdd_thresholds"), 
                t_base_c=self._safe_float(resolved_crop_config.get("t_base_c")), 
                t_upper_c=self._safe_float(resolved_crop_config.get("t_upper_c")), 
                n_demand_per_stage=resolved_crop_config.get("N_demand_kg_ha_per_stage"), 
                water_stress_threshold_awc=self._safe_float(resolved_crop_config.get("water_stress_threshold_awc")), 
                anaerobic_stress_threshold_awc=self._safe_float(resolved_crop_config.get("anaerobic_stress_threshold_awc")), 
                radiation_use_efficiency_g_mj=self._safe_float(resolved_crop_config.get("radiation_use_efficiency_g_mj")), 
                light_interception_per_stage=resolved_crop_config.get("light_interception_per_stage"), 
                harvest_index=self._safe_float(resolved_crop_config.get("harvest_index")),
                max_root_depth_mm=self._safe_float(resolved_crop_config.get("max_root_depth_mm"), 1200.0),
                daily_root_growth_rate_mm=self._safe_float(resolved_crop_config.get("daily_root_growth_rate_mm"), 15.0),
            )

            # Soil Model
            root_zone_depth_mm = self._safe_float(self.sim_inputs_conf.get("assumed_root_zone_depth_mm"), 400.0)
            initial_moisture_frac = self._safe_float(self.sim_settings_conf.get("initial_moisture_fraction_awc"), 0.5)
            fc_mm = self._safe_float(self.soil_params_conf.get("field_capacity_mm"))
            wp_mm = self._safe_float(self.soil_params_conf.get("wilting_point_mm"))
            sat_vol = self._safe_float(self.soil_params_conf.get("saturation_volumetric"), 0.45)
            
            if fc_mm is None or wp_mm is None: 
                raise ValueError("Config must include 'field_capacity_mm' and 'wilting_point_mm'.")
                
            custom_soil_params = {
                "fc": fc_mm / root_zone_depth_mm, 
                "wp": wp_mm / root_zone_depth_mm, 
                "sat": sat_vol, 
                "description": self.soil_params_conf.get("type", "Custom Soil")
            }
            self.soil_model = SoilModel(
                soil_type_name=self.soil_params_conf.get("type", "Custom"), 
                soil_depth_mm=root_zone_depth_mm, 
                initial_moisture_fraction_awc=initial_moisture_frac, 
                custom_soil_params=custom_soil_params
            )

            # Nutrient Model
            self.nutrient_model = NutrientModel(
                initial_nitrate_N_kg_ha=self._safe_float(self.nutrient_config.get("initial_nitrate_N_kg_ha"), 15.0), 
                initial_ammonium_N_kg_ha=self._safe_float(self.nutrient_config.get("initial_ammonium_N_kg_ha"), 5.0), 
                max_daily_urea_hydrolysis_rate=self._safe_float(self.nutrient_config.get("max_daily_urea_hydrolysis_rate"), 0.30), 
                max_daily_nitrification_rate=self._safe_float(self.nutrient_config.get("max_daily_nitrification_rate"), 0.15), 
                temp_base=self._safe_float(self.nutrient_config.get("temp_base"), 5.0), 
                temp_opt=self._safe_float(self.nutrient_config.get("temp_opt"), 25.0), 
                temp_max=self._safe_float(self.nutrient_config.get("temp_max"), 40.0)
            )

            # Disease Model
            self.disease_model = DiseaseModel(config=self.disease_config)

            # Rule Engine
            rule_path = self._resolve_path(self.config.get("rule_path", "rules.json"))
            self.rule_evaluator = RuleEvaluator(rule_file_path=rule_path)

            # Reporting Service
            self.reporting_service = ReportingService(
                self.data_manager, self.soil_model, self.crop_model, 
                self.nutrient_model, self.disease_model, self.rule_evaluator
            )
        
            # Initialize ET0 Service
            et0_config = self.config.get("et0_config", {})
            self.et0_service = ET0Service(et0_config)
            self.logger.info("SimulationService initialization complete.")

        except ConfigValidationError:
            raise  # Already a user-friendly exception
        except Exception as e:
            self.logger.critical(f"Failed to initialize models from config: {e}", exc_info=True)
            raise ModelInitError("SimulationService", str(e)) from e

    def get_available_start_dates(self):
        if self.df_weather is not None and not self.df_weather.empty:
            return sorted(list(set(self.df_weather.index.date)))
        return []

    def run_simulation(self, start_date: date, sim_days: int, output_csv_path: str):
        latitude = self._safe_float(self.sim_settings_conf.get("latitude_degrees", 40.0))
        longitude = self._safe_float(self.sim_settings_conf.get("longitude_degrees", 0.0))
        elevation = self._safe_float(self.sim_settings_conf.get("elevation_m", 100.0))
        
        sim_dates_to_process = [start_date + timedelta(days=i) for i in range(sim_days)]
        actual_sim_days_count = len(sim_dates_to_process)
        
        self.logger.info(f"Simulation will run from {start_date} for {actual_sim_days_count} day(s).")
        
        # CSV Headers - matching old run.py
        csv_headers = [
            "date", "day_of_year",
            "daily_avg_temp_c", "daily_min_temp_c", "daily_max_temp_c", "daily_precipitation_mm",
            "daily_solar_radiation_mj_m2", "daily_avg_humidity_percent", "daily_et0_mm",
            "gdd_accumulated", "crop_growth_stage", "total_biomass_kg_ha", "leaf_area_index", "crop_nitrogen_demand_kg_ha",
            "fraction_awc", "daily_etc_mm", "daily_percolation_mm", "daily_runoff_mm",
            "daily_irrigation_mm", "daily_fertilization_kg_ha",
            "soil_urea_kg_ha", "soil_ammonium_kg_ha", "soil_nitrate_kg_ha", "crop_nitrogen_uptake_kg_ha", "nitrogen_daily_leaching_kg_ha",
            "overall_stress_factor", "water_stress_factor", "nitrogen_stress_factor", "disease_stress_factor",
            "disease_severity_percent",
            "triggered_rules",
        ]

        all_triggered_rules_over_time = []
        csv_file = None
        
        try:
            csv_file = open(output_csv_path, 'w', newline='', encoding='utf-8')
            csv_writer = csv.DictWriter(csv_file, fieldnames=csv_headers)
            csv_writer.writeheader()
            self.logger.info(f"CSV output file opened: {output_csv_path}")

            for day_idx, current_simulation_date in enumerate(sim_dates_to_process):
                sim_day_number = day_idx + 1
                self.logger.info(f"--- Processing Day {sim_day_number}/{actual_sim_days_count}: {current_simulation_date.strftime('%Y-%m-%d')} ---")

                # 1. Management
                irrigation_today_mm = 0.0
                daily_fertilization_events = []
                if sim_day_number in self.management_events:
                    for event in self.management_events[sim_day_number]:
                        if event.get("type") == "irrigation":
                            amount = self._safe_float(event.get("amount_mm"), 0.0)
                            irrigation_today_mm += amount
                            self.logger.info(f"MANAGEMENT EVENT: Applying {amount:.1f} mm irrigation.")
                        elif event.get("type") == "fertilizer":
                            amount_n = self._safe_float(event.get("amount_kg_ha"), 0.0)
                            fert_type = event.get("fertilizer_type", "unknown")
                            daily_fertilization_events.append({"amount_kg_ha": amount_n, "type": fert_type})
                            self.logger.info(f"MANAGEMENT EVENT: Applying {amount_n:.1f} kg N/ha as {fert_type}.")
                            self.nutrient_model.add_fertilizer(amount_n, fert_type)

                # 2. Weather (WeatherService handles full fallback chain)
                daily_aggregated_weather = self.weather_service.get_daily_weather(
                    lat=latitude, lon=longitude,
                    target_date=current_simulation_date
                )

                precipitation_today = daily_aggregated_weather.get('total_precip_mm', 0.0)
                min_temp_numeric = daily_aggregated_weather.get('min_temp_c', 10.0)
                max_temp_numeric = daily_aggregated_weather.get('max_temp_c', 20.0)
                avg_temp_numeric = daily_aggregated_weather.get('avg_temp_c', 15.0)
                avg_humidity_numeric = daily_aggregated_weather.get('avg_humidity', 70.0)
                max_humidity_numeric = daily_aggregated_weather.get('max_humidity_percent', 85.0)
                solar_rad_today = daily_aggregated_weather.get('total_solar_rad_mj_m2', 20.0)
                wind_speed_today = daily_aggregated_weather.get('avg_wind_speed_m_s', 2.0)
                
                # Use ET0Service for calculation
                et0_today = self.et0_service.calculate_et0(
                    weather_data={
                        "t_min": min_temp_numeric,
                        "t_max": max_temp_numeric,
                        "t_avg": avg_temp_numeric,
                        "rh_avg": avg_humidity_numeric,
                        "rs_mj_m2": solar_rad_today,
                        "u2_m_s": wind_speed_today
                    },
                    location={
                        "lat": latitude,
                        "elevation_m": elevation
                    },
                    day_of_year=current_simulation_date
                )

                daily_weather = {
                    'avg_temp_c': avg_temp_numeric,
                    'min_temp_c': min_temp_numeric,
                    'max_temp_c': max_temp_numeric,
                    'precipitation_mm': precipitation_today,
                    'solar_radiation_mj_m2': solar_rad_today,
                    'avg_humidity_percent': avg_humidity_numeric,
                    'et0_mm': et0_today
                }

                # 3. Update Models
                current_crop_stage_before_update = self.crop_model.get_status()["current_stage"]
                kc_map = self.crop_config_conf.get("kc_per_stage", {})
                kc_today = kc_map.get(current_crop_stage_before_update, self.crop_config_conf.get("kc_fallback", 0.7))

                # Phase 2: Dynamic root depth passed to soil model
                crop_status_before_update = self.crop_model.get_status() # Moved up to get root_depth
                root_depth = crop_status_before_update.get('root_depth_mm', 50.0)
                
                soil_updates = self.soil_model.update_daily(
                    precipitation_mm=precipitation_today,
                    irrigation_mm=irrigation_today_mm,
                    et0_mm=et0_today,
                    crop_coefficient_kc=kc_today,
                    root_depth_mm=root_depth # NEW
                )
                
                deep_percolation_mm_today = soil_updates["deep_percolation_mm"]

                # 3. Crop Model Update
                # Note: We need 'effective' soil moisture for the plant.
                # The SoilModel.get_soil_moisture_status() returns `fraction_awc` as total profile average,
                # but technically plants only feel what's in the root zone.
                # For Phase 2, we rely on the implementation detailed in SoilModel which might need refining
                # to return 'root_zone_fraction_awc'.
                # For now, we use the `fraction_awc` returned (Total Profile), which is a simplification,
                # BUT since water extraction is layer-based, the "Total Profile" will heavily reflect where water was taken from.
                
                soil_status_dict = self.soil_model.get_soil_moisture_status()
                
                # Update Crop
                # Get L1 moisture specifically for germination/seedling stress if needed?
                # Currently crop model just takes 'fraction_awc'.
                
                crop_n_demand_today = self.crop_model.get_daily_n_demand()
                actual_n_uptake_today = self.nutrient_model.update_daily(crop_n_demand_today, deep_percolation_mm_today, avg_temp_numeric, soil_status_dict)
                
                # crop_status_before_update = self.crop_model.get_status() # Moved up
                non_disease_stress = min(crop_status_before_update['nitrogen_stress_factor'], crop_status_before_update['water_stress_factor'])

                # Disease Model
                hourly_data_df = self.data_manager.get_hourly_data_for_simulation_day(current_simulation_date)
                hourly_weather_list = hourly_data_df.to_dict('records') if hourly_data_df is not None else []
                calculated_lwd_hours = calculate_leaf_wetness_duration(hourly_weather_list) if hourly_weather_list else 0.0

                disease_weather_input = {'avg_temp_c': avg_temp_numeric}
                self.disease_model.update_daily(
                    daily_weather=disease_weather_input,
                    hourly_weather=hourly_weather_list,
                    crop_growth_stage=crop_status_before_update['current_stage'],
                    crop_lai=crop_status_before_update.get('lai', 0.0),
                    crop_non_disease_stress_factor=non_disease_stress
                )
                disease_status = self.disease_model.get_current_state()
                disease_stress_factor = disease_status['disease_stress_factor']

                self.crop_model.update_daily(min_temp_numeric, max_temp_numeric, solar_rad_today, actual_n_uptake_today, soil_status_dict, disease_stress_factor)
                crop_status = self.crop_model.get_status()
                nutrient_status = self.nutrient_model.get_status()

                self.logger.info(f"  Crop Status: Stage='{crop_status['current_stage']}', GDD={crop_status['accumulated_gdd']:.1f}, Root={crop_status.get('root_depth_mm',0):.0f}mm, Veg/Rep Bio={crop_status.get('vegetative_biomass_kg_ha',0):.1f}/{crop_status.get('reproductive_biomass_kg_ha',0):.1f}, N-Stress={crop_status['nitrogen_stress_factor']:.2f}, H2O-Stress={crop_status['water_stress_factor']:.2f}")
                self.logger.info(f"  Disease Status: Severity={disease_status['disease_severity']:.4f}, Stress Factor={disease_stress_factor:.2f}")
                self.logger.info(f"  Nutrient Status: Available N={nutrient_status['available_N_kg_ha']:.2f} kg/ha (Urea: {nutrient_status['urea_N_kg_ha']:.2f}, NH4: {nutrient_status['ammonium_N_kg_ha']:.2f}, NO3: {nutrient_status['nitrate_N_kg_ha']:.2f})")
                self.logger.info(f"  Soil: Total AWC={soil_status_dict['fraction_awc']:.2f} | L1(0-15cm): {soil_status_dict.get('L1_frac_awc',0):.2f} | L2(15-60cm): {soil_status_dict.get('L2_frac_awc',0):.2f} | DP={deep_percolation_mm_today:.1f}mm")

                # 4. Rules
                input_data_for_rules = {"weather": {"humidity_percent": float(avg_humidity_numeric), "current_temp_c": float(avg_temp_numeric), "leaf_wetness_hours": calculated_lwd_hours}, "soil": {**soil_status_dict}, "crop": {**crop_status}, "nutrients": {**nutrient_status}, "disease": {**disease_status}}
                triggered_rules_today = self.rule_evaluator.evaluate_rules(input_data_for_rules)
                triggered_rules_list = [r['rule_id'] for r in triggered_rules_today] if triggered_rules_today else []
                
                if triggered_rules_today:
                    for rule in triggered_rules_today:
                        self.logger.info(f"--- >>> Rule {rule.get('rule_id')} ('{rule.get('name')}') TRIGGERED <<< ---")
                    all_triggered_rules_over_time.append({"date": current_simulation_date.strftime('%Y-%m-%d'), "rules": triggered_rules_today})

                # 5. Reporting
                daily_report_data = self.reporting_service.get_daily_report_data(
                    current_date=current_simulation_date,
                    daily_weather=daily_weather,
                    daily_irrigation_mm=irrigation_today_mm,
                    daily_fertilization_events=daily_fertilization_events,
                    triggered_rules_for_day=triggered_rules_list
                )
                csv_writer.writerow(daily_report_data)

            self.logger.info("\n--- SIMULATION COMPLETE ---")
            final_yield = self.crop_model.get_final_yield()
            self.logger.info(f"Total Biomass Accumulated: {self.crop_model.total_biomass_kg_ha:.2f} kg/ha")
            self.logger.info(f"Predicted Final Grain Yield: {final_yield:.2f} kg/ha")

            return {
                "total_biomass_kg_ha": self.crop_model.total_biomass_kg_ha,
                "final_yield_kg_ha": final_yield,
                "triggered_rules": all_triggered_rules_over_time
            }

        finally:
            if csv_file:
                csv_file.close()
                self.logger.info(f"CSV file closed: {output_csv_path}")

