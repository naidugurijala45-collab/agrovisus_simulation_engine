# AGROVISUS_SIMULATION_ENGINE/run.py
import os
import sys
import json
import argparse
import logging
from datetime import datetime, date

from app.services.report_generator import ReportGenerator
from app.services.simulation_service import SimulationService
from app.utils.exceptions import AgroVisusError

OUTPUT_DIR = 'outputs'
DEFAULT_LOG_FILE = os.path.join(OUTPUT_DIR, 'simulation_run.log')
DEFAULT_CSV_OUTPUT = os.path.join(OUTPUT_DIR, 'simulation_output.csv')
DEFAULT_CONFIG_FILE_PATH = 'config.json'

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


from app.utils.config_loader import load_config


def parse_arguments():
    parser = argparse.ArgumentParser(description="AGROVISUS Simulation Engine")
    parser.add_argument("-c", "--config", default=DEFAULT_CONFIG_FILE_PATH, type=str, help=f"Path to JSON config file (default: {DEFAULT_CONFIG_FILE_PATH})")
    parser.add_argument("-d", "--days", type=int, help="Number of days to simulate (overrides config)")
    parser.add_argument("-o", "--output", default=DEFAULT_CSV_OUTPUT, type=str, help=f"Path for output CSV file (default: {DEFAULT_CSV_OUTPUT})")
    parser.add_argument("-s", "--start-date", type=str, default=None, help="Simulation start date in YYYY-MM-DD format.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose (DEBUG level) logging.")
    return parser.parse_args()


def main(cli_args):
    # Create outputs directory early and set up logging
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    setup_logging(log_file_path=DEFAULT_LOG_FILE, verbose=cli_args.verbose)

    # Load config
    config = load_config(cli_args.config)

    # Initialize Service
    project_root = os.path.abspath(os.path.dirname(__file__))
    try:
        sim_service = SimulationService(config_data=config, project_root=project_root)
    except Exception:
        return # Error already logged in service init

    # Determine Start Date
    available_dates = sim_service.get_available_start_dates()
    
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

    sim_settings_conf = config.get("simulation_settings", {})
    sim_days = cli_args.days if cli_args.days is not None else int(sim_settings_conf.get("simulation_days_default", 90))
    if sim_days <= 0:
        logging.error("Simulation days must be a positive integer."); return

    # --- CSV File Setup ---
    output_dir = os.path.dirname(cli_args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    final_report_path = None
    try:
        # Run Simulation
        sim_service.run_simulation(start_date=start_date, sim_days=sim_days, output_csv_path=cli_args.output)
        
    finally:
        logging.info(f"CSV file closed (handled by service): {cli_args.output}")
            
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
    
    # Print clean summary
    _print_summary(cli_args.output, config, sim_days, start_date, final_report_path)
    logging.info("\n--- AGROVISUS Simulation Engine Finished ---")


def _print_summary(csv_path, config, sim_days, start_date, report_path):
    """Print a clean, human-readable summary after simulation."""
    try:
        import pandas as pd
        df = pd.read_csv(csv_path)
        if df.empty:
            return

        final = df.iloc[-1]
        crop_cfg = config.get("crop_model_config", {})
        template = crop_cfg.get("crop_template", "custom")
        hi = float(crop_cfg.get("harvest_index", 0.5))
        biomass = float(final.get("total_biomass_kg_ha", 0))
        est_yield = biomass * hi

        w = 52
        print(f"\n{'═' * w}")
        print(f"  🌾  AGROVISUS SIMULATION SUMMARY")
        print(f"{'═' * w}")
        print(f"  Crop Template    │  {template.capitalize()}")
        print(f"  Start Date       │  {start_date}")
        print(f"  Duration         │  {sim_days} days")
        print(f"  Final Stage      │  {final.get('crop_growth_stage', 'N/A')}")
        print(f"{'─' * w}")
        print(f"  Total Biomass    │  {biomass:,.0f} kg/ha")
        print(f"  Estimated Yield  │  {est_yield:,.0f} kg/ha  (HI={hi})")
        print(f"  GDD Accumulated  │  {final.get('gdd_accumulated', 0):.0f} °C·d")
        print(f"{'─' * w}")
        total_irr = df["daily_irrigation_mm"].sum()
        total_rain = df["daily_precipitation_mm"].sum()
        avg_stress = df["overall_stress_factor"].mean()
        print(f"  Irrigation       │  {total_irr:.0f} mm")
        print(f"  Precipitation    │  {total_rain:.0f} mm")
        print(f"  Avg Stress       │  {avg_stress:.2f}  (1.0 = none)")
        print(f"{'─' * w}")
        print(f"  CSV Output       │  {csv_path}")
        if report_path:
            print(f"  HTML Report      │  {report_path}")
        print(f"{'═' * w}")
        print(f"  💡 Run:  streamlit run dashboard.py")
        print(f"{'═' * w}\n")
    except Exception:
        pass  # Don't crash on summary errors


if __name__ == '__main__':
    cli_args = parse_arguments()
    try:
        main(cli_args)
    except AgroVisusError as e:
        print(f"\n{'='*60}")
        print(e.user_message())
        print(f"{'='*60}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nSimulation interrupted by user.")
        sys.exit(130)
