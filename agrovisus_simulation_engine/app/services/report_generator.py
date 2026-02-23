# app/services/report_generator.py
import datetime
import json
import logging
import os

from jinja2 import Environment, FileSystemLoader

from app.services.report_data_manager import ReportDataManager
from app.utils import plot_utils


class ReportGenerator:
    """
    Generates comprehensive HTML reports from simulation output data.
    Uses Jinja2 templates to render the final report with plots and KPIs.
    """

    def __init__(self, templates_dir="app/templates", plots_subdir="plots"):
        """
        Initialize the report generator.

        Args:
            templates_dir: Directory containing Jinja2 templates
            plots_subdir: Subdirectory name for plots relative to report output directory
        """
        self.env = Environment(loader=FileSystemLoader(templates_dir))
        self.template = self.env.get_template("simulation_report_template.html")
        self.plots_subdir = (
            plots_subdir  # Where plots will be saved relative to report_output_dir
        )
        logging.info(f"ReportGenerator initialized with template from {templates_dir}")

    def generate_scenario_report(
        self, simulation_csv_filepath, config_filepath, report_output_dir
    ):
        """
        Generates a comprehensive HTML report for a single simulation scenario.

        Args:
            simulation_csv_filepath (str): Path to the CSV output from the simulation.
            config_filepath (str): Path to the config.json used for this simulation.
            report_output_dir (str): Directory where the report HTML and plots will be saved.

        Returns:
            str: Path to the generated report file, or None if generation failed
        """
        os.makedirs(report_output_dir, exist_ok=True)
        plots_output_path = os.path.join(report_output_dir, self.plots_subdir)
        os.makedirs(plots_output_path, exist_ok=True)

        # 1. Load Simulation Data
        data_manager = ReportDataManager(simulation_csv_filepath)
        df = data_manager.df

        if df.empty:
            logging.error(
                f"Cannot generate report: No data loaded from {simulation_csv_filepath}"
            )
            return None

        # 2. Load Configuration Parameters (Important Factors)
        config_params = {}
        try:
            with open(config_filepath, "r") as f:
                config_params = json.load(f)
        except FileNotFoundError:
            logging.warning(
                f"Config file not found: {config_filepath}. Report will miss config details."
            )
        except json.JSONDecodeError:
            logging.error(f"Error decoding config JSON from {config_filepath}")

        # 3. Generate Plots
        plot_paths = {}

        # Crop Growth
        crop_cols = ["total_biomass_kg_ha", "gdd_accumulated", "leaf_area_index"]
        available_crop_cols = [col for col in crop_cols if col in df.columns]
        if available_crop_cols:
            plot_paths["crop_growth_plot"] = plot_utils.plot_multiple_time_series(
                df,
                "Crop Growth & Development",
                "Value",
                y_columns=available_crop_cols,
                filename="crop_growth.png",
                output_dir=plots_output_path,
            )

        # Water Dynamics
        water_cols = [
            "fraction_awc",
            "daily_precipitation_mm",
            "daily_irrigation_mm",
            "daily_percolation_mm",
        ]
        available_water_cols = [col for col in water_cols if col in df.columns]
        if available_water_cols:
            plot_paths["water_dynamics_plot"] = plot_utils.plot_multiple_time_series(
                df,
                "Soil Moisture & Water Dynamics",
                "mm / Fraction",
                y_columns=available_water_cols,
                filename="water_dynamics.png",
                output_dir=plots_output_path,
            )

        # Nutrient Dynamics
        nitrogen_cols = ["soil_nitrate_kg_ha", "soil_ammonium_kg_ha", "crop_nitrogen_uptake_kg_ha"]
        available_nitrogen_cols = [col for col in nitrogen_cols if col in df.columns]
        if available_nitrogen_cols:
            plot_paths["nitrogen_dynamics_plot"] = plot_utils.plot_multiple_time_series(
                df,
                "Nitrogen Pools & Uptake",
                "N (kg/ha)",
                y_columns=available_nitrogen_cols,
                filename="nitrogen_dynamics.png",
                output_dir=plots_output_path,
            )

        # Stress Factors
        stress_cols = [
            "water_stress_factor",
            "nitrogen_stress_factor",
            "disease_stress_factor",
        ]
        available_stress_cols = [col for col in stress_cols if col in df.columns]
        if available_stress_cols:
            plot_paths["stress_factors_plot"] = plot_utils.plot_multiple_time_series(
                df,
                "Crop Stress Factors",
                "Stress Factor (0-1)",
                y_columns=available_stress_cols,
                filename="stress_factors.png",
                output_dir=plots_output_path,
            )

        # Disease Progression
        if "disease_severity_percent" in df.columns:
            plot_paths["disease_progression_plot"] = plot_utils.plot_time_series(
                data_manager.get_daily_data("disease_severity_percent"),
                "Disease Progression",
                "Severity (%)",
                filename="disease_progression.png",
                output_dir=plots_output_path,
            )

        # Adjust plot paths to be relative for HTML embedding
        for key, path in plot_paths.items():
            if path:
                plot_paths[key] = os.path.join(
                    self.plots_subdir, os.path.basename(path)
                )

        # 4. Extract KPIs (Summary Charts data)
        final_biomass = (
            data_manager.get_final_value("total_biomass_kg_ha") if not df.empty else 0.0
        )
        crop_config = config_params.get("crop_model_config", {})
        harvest_index = crop_config.get("harvest_index", 0.5)

        kpis = {
            "crop_template": crop_config.get("crop_template", "custom"),
            "crop_name": crop_config.get("crop_name", "Unknown"),
            "final_biomass_kg_ha": final_biomass if final_biomass else 0.0,
            "final_yield_kg_ha": final_biomass * harvest_index
            if final_biomass
            else 0.0,
            "final_growth_stage": data_manager.get_final_value("crop_growth_stage") or "N/A",
            "final_gdd": data_manager.get_final_value("gdd_accumulated") or 0.0,
            "total_irrigation_mm": data_manager.get_summary_stats("daily_irrigation_mm").get(
                "sum", 0.0
            ),
            "total_precipitation_mm": data_manager.get_summary_stats("daily_precipitation_mm").get(
                "sum", 0.0
            ),
            "total_n_leached_kg_ha": data_manager.get_summary_stats(
                "nitrogen_daily_leaching_kg_ha"
            ).get("sum", 0.0),
            "peak_disease_severity_percent": data_manager.get_summary_stats(
                "disease_severity_percent"
            ).get("max", 0.0),
            "avg_stress_factor": data_manager.get_summary_stats(
                "overall_stress_factor"
            ).get("mean", 0.0),
            "triggered_rules": [],
        }

        # Process triggered rules
        if "triggered_rules" in df.columns:
            triggered_rules = (
                df["triggered_rules"]
                .apply(
                    lambda x: [r.strip() for r in x.split(",") if r.strip()]
                    if isinstance(x, str)
                    else []
                )
                .explode()
                .dropna()
                .unique()
                .tolist()
            )
            # Clean up the triggered rules to remove empty strings or 'None' if any
            kpis["triggered_rules"] = [
                rule for rule in triggered_rules if rule and rule.lower() != "none"
            ]

        # 5. Prepare data for HTML rendering
        context = {
            "scenario_name": os.path.basename(config_filepath).replace(".json", "")
            if config_filepath
            else "Unnamed Scenario",
            "simulation_id": os.path.basename(simulation_csv_filepath).replace(
                ".csv", ""
            ),
            "generation_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "start_date": df.index.min().strftime("%Y-%m-%d")
            if not df.empty
            else "N/A",
            "end_date": df.index.max().strftime("%Y-%m-%d") if not df.empty else "N/A",
            "total_days": len(df) if not df.empty else 0,
            "config_params": config_params,
            "kpis": kpis,
            "plot_paths": plot_paths,
            "daily_data_html_table": df.head(5).to_html(
                classes="table table-striped", escape=False
            )
            if not df.empty
            else "",  # Display first 5 rows of raw data
        }

        # 6. Render and save the HTML report
        report_html_content = self.template.render(context)
        report_filename = os.path.join(
            report_output_dir, f"report_{context['simulation_id']}.html"
        )
        with open(report_filename, "w", encoding="utf-8") as f:
            f.write(report_html_content)
        logging.info(f"Report generated successfully: {report_filename}")
        return report_filename

    def generate_comparison_report(self, scenario_data_paths, comparison_output_dir):
        """
        Generates a comparative HTML report for multiple simulation scenarios.

        Args:
            scenario_data_paths (dict): A dictionary where keys are scenario names (str)
                                        and values are dicts containing 'csv_filepath' (str)
                                        and 'config_filepath' (str) for each scenario.
            comparison_output_dir (str): Directory where the comparison report HTML and plots will be saved.
        """
        os.makedirs(comparison_output_dir, exist_ok=True)
        plots_output_path = os.path.join(comparison_output_dir, self.plots_subdir)
        os.makedirs(plots_output_path, exist_ok=True)

        all_dfs = {}
        all_kpis = {}
        scenario_names = []

        # 1. Load Data and Extract KPIs for all scenarios
        for name, paths in scenario_data_paths.items():
            scenario_names.append(name)
            data_manager = ReportDataManager(paths["csv_filepath"])
            df = data_manager.df
            if df.empty:
                logging.warning(
                    f"Skipping scenario '{name}': No data loaded from {paths['csv_filepath']}"
                )
                continue
            all_dfs[name] = df

            config_params = {}
            try:
                with open(paths["config_filepath"], "r") as f:
                    config_params = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logging.warning(
                    f"Could not load config for scenario '{name}': {e}. KPIs might be incomplete."
                )

            # Extract KPIs
            crop_cfg = config_params.get("crop_model_config", {})
            harvest_index = float(crop_cfg.get("harvest_index", 0.5))
            final_biomass = data_manager.get_final_value("total_biomass_kg_ha") or 0.0

            kpis = {
                "crop_name": crop_cfg.get("crop_name", name),
                "final_biomass_kg_ha": final_biomass if not df.empty else 0.0,
                "final_yield_kg_ha": final_biomass * harvest_index
                if not df.empty
                else 0.0,
                "total_irrigation_mm": data_manager.get_summary_stats(
                    "daily_irrigation_mm"
                ).get("sum", 0.0),
                "total_n_leached_kg_ha": data_manager.get_summary_stats(
                    "nitrogen_daily_leaching_kg_ha"
                ).get("sum", 0.0),
                "peak_disease_severity_percent": data_manager.get_summary_stats(
                    "disease_severity_percent"
                ).get("max", 0.0),
                "avg_stress_factor": data_manager.get_summary_stats(
                    "overall_stress_factor"
                ).get("mean", 0.0),
            }
            all_kpis[name] = kpis

        if not all_dfs:
            logging.error(
                "No valid scenarios to compare. Aborting comparison report generation."
            )
            return None

        # 2. Generate Comparative Plots
        plot_paths = {}

        # Comparative Bar Charts
        plot_paths["yield_comparison_plot"] = plot_utils.plot_comparative_bar_chart(
            all_kpis,
            "final_yield_kg_ha",
            "Final Grain Yield Comparison",
            "Yield (kg/ha)",
            filename="comp_yield.png",
            output_dir=plots_output_path,
        )
        plot_paths["irrigation_comparison_plot"] = (
            plot_utils.plot_comparative_bar_chart(
                all_kpis,
                "total_irrigation_mm",
                "Total Irrigation Comparison",
                "Irrigation (mm)",
                filename="comp_irrigation.png",
                output_dir=plots_output_path,
            )
        )
        # Add more comparative bar charts for other KPIs

        # Comparative Time-Series Plots
        plot_paths["comparative_awc_plot"] = plot_utils.plot_comparative_time_series(
            all_dfs,
            "fraction_awc",
            "Soil Moisture (Fraction AWC) Comparison",
            "Fraction AWC (0-1)",
            filename="comp_awc.png",
            output_dir=plots_output_path,
        )
        plot_paths["comparative_biomass_plot"] = (
            plot_utils.plot_comparative_time_series(
                all_dfs,
                "total_biomass_kg_ha",
                "Total Biomass Accumulation Comparison",
                "Biomass (kg/ha)",
                filename="comp_biomass.png",
                output_dir=plots_output_path,
            )
        )
        plot_paths["comparative_stress_plot"] = plot_utils.plot_comparative_time_series(
            all_dfs,
            "overall_stress_factor",
            "Overall Crop Stress Comparison",
            "Stress Factor (0-1)",
            filename="comp_stress.png",
            output_dir=plots_output_path,
        )
        plot_paths["comparative_disease_plot"] = (
            plot_utils.plot_comparative_time_series(
                all_dfs,
                "disease_severity_percent",
                "Disease Severity Progression Comparison",
                "Severity (%)",
                filename="comp_disease.png",
                output_dir=plots_output_path,
            )
        )
        # Adjust plot paths to be relative for HTML embedding
        for key, path in plot_paths.items():
            if path:
                plot_paths[key] = os.path.join(
                    self.plots_subdir, os.path.basename(path)
                )

        # 3. Render and save the HTML comparison report
        comparison_template = self.env.get_template("comparison_report_template.html")
        context = {
            "generation_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "scenario_names": scenario_names,
            "all_kpis": all_kpis,
            "plot_paths": plot_paths,
        }

        report_html_content = comparison_template.render(context)
        report_filename = os.path.join(comparison_output_dir, "comparison_report.html")
        with open(report_filename, "w", encoding="utf-8") as f:
            f.write(report_html_content)
        logging.info(f"Comparison report generated successfully: {report_filename}")
        return report_filename


# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Generate a report from the simulation output
    generator = ReportGenerator()
    report_path = generator.generate_scenario_report(
        simulation_csv_filepath="outputs/simulation_output.csv",
        config_filepath="config.json",
        report_output_dir="outputs",
    )

    if report_path:
        print(f"Report generated successfully: {report_path}")
    else:
        print("Report generation failed.")
