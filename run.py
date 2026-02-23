# AGROVISUS_SIMULATION_ENGINE/run.py
import csv
import os
import json
from datetime import datetime, date, timedelta
import pandas as pd
import argparse
import logging
from typing import Any, Dict, List, Optional

OUTPUT_DIR = 'outputs'
DEFAULT_LOG_FILE = os.path.join(OUTPUT_DIR, 'simulation_run.log')
DEFAULT_CSV_OUTPUT = os.path.join(OUTPUT_DIR, 'simulation_output.csv')

from app.models.rule_evaluator import RuleEvaluator
from app.services.data_manager import DataManager
from app.services.reporting_service import ReportingService
from app.services.report_generator import ReportGenerator
from app.utils.leaf_wetness_model import calculate_leaf_wetness_duration
from app.models.soil_model import SoilModel
from app.utils.calculations import et0_penman_monteith, et0_hargreaves
from app.models.crop_model import CropModel
from app.models.nutrient_model import NutrientModel
from app.models.disease_model import DiseaseModel

DEFAULT_CONFIG_FILE_PATH = 'config.json'

# CSV Headers for daily report output - matches ReportingService.get_daily_report_data() keys
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


def setup_logging(log_file_path: str, verbose: bool):
    log_level = logging.DEBUG if verbose else logging.INFO
    log_dir = os.path.dirname(log_file_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file_path, mode='w'),
            logging.StreamHandler()
        ]
    )


def load_config(config_path: str) -> dict:
    try:
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        logging.info(f"Configuration loaded successfully from {config_path}")
        return config_data
    except Exception as e:
        logging.critical(f"Error loading config: {e}", exc_info=True)
        exit(1)


def parse_arguments():
    parser = argparse.ArgumentParser(description="AGROVISUS Simulation Engine")
    parser.add_argument("-c", "--config", default=DEFAULT_CONFIG_FILE_PATH, type=str, help=f"Path to JSON config file (default: {DEFAULT_CONFIG_FILE_PATH})")
    parser.add_argument("-d", "--days", type=int, help="Number of days to simulate (overrides config)")
    parser.add_argument("-o", "--output", default=DEFAULT_CSV_OUTPUT, type=str, help=f"Path for output CSV file (default: {DEFAULT_CSV_OUTPUT})")
    parser.add_argument("-s", "--start-date", type=str, default=None, help="Simulation start date in YYYY-MM-DD format.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose (DEBUG level) logging.")
    return parser.parse_args()


def _resolve_path_relative_to_project(file_path: str) -> str:
    if os.path.isabs(file_path):
        return file_path
    project_root = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(project_root, file_path)


def _safe_float(x: Optional[Any], default: Optional[float] = None) -> Optional[float]:
    try:
        return None if x is None else float(x)
    except (ValueError, TypeError):
        return default


def main(cli_args):
    # Create outputs directory early and set up logging
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    setup_logging(log_file_path=DEFAULT_LOG_FILE, verbose=cli_args.verbose)

    # Load config
    config = load_config(cli_args.config)

    # --- Config Loading ---
    sim_settings_conf = config.get("simulation_settings", {})
    soil_params_conf = config.get("soil_parameters", {})
    sim_inputs_conf = config.get("simulation_inputs", {})
    historical_paths_conf = config.get("historical_data_paths", {})
    crop_config_conf = config.get("crop_model_config", {})
    nutrient_config = config.get("nutrient_model_config", {})
    management_schedule_list = config.get("management_schedule", [])
    disease_config = config.get("disease_model_config", {})

    # Management events grouped by day index (1-based)
    management_events: Dict[int, List[Dict[str, Any]]] = {}
    for event in management_schedule_list:
        day = event.get("day")
        if day is not None:
            if day not in management_events:
                management_events[day] = []
            management_events[day].append(event)
    logging.info(f"Loaded {len(management_schedule_list)} management events from config.")

    # --- Data Manager / Weather ---
    hourly_weather_path = historical_paths_conf.get("hourly_weather_csv", "data/hourly_weather.csv")
    data_manager = DataManager(hourly_weather_path)
    df_weather = data_manager.df_historical_weather
    if df_weather is None or df_weather.empty:
        logging.warning("Historical weather data is missing or empty. Simulation will use defaults.")

    # --- Simulation Dates ---
    available_dates = sorted(list(set(df_weather.index.date))) if df_weather is not None and not df_weather.empty else []
    
    if cli_args.start_date:
        try:
            start_date = datetime.strptime(cli_args.start_date, "%Y-%m-%d").date()
            if available_dates and start_date not in available_dates:
                logging.warning(f"Start date {start_date} not in dataset. Starting from next available date.")
                start_date = next((d for d in available_dates if d >= start_date), available_dates[-1])
        except Exception as e:
            logging.error(f"Invalid --start-date '{cli_args.start_date}': {e}. Falling back to dataset start.")
            start_date = available_dates[0] if available_dates else date.today()
    else:
        start_date = available_dates[0] if available_dates else date.today()

    sim_days = cli_args.days if cli_args.days is not None else int(sim_settings_conf.get("simulation_days_default", 90))
    if sim_days <= 0:
        logging.error("Simulation days must be a positive integer."); return

    sim_dates_to_process = [start_date + timedelta(days=i) for i in range(sim_days)]
    actual_sim_days_count = len(sim_dates_to_process)

    # --- Initialize Models ---
    try:
        crop_model = CropModel(initial_stage=crop_config_conf.get("initial_stage"), gdd_thresholds=crop_config_conf.get("gdd_thresholds"), t_base_c=_safe_float(crop_config_conf.get("t_base_c")), t_upper_c=_safe_float(crop_config_conf.get("t_upper_c")), n_demand_per_stage=crop_config_conf.get("N_demand_kg_ha_per_stage"), water_stress_threshold_awc=_safe_float(crop_config_conf.get("water_stress_threshold_awc")), anaerobic_stress_threshold_awc=_safe_float(crop_config_conf.get("anaerobic_stress_threshold_awc")), radiation_use_efficiency_g_mj=_safe_float(crop_config_conf.get("radiation_use_efficiency_g_mj")), light_interception_per_stage=crop_config_conf.get("light_interception_per_stage"), harvest_index=_safe_float(crop_config_conf.get("harvest_index")))
        root_zone_depth_mm = _safe_float(sim_inputs_conf.get("assumed_root_zone_depth_mm"), 400.0)
        initial_moisture_frac = _safe_float(sim_settings_conf.get("initial_moisture_fraction_awc"), 0.5)
        fc_mm = _safe_float(soil_params_conf.get("field_capacity_mm")); wp_mm = _safe_float(soil_params_conf.get("wilting_point_mm")); sat_vol = _safe_float(soil_params_conf.get("saturation_volumetric"), 0.45)
        if fc_mm is None or wp_mm is None: raise ValueError("Config must include 'field_capacity_mm' and 'wilting_point_mm'.")
        custom_soil_params = {"fc": fc_mm / root_zone_depth_mm, "wp": wp_mm / root_zone_depth_mm, "sat": sat_vol, "description": soil_params_conf.get("type", "Custom Soil")}
        soil_model = SoilModel(soil_type_name=soil_params_conf.get("type", "Custom"), soil_depth_mm=root_zone_depth_mm, initial_moisture_fraction_awc=initial_moisture_frac, custom_soil_params=custom_soil_params)
        nutrient_model = NutrientModel(initial_nitrate_N_kg_ha=_safe_float(nutrient_config.get("initial_nitrate_N_kg_ha"), 15.0), initial_ammonium_N_kg_ha=_safe_float(nutrient_config.get("initial_ammonium_N_kg_ha"), 5.0), max_daily_urea_hydrolysis_rate=_safe_float(nutrient_config.get("max_daily_urea_hydrolysis_rate"), 0.30), max_daily_nitrification_rate=_safe_float(nutrient_config.get("max_daily_nitrification_rate"), 0.15), temp_base=_safe_float(nutrient_config.get("temp_base"), 5.0), temp_opt=_safe_float(nutrient_config.get("temp_opt"), 25.0), temp_max=_safe_float(nutrient_config.get("temp_max"), 40.0))
        disease_model = DiseaseModel(config=disease_config)
        rule_path = _resolve_path_relative_to_project(config.get("rule_path", "rules.json"))
        rule_evaluator = RuleEvaluator(rule_file_path=rule_path)
        reporting_service = ReportingService(data_manager, soil_model, crop_model, nutrient_model, disease_model, rule_evaluator)
    except Exception as e:
        logging.critical(f"Failed to initialize models from config: {e}", exc_info=True); return

    latitude = _safe_float(sim_settings_conf.get("latitude_degrees", 40.0))
    elevation = _safe_float(sim_settings_conf.get("elevation_m", 100.0))
    logging.info(f"Simulation will run from {start_date} for {actual_sim_days_count} day(s).")
    
    # --- CSV File Setup ---
    output_dir = os.path.dirname(cli_args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    csv_file = None
    all_triggered_rules_over_time: List[Dict[str, Any]] = []
    
    try:
        csv_file = open(cli_args.output, 'w', newline='', encoding='utf-8')
        csv_writer = csv.DictWriter(csv_file, fieldnames=csv_headers)
        csv_writer.writeheader()
        logging.info(f"CSV output file opened: {cli_args.output}")
        
        # --- Simulation Loop ---
        for day_idx, current_simulation_date in enumerate(sim_dates_to_process):
            sim_day_number = day_idx + 1
            logging.info(f"--- Processing Day {sim_day_number}/{actual_sim_days_count}: {current_simulation_date.strftime('%Y-%m-%d')} ---")

            # 1. Get management actions for the day
            irrigation_today_mm = 0.0
            daily_fertilization_events = []
            if sim_day_number in management_events:
                for event in management_events[sim_day_number]:
                    if event.get("type") == "irrigation":
                        amount = _safe_float(event.get("amount_mm"), 0.0)
                        irrigation_today_mm += amount
                        logging.info(f"MANAGEMENT EVENT: Applying {amount:.1f} mm irrigation.")
                    elif event.get("type") == "fertilizer":
                        amount_n = _safe_float(event.get("amount_kg_ha"), 0.0)
                        fert_type = event.get("fertilizer_type", "unknown")
                        daily_fertilization_events.append({"amount_kg_ha": amount_n, "type": fert_type})
                        logging.info(f"MANAGEMENT EVENT: Applying {amount_n:.1f} kg N/ha as {fert_type}.")
                        nutrient_model.add_fertilizer(amount_n, fert_type)

            # 2. Fetch daily weather data
            daily_aggregated_weather = data_manager.get_daily_aggregated_data(simulation_date=current_simulation_date) or {}
            precipitation_today = daily_aggregated_weather.get('total_precip_mm', 0.0)
            min_temp_numeric = daily_aggregated_weather.get('min_temp_c', 10.0)
            max_temp_numeric = daily_aggregated_weather.get('max_temp_c', 20.0)
            avg_temp_numeric = daily_aggregated_weather.get('avg_temp_c', 15.0)
            avg_humidity_numeric = daily_aggregated_weather.get('avg_humidity', 70.0)
            max_humidity_numeric = daily_aggregated_weather.get('max_humidity_percent', 85.0)
            solar_rad_today = daily_aggregated_weather.get('total_solar_rad_mj_m2', 20.0)
            wind_speed_today = daily_aggregated_weather.get('avg_wind_speed_m_s', 2.0)
            
            et0_today = et0_penman_monteith(t_min=min_temp_numeric, t_max=max_temp_numeric, t_avg=avg_temp_numeric, rh_avg=avg_humidity_numeric, rs_mj_m2=solar_rad_today, u2_m_s=wind_speed_today, lat=latitude, elevation_m=elevation, day_of_year=current_simulation_date)

            # Prepare daily_weather dict for reporting service
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
            current_crop_stage_before_update = crop_model.get_status()["current_stage"]
            kc_map = crop_config_conf.get("kc_per_stage", {})
            kc_today = kc_map.get(current_crop_stage_before_update, crop_config_conf.get("kc_fallback", 0.7))

            soil_model_outputs = soil_model.update_daily(precipitation_today, irrigation_today_mm, et0_today, kc_today)
            deep_percolation_mm_today = soil_model_outputs.get("deep_percolation_mm", 0.0)
            soil_status_dict = soil_model.get_soil_moisture_status()
            
            crop_n_demand_today = crop_model.get_daily_n_demand()
            actual_n_uptake_today = nutrient_model.update_daily(crop_n_demand_today, deep_percolation_mm_today, avg_temp_numeric, soil_status_dict)
            
            crop_status_before_update = crop_model.get_status()
            non_disease_stress = min(crop_status_before_update['nitrogen_stress_factor'], crop_status_before_update['water_stress_factor'])

            # Get hourly weather data for leaf wetness calculation in disease model
            hourly_data_df = data_manager.get_hourly_data_for_simulation_day(current_simulation_date)
            hourly_weather_list = hourly_data_df.to_dict('records') if hourly_data_df is not None else []
            
            # Also calculate LWD for logging/reporting purposes
            calculated_lwd_hours = calculate_leaf_wetness_duration(hourly_weather_list) if hourly_weather_list else 0.0

            disease_weather_input = {'avg_temp_c': avg_temp_numeric}
            disease_model.update_daily(
                daily_weather=disease_weather_input,
                hourly_weather=hourly_weather_list,
                crop_growth_stage=crop_status_before_update['current_stage'],
                crop_lai=crop_status_before_update.get('lai', 0.0),
                crop_non_disease_stress_factor=non_disease_stress
            )
            disease_status = disease_model.get_current_state()
            disease_stress_factor = disease_status['disease_stress_factor']

            crop_model.update_daily(min_temp_numeric, max_temp_numeric, solar_rad_today, actual_n_uptake_today, soil_status_dict, disease_stress_factor)
            crop_status = crop_model.get_status()
            
            nutrient_status = nutrient_model.get_status()

            logging.info(f"  Crop Status: Stage='{crop_status['current_stage']}', GDD={crop_status['accumulated_gdd']:.1f}, Biomass={crop_status['total_biomass_kg_ha']:.1f}, N-Stress={crop_status['nitrogen_stress_factor']:.2f}, H2O-Stress={crop_status['water_stress_factor']:.2f}")
            logging.info(f"  Disease Status: Severity={disease_status['disease_severity']:.4f}, Stress Factor={disease_stress_factor:.2f}")
            logging.info(f"  Nutrient Status: Available N={nutrient_status['available_N_kg_ha']:.2f} kg/ha (Urea: {nutrient_status['urea_N_kg_ha']:.2f}, NH4: {nutrient_status['ammonium_N_kg_ha']:.2f}, NO3: {nutrient_status['nitrate_N_kg_ha']:.2f})")
            logging.info(f"  Soil Status: Water={soil_status_dict['current_water_mm']:.1f}mm, Frac_AWC={soil_status_dict['fraction_awc']:.2f} ('{soil_status_dict['status_category']}') DP={deep_percolation_mm_today:.2f}mm")

            # 4. Evaluate Rules
            input_data_for_rules = {"weather": {"humidity_percent": float(avg_humidity_numeric), "current_temp_c": float(avg_temp_numeric), "leaf_wetness_hours": calculated_lwd_hours}, "soil": {**soil_status_dict}, "crop": {**crop_status}, "nutrients": {**nutrient_status}, "disease": {**disease_status}}
            triggered_rules_today = rule_evaluator.evaluate_rules(input_data_for_rules)
            triggered_rules_list = [r['rule_id'] for r in triggered_rules_today] if triggered_rules_today else []
            
            if triggered_rules_today:
                for rule in triggered_rules_today:
                    logging.info(f"--- >>> Rule {rule.get('rule_id')} ('{rule.get('name')}') TRIGGERED <<< ---")
                all_triggered_rules_over_time.append({"date": current_simulation_date.strftime('%Y-%m-%d'), "rules": triggered_rules_today})

            # 5. Collect and write daily report data using ReportingService
            daily_report_data = reporting_service.get_daily_report_data(
                current_date=current_simulation_date,
                daily_weather=daily_weather,
                daily_irrigation_mm=irrigation_today_mm,
                daily_fertilization_events=daily_fertilization_events,
                triggered_rules_for_day=triggered_rules_list
            )
            csv_writer.writerow(daily_report_data)

        # --- Simulation Complete ---
        final_yield_kg_ha = crop_model.get_final_yield()
        logging.info("\n--- SIMULATION COMPLETE ---")
        logging.info(f"Total Biomass Accumulated: {crop_model.total_biomass_kg_ha:.2f} kg/ha")
        logging.info(f"Predicted Final Grain Yield: {final_yield_kg_ha:.2f} kg/ha")
        if 'disease_status' in locals() and disease_status:
            logging.info(f"Final Disease Severity: {disease_status.get('disease_severity', 0.0):.4f}")
        logging.info(f"Simulation daily outputs saved to: {cli_args.output}")
        
    finally:
        if csv_file is not None:
            csv_file.close()
            logging.info(f"CSV file closed: {cli_args.output}")
            
            # Generate HTML report after simulation completes
            try:
                logging.info(f"\nGenerating HTML report for simulation results...")
                report_generator = ReportGenerator(
                    templates_dir="app/templates",
                    plots_subdir="plots"
                )
                final_report_path = report_generator.generate_scenario_report(
                    simulation_csv_filepath=cli_args.output,
                    config_filepath=cli_args.config,
                    report_output_dir=OUTPUT_DIR
                )
                if final_report_path:
                    logging.info(f"HTML report successfully generated: {final_report_path}")
                else:
                    logging.error("HTML report generation failed.")
            except Exception as report_e:
                logging.error(f"Error during HTML report generation: {report_e}", exc_info=True)
    
    if all_triggered_rules_over_time:
        logging.info("\n\n--- Overall Triggered Rules Summary ---")
        for day_result in all_triggered_rules_over_time:
            date_log_message = f"\nOn Date: {day_result['date']}"
            for i, rule in enumerate(day_result['rules']):
                date_log_message += f"\n  {i+1}. Rule ID: {rule.get('rule_id')} (Name: {rule.get('name')})"
                recommendation = rule.get('recommendation', rule.get('result', {}))
                if isinstance(recommendation, dict):
                    for key, value in recommendation.items():
                        date_log_message += f"\n     {key.replace('_', ' ').capitalize()}: {value}"
                else:
                    date_log_message += f"\n     Recommendation/Result: {recommendation}"
            logging.info(date_log_message)
            
    logging.info("\n--- AGROVISUS Simulation Engine Finished ---")


if __name__ == '__main__':
    cli_args = parse_arguments()
    main(cli_args)
