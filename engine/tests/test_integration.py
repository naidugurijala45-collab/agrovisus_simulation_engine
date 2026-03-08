"""
End-to-end integration tests for the AgroVisus simulation engine.

Tests each crop template through a short simulation run and validates
that the output CSV contains all expected columns with reasonable values.

Usage:
    python -m pytest tests/test_integration.py -v
"""
import json
import os
import sys
import tempfile

import pandas as pd
import pytest

# Ensure project root is on path
ENGINE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ENGINE_ROOT)

from app.utils.crop_template_loader import CropTemplateLoader
from app.utils.config_loader import load_config


# Expected columns in every simulation CSV
REQUIRED_COLUMNS = [
    "date",
    "total_biomass_kg_ha",
    "gdd_accumulated",
    "leaf_area_index",
    "crop_growth_stage",
    "fraction_awc",
    "daily_precipitation_mm",
    "daily_irrigation_mm",
    "daily_avg_temp_c",
    "daily_max_temp_c",
    "daily_min_temp_c",
    "soil_nitrate_kg_ha",
    "soil_ammonium_kg_ha",
    "crop_nitrogen_uptake_kg_ha",
    "water_stress_factor",
    "nitrogen_stress_factor",
    "disease_stress_factor",
    "overall_stress_factor",
    "disease_severity_percent",
    "daily_fertilization_kg_ha",
]

NUMERIC_COLUMNS = [
    "total_biomass_kg_ha",
    "gdd_accumulated",
    "leaf_area_index",
    "fraction_awc",
    "water_stress_factor",
    "nitrogen_stress_factor",
    "disease_stress_factor",
    "overall_stress_factor",
]


def run_simulation_for_crop(crop_name, sim_days=30):
    """Run a short simulation for a crop and return the CSV path."""
    import subprocess

    config = load_config(os.path.join(ENGINE_ROOT, "config.json"))
    config["crop_model_config"]["crop_template"] = crop_name

    # Save temporary config
    temp_config = os.path.join(ENGINE_ROOT, "outputs", f"test_config_{crop_name}.json")
    with open(temp_config, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    csv_path = os.path.join(ENGINE_ROOT, "outputs", f"test_{crop_name}_output.csv")

    python_exe = os.path.join(ENGINE_ROOT, "venv", "Scripts", "python.exe")
    if not os.path.exists(python_exe):
        python_exe = sys.executable

    result = subprocess.run(
        [python_exe, "run.py", "-c", temp_config, "-d", str(sim_days), "-o", csv_path],
        cwd=ENGINE_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )

    # Cleanup temp config
    if os.path.exists(temp_config):
        os.remove(temp_config)

    if result.returncode != 0:
        pytest.fail(f"Simulation failed for {crop_name}:\n{result.stderr}")

    return csv_path


class TestCropTemplateAvailability:
    """Verify all crop templates are loadable."""

    def test_loader_initializes(self):
        loader = CropTemplateLoader()
        assert loader is not None

    def test_all_templates_loadable(self):
        loader = CropTemplateLoader()
        templates = loader.list_available_crops()
        assert len(templates) >= 5, f"Expected at least 5 templates, got {len(templates)}"

        for name in templates:
            t = loader.load_template(name)
            assert "crop_name" in t, f"Template '{name}' missing crop_name"
            growth = t.get("growth", {})
            assert "t_base_c" in growth, f"Template '{name}' missing growth.t_base_c"
            assert "harvest_index" in growth, f"Template '{name}' missing growth.harvest_index"
            assert "gdd_thresholds" in growth, f"Template '{name}' missing growth.gdd_thresholds"
            assert "soil" in t, f"Template '{name}' missing soil"
            assert "diseases" in t, f"Template '{name}' missing diseases"


class TestCornSimulation:
    """End-to-end test with corn (most common crop)."""

    @pytest.fixture(scope="class")
    def corn_csv(self):
        csv_path = run_simulation_for_crop("corn", sim_days=30)
        yield csv_path
        if os.path.exists(csv_path):
            os.remove(csv_path)

    def test_csv_created(self, corn_csv):
        assert os.path.exists(corn_csv), "CSV file was not created"

    def test_csv_has_rows(self, corn_csv):
        df = pd.read_csv(corn_csv)
        assert len(df) == 30, f"Expected 30 rows, got {len(df)}"

    def test_required_columns_present(self, corn_csv):
        df = pd.read_csv(corn_csv)
        missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
        assert not missing, f"Missing columns: {missing}"

    def test_no_nan_in_critical_columns(self, corn_csv):
        df = pd.read_csv(corn_csv)
        for col in NUMERIC_COLUMNS:
            if col in df.columns:
                nan_count = df[col].isna().sum()
                assert nan_count == 0, f"Column '{col}' has {nan_count} NaN values"

    def test_biomass_increases(self, corn_csv):
        df = pd.read_csv(corn_csv)
        first_biomass = df["total_biomass_kg_ha"].iloc[0]
        last_biomass = df["total_biomass_kg_ha"].iloc[-1]
        assert last_biomass > first_biomass, "Biomass should increase over time"

    def test_gdd_accumulates(self, corn_csv):
        df = pd.read_csv(corn_csv)
        first_gdd = df["gdd_accumulated"].iloc[0]
        last_gdd = df["gdd_accumulated"].iloc[-1]
        assert last_gdd >= first_gdd, "GDD should accumulate"

    def test_stress_factors_in_range(self, corn_csv):
        df = pd.read_csv(corn_csv)
        for col in ["water_stress_factor", "nitrogen_stress_factor",
                     "disease_stress_factor", "overall_stress_factor"]:
            assert df[col].min() >= 0.0, f"{col} has negative values"
            assert df[col].max() <= 1.0, f"{col} exceeds 1.0"

    def test_fraction_awc_in_range(self, corn_csv):
        df = pd.read_csv(corn_csv)
        assert df["fraction_awc"].min() >= 0.0, "fraction_awc negative"
        assert df["fraction_awc"].max() <= 2.0, "fraction_awc unreasonably high"


class TestReportGeneration:
    """Test that HTML report generates from simulation output."""

    @pytest.fixture(scope="class")
    def report_output(self):
        from app.services.report_generator import ReportGenerator

        csv_path = os.path.join(ENGINE_ROOT, "outputs", "simulation_output.csv")
        if not os.path.exists(csv_path):
            pytest.skip("No simulation output found")

        rg = ReportGenerator(templates_dir=os.path.join(ENGINE_ROOT, "app", "templates"), plots_subdir="plots")
        report_path = rg.generate_scenario_report(
            simulation_csv_filepath=csv_path,
            config_filepath=os.path.join(ENGINE_ROOT, "config.json"),
            report_output_dir=os.path.join(ENGINE_ROOT, "outputs"),
        )
        yield report_path

    def test_report_created(self, report_output):
        assert report_output is not None
        assert os.path.exists(report_output)

    def test_report_has_content(self, report_output):
        size = os.path.getsize(report_output)
        assert size > 1000, f"Report too small: {size} bytes"

    def test_report_contains_key_elements(self, report_output):
        with open(report_output, "r", encoding="utf-8") as f:
            html = f.read()
        assert "kg/ha" in html, "Report missing biomass data"
        assert "AgroVisus" in html, "Report missing branding"


class TestReportDataManager:
    """Test ReportDataManager with real CSV data."""

    def test_summary_stats(self):
        from app.services.report_data_manager import ReportDataManager

        csv_path = os.path.join(ENGINE_ROOT, "outputs", "simulation_output.csv")
        if not os.path.exists(csv_path):
            pytest.skip("No simulation output found")

        dm = ReportDataManager(csv_path)
        assert not dm.df.empty

        # Test known columns
        stats = dm.get_summary_stats("daily_irrigation_mm")
        assert "sum" in stats
        assert "mean" in stats

        final = dm.get_final_value("total_biomass_kg_ha")
        assert final is not None
        assert final > 0
