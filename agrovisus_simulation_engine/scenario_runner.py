"""
AgroVisus Batch Scenario Runner

Run multiple crop simulations back-to-back and generate a comparative HTML report.

Usage:
    python scenario_runner.py --crops corn wheat rice --days 120
    python scenario_runner.py --crops corn soybean --days 90 --output outputs/comparison
    python scenario_runner.py --all --days 100
"""
import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime
import io

# Force UTF-8 for stdout/stderr to handle emojis on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from app.services.report_generator import ReportGenerator
from app.utils.crop_template_loader import CropTemplateLoader

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs")
COMPARISON_DIR = os.path.join(OUTPUT_DIR, "comparison")
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                os.path.join(OUTPUT_DIR, "scenario_runner.log"), mode="w", encoding="utf-8"
            ),
        ],
    )


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def run_single_scenario(crop_name, sim_days, scenario_output_dir):
    """Run a single crop simulation and return the CSV path."""
    import subprocess

    # Update config to use this crop template
    config = load_config()
    config["crop_model_config"]["crop_template"] = crop_name
    save_config(config)

    csv_path = os.path.join(scenario_output_dir, f"{crop_name}_output.csv")

    python_exe = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
    if not os.path.exists(python_exe):
        python_exe = sys.executable

    logging.info(f"Running {crop_name} simulation for {sim_days} days...")

    result = subprocess.run(
        [python_exe, "run.py", "-d", str(sim_days), "-o", csv_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )

    if result.returncode != 0:
        logging.error(f"Simulation failed for {crop_name}!")
        logging.error(result.stderr or result.stdout)
        return None

    if os.path.exists(csv_path):
        logging.info(f"✓ {crop_name} completed → {csv_path}")
        return csv_path
    else:
        logging.error(f"CSV not found after simulation: {csv_path}")
        return None


def run_scenarios(crop_names, sim_days, output_dir):
    """Run all scenarios and generate comparison report."""
    os.makedirs(output_dir, exist_ok=True)
    scenario_dir = os.path.join(output_dir, "scenarios")
    os.makedirs(scenario_dir, exist_ok=True)

    # Save original config to restore later
    original_config = load_config()

    # Validate crop names
    loader = CropTemplateLoader()
    available = loader.list_available_crops()
    invalid = [c for c in crop_names if c not in available]
    if invalid:
        logging.error(f"Unknown crop templates: {invalid}")
        logging.info(f"Available templates: {available}")
        return None

    scenario_data = {}
    results = []

    print(f"\n{'═' * 56}")
    print(f"  🌾  AGROVISUS BATCH SCENARIO RUNNER")
    print(f"{'═' * 56}")
    print(f"  Crops: {', '.join(c.capitalize() for c in crop_names)}")
    print(f"  Days:  {sim_days}")
    print(f"{'─' * 56}")

    for crop in crop_names:
        csv_path = run_single_scenario(crop, sim_days, scenario_dir)

        if csv_path:
            # Create a temporary config for this scenario
            scenario_config_path = os.path.join(
                scenario_dir, f"{crop}_config.json"
            )
            config = load_config()
            with open(scenario_config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)

            template_info = loader.load_template(crop)
            display_name = template_info.get("crop_name", crop.capitalize())

            scenario_data[display_name] = {
                "csv_filepath": csv_path,
                "config_filepath": scenario_config_path,
            }

            # Quick summary from CSV
            import pandas as pd

            df = pd.read_csv(csv_path)
            final = df.iloc[-1]
            hi = float(template_info.get("harvest_index", 0.5))
            biomass = float(final.get("total_biomass_kg_ha", 0))
            results.append({
                "crop": display_name,
                "biomass": biomass,
                "yield": biomass * hi,
                "gdd": float(final.get("gdd_accumulated", 0)),
                "stage": final.get("crop_growth_stage", "N/A"),
                "stress": float(df["overall_stress_factor"].mean()),
            })

    # Restore original config
    save_config(original_config)

    if not scenario_data:
        logging.error("No scenarios completed successfully.")
        return None

    # Print results table
    print(f"\n{'─' * 56}")
    print(f"  {'Crop':<16} {'Biomass':>10} {'Yield':>10} {'Stress':>8}")
    print(f"  {'':─<16} {'':─>10} {'':─>10} {'':─>8}")
    for r in results:
        print(
            f"  {r['crop']:<16} {r['biomass']:>9,.0f} {r['yield']:>9,.0f} "
            f"{r['stress']:>7.2f}"
        )
    print(f"{'─' * 56}")

    # Generate comparison report
    logging.info("\nGenerating comparison report...")
    try:
        report_gen = ReportGenerator(
            templates_dir="app/templates", plots_subdir="plots"
        )
        report_path = report_gen.generate_comparison_report(
            scenario_data_paths=scenario_data,
            comparison_output_dir=output_dir,
        )
        if report_path:
            print(f"\n  📊 Comparison report: {report_path}")
            print(f"{'═' * 56}\n")
            return report_path
    except Exception as e:
        logging.error(f"Comparison report generation failed: {e}", exc_info=True)

    return None


def main():
    parser = argparse.ArgumentParser(
        description="AgroVisus Batch Scenario Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scenario_runner.py --crops corn wheat rice --days 120
  python scenario_runner.py --all --days 90
  python scenario_runner.py --crops corn soybean --days 100 --output outputs/my_comparison
        """,
    )
    parser.add_argument(
        "--crops",
        nargs="+",
        help="Crop template names to simulate (e.g. corn wheat rice)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all available crop templates",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Number of simulation days (default: 90)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=COMPARISON_DIR,
        help=f"Output directory for comparison (default: {COMPARISON_DIR})",
    )

    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    setup_logging()

    if args.all:
        loader = CropTemplateLoader()
        crop_names = loader.list_available_crops()
    elif args.crops:
        crop_names = [c.lower() for c in args.crops]
    else:
        parser.error("Specify --crops or --all")
        return

    if len(crop_names) < 2:
        logging.error("Need at least 2 crops for comparison. Use run.py for single runs.")
        return

    report = run_scenarios(crop_names, args.days, args.output)
    if report:
        logging.info(f"All done! Open {report} in your browser.")
    else:
        logging.error("Scenario runner finished with errors.")


if __name__ == "__main__":
    main()
