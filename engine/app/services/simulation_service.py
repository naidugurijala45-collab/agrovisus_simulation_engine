import os
import csv
import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

# Import models and services (adjusting paths for internal service usage)
from app.models.rule_evaluator import RuleEvaluator
from app.services.data_manager import DataManager
from app.services.weather_service import WeatherService
from app.services.reporting_service import ReportingService
from app.services.et0_service import ET0Service
from app.services.simulation_pipeline import SimulationPipeline, DayState
from app.models.soil_model import SoilModel
from app.models.crop_model import CropModel
from app.models.nutrient_model import NutrientModel
from app.models.disease_model import DiseaseModel
from app.utils.validators import validate_config_value, validate_positive
from app.utils.exceptions import ConfigValidationError, ModelInitError
from app.utils.crop_template_loader import CropTemplateLoader
from app.services.regional_profile_loader import (
    load_profile, get_disease_multiplier, get_soil_defaults, get_yield_benchmark,
)

_CSV_HEADERS = [
    "date", "day_of_year",
    "daily_avg_temp_c", "daily_min_temp_c", "daily_max_temp_c", "daily_precipitation_mm",
    "daily_solar_radiation_mj_m2", "daily_avg_humidity_percent", "daily_et0_mm",
    "gdd_accumulated", "crop_growth_stage", "total_biomass_kg_ha", "leaf_area_index",
    "crop_nitrogen_demand_kg_ha",
    "fraction_awc", "daily_etc_mm", "daily_percolation_mm", "daily_runoff_mm",
    "daily_irrigation_mm", "daily_fertilization_kg_ha",
    "soil_urea_kg_ha", "soil_ammonium_kg_ha", "soil_nitrate_kg_ha",
    "crop_nitrogen_uptake_kg_ha", "nitrogen_daily_leaching_kg_ha",
    "overall_stress_factor", "water_stress_factor", "nitrogen_stress_factor",
    "disease_stress_factor", "disease_severity_percent",
    "triggered_rules",
]


class SimulationService:
    def __init__(self, config_data: Dict[str, Any], project_root: str, state_code: Optional[str] = None):
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

        self.state_code = (state_code or "").strip().upper() or None

        # Initialize Models
        self._initialize_models(state_code=self.state_code)
    
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

    def _resolve_n_initial(self, key: str, full_template: Optional[dict], default: float) -> float:
        """Resolve an initial soil-N value using the four-tier config priority chain.

        Priority (highest → lowest):
          1. nutrient_model_config in the passed config  — explicit programmatic override
          2. crop template ``nutrients`` section          — canonical non-request source
          3. regional profile ``soil_defaults``           — location-specific adjustment
          4. ``default`` argument                        — hardcoded fallback
        """
        # Tier 1: explicit override (e.g. set programmatically or forwarded from request)
        explicit = self.nutrient_config.get(key)
        if explicit is not None:
            self.logger.debug("N-init %s: tier-1 explicit = %s", key, explicit)
            return float(explicit)

        # Tier 2: crop template nutrients section
        if full_template is not None:
            tmpl_val = full_template.get("nutrients", {}).get(key)
            if tmpl_val is not None:
                self.logger.debug("N-init %s: tier-2 template = %s", key, tmpl_val)
                return float(tmpl_val)

        # Tier 3: regional profile soil defaults (reserved for future regional data)
        if self.regional_profile is not None:
            reg_val = self.regional_profile.get("soil_defaults", {}).get(key)
            if reg_val is not None:
                self.logger.debug("N-init %s: tier-3 regional = %s", key, reg_val)
                return float(reg_val)

        # Tier 4: hardcoded fallback
        self.logger.debug("N-init %s: tier-4 fallback = %s", key, default)
        return default

    def _resolve_crop_config(self):
        """
        Resolve crop config: if crop_template is set, load template and
        merge user overrides on top. Otherwise use raw config as-is.
        
        Returns:
            Tuple of (flattened crop config dict, full raw template or None)
        """
        template_name = self.crop_config_conf.get("crop_template")
        
        if template_name:
            loader = CropTemplateLoader()
            self.crop_template_loader = loader
            self.logger.info(f"Loading crop template: '{template_name}'")
            
            resolved = loader.merge_with_overrides(template_name, self.crop_config_conf)
            warnings = loader.validate_crop_config(resolved)
            for w in warnings:
                self.logger.warning(f"Crop config: {w}")
            
            full_template = loader.load_template(template_name)
            
            self.logger.info(
                f"Crop template '{template_name}' loaded: "
                f"{resolved.get('crop_name', template_name)}"
            )
            return resolved, full_template
        else:
            self.logger.info("No crop_template set, using raw config values")
            self.crop_template_loader = None
            return dict(self.crop_config_conf), None

    def _initialize_models(self, state_code: Optional[str] = None):
        """Instantiate all simulation models using a four-tier config priority chain.

        Config resolution priority (highest → lowest):
          1. Explicit request params   — values set in SimulationRequest / _build_config()
          2. Regional profile          — get_soil_defaults(state_code) for FC/WP when not
                                         overridden by the request
          3. Crop template             — soil.* and growth.* from crop_templates.json when
                                         the user selects a template (e.g. "corn")
          4. config.json defaults      — baseline values from the root config file

        Initial soil-N values (initial_nitrate_N_kg_ha, initial_ammonium_N_kg_ha) are
        resolved via ``_resolve_n_initial()``, which enforces this same four-tier order:
          1. nutrient_model_config key present in the passed config  (explicit override)
          2. crop template's ``nutrients`` section                    (canonical source)
          3. regional profile's ``soil_defaults``                     (location adjustment)
          4. hardcoded fallback  (40 kg NO3-N/ha, 10 kg NH4-N/ha)
        """
        try:
            # ── Regional profile ────────────────────────────────────────────
            if state_code:
                self.regional_profile = load_profile(state_code)
                self.regional_yield_benchmark_bu_ac = get_yield_benchmark(state_code)
                self.logger.info(
                    "Regional profile loaded: %s (%s)",
                    self.regional_profile.get("region_key", "unknown"),
                    state_code,
                )
            else:
                self.regional_profile = None
                self.regional_yield_benchmark_bu_ac = None
                self.logger.info("No state_code provided, using defaults.")

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
            resolved_crop_config, full_template = self._resolve_crop_config()
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
                vegetative_stages=resolved_crop_config.get("vegetative_stages"),
                reproductive_stages=resolved_crop_config.get("reproductive_stages"),
            )

            # Soil Model — priority: explicit user config > template defaults > regional defaults
            if full_template:
                soil_defaults = full_template.get("soil", {})
            else:
                soil_defaults = {}

            # Regional soil defaults fill in only when user hasn't provided explicit values
            user_provided_fc = self.soil_params_conf.get("field_capacity_mm") is not None
            user_provided_wp = self.soil_params_conf.get("wilting_point_mm") is not None
            if state_code and not user_provided_fc:
                regional_soil = get_soil_defaults(state_code)
                self.logger.info(
                    "Applying regional soil defaults for %s: FC=%s mm, WP=%s mm",
                    state_code,
                    regional_soil.get("field_capacity_mm"),
                    regional_soil.get("wilting_point_mm"),
                )
            else:
                regional_soil = {}

            root_zone_depth_mm = self._safe_float(
                self.sim_inputs_conf.get("assumed_root_zone_depth_mm")
                or soil_defaults.get("assumed_root_zone_depth_mm"),
                400.0
            )
            initial_moisture_frac = self._safe_float(self.sim_settings_conf.get("initial_moisture_fraction_awc"), 0.5)
            fc_mm = self._safe_float(
                self.soil_params_conf.get("field_capacity_mm")
                or soil_defaults.get("field_capacity_mm")
                or regional_soil.get("field_capacity_mm")
            )
            wp_mm = self._safe_float(
                self.soil_params_conf.get("wilting_point_mm")
                or soil_defaults.get("wilting_point_mm")
                or regional_soil.get("wilting_point_mm")
            )
            sat_vol = self._safe_float(
                self.soil_params_conf.get("saturation_volumetric")
                or soil_defaults.get("saturation_volumetric"),
                0.45
            )
            
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

            # Nutrient Model — initial N resolved via priority chain (see _resolve_n_initial)
            init_no3 = self._resolve_n_initial("initial_nitrate_N_kg_ha", full_template, 40.0)
            init_nh4 = self._resolve_n_initial("initial_ammonium_N_kg_ha", full_template, 10.0)
            self.logger.info("NutrientModel init: NO3=%.1f kg/ha, NH4=%.1f kg/ha", init_no3, init_nh4)
            self.nutrient_model = NutrientModel(
                initial_nitrate_N_kg_ha=init_no3,
                initial_ammonium_N_kg_ha=init_nh4,
                max_daily_urea_hydrolysis_rate=self._safe_float(self.nutrient_config.get("max_daily_urea_hydrolysis_rate"), 0.30), 
                max_daily_nitrification_rate=self._safe_float(self.nutrient_config.get("max_daily_nitrification_rate"), 0.15), 
                temp_base=self._safe_float(self.nutrient_config.get("temp_base"), 5.0), 
                temp_opt=self._safe_float(self.nutrient_config.get("temp_opt"), 25.0), 
                temp_max=self._safe_float(self.nutrient_config.get("temp_max"), 40.0)
            )

            # Disease Models — one per disease in the template
            if full_template and full_template.get("diseases"):
                template_diseases = full_template["diseases"]
                self.disease_models = [DiseaseModel(config=d) for d in template_diseases]
                self.logger.info(
                    f"Loaded {len(self.disease_models)} disease model(s): "
                    + ", ".join(d.get("name", d.get("id", "?")) for d in template_diseases)
                )
            else:
                # Fall back to single model from config
                self.disease_models = [DiseaseModel(config=self.disease_config)]
                self.logger.info("Using single disease model from config.")
            # Keep singular alias for ReportingService compatibility
            self.disease_model = self.disease_models[0]

            # Apply regional disease risk multipliers to max_severity_rate
            if state_code:
                for dm in self.disease_models:
                    disease_id = dm.config.get("id") or dm.config.get("name", "")
                    multiplier = get_disease_multiplier(state_code, disease_id)
                    if multiplier != 1.0:
                        dm.max_severity_rate = dm.max_severity_rate * multiplier
                        self.logger.info(
                            "Disease '%s': applied regional multiplier %.2f → max_severity_rate=%.4f",
                            disease_id, multiplier, dm.max_severity_rate,
                        )

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
        sim_dates = [start_date + timedelta(days=i) for i in range(sim_days)]
        self.logger.info(f"Simulation will run from {start_date} for {len(sim_dates)} day(s).")

        # Prefetch entire date range from Open-Meteo in one API call so the
        # per-day loop hits the in-memory cache instead of making 150+ requests.
        if sim_dates:
            self.weather_service.prefetch_date_range(
                latitude, longitude, sim_dates[0], sim_dates[-1]
            )

        pipeline = SimulationPipeline()
        all_rows: List[Dict[str, Any]] = []
        all_triggered: List[Dict[str, Any]] = []
        csv_file = None
        try:
            csv_file = open(output_csv_path, "w", newline="", encoding="utf-8")
            csv_writer = csv.DictWriter(csv_file, fieldnames=_CSV_HEADERS)
            csv_writer.writeheader()
            self.logger.info(f"CSV output file opened: {output_csv_path}")

            for day_idx, sim_date in enumerate(sim_dates):
                self.logger.info(
                    f"--- Processing Day {day_idx + 1}/{len(sim_dates)}:"
                    f" {sim_date.strftime('%Y-%m-%d')} ---"
                )
                state = DayState(sim_date=sim_date, day_num=day_idx + 1)
                pipeline.run_day(state, self)
                all_rows.append(state.daily_report)
                if state.triggered_rule_dicts:
                    all_triggered.append(
                        {"date": sim_date.strftime("%Y-%m-%d"), "rules": state.triggered_rule_dicts}
                    )

            csv_writer.writerows(all_rows)
            self.logger.info("\n--- SIMULATION COMPLETE ---")
            final_yield = self.crop_model.get_final_yield()
            self.logger.info(f"Total Biomass Accumulated: {self.crop_model.total_biomass_kg_ha:.2f} kg/ha")
            self.logger.info(f"Predicted Final Grain Yield: {final_yield:.2f} kg/ha")
            return {
                "total_biomass_kg_ha": self.crop_model.total_biomass_kg_ha,
                "final_yield_kg_ha": final_yield,
                "triggered_rules": all_triggered,
                "regional_yield_benchmark_bu_ac": self.regional_yield_benchmark_bu_ac,
            }
        finally:
            if csv_file:
                csv_file.close()
                self.logger.info(f"CSV file closed: {output_csv_path}")

