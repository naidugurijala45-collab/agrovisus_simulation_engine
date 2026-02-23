import unittest
import os
import shutil
import tempfile
import json
from datetime import date

# Adjust path to find app module
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.simulation_service import SimulationService

class TestSimulationService(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        
        # Mock Config
        self.config = {
            "simulation_settings": {
                "simulation_days_default": 2,
                "initial_moisture_fraction_awc": 0.5,
                "latitude_degrees": 40.0,
                "elevation_m": 100.0
            },
            "soil_parameters": {
                "type": "Test Clay",
                "field_capacity_mm": 140.0,
                "wilting_point_mm": 70.0,
                "saturation_volumetric": 0.45
            },
            "simulation_inputs": {
                "assumed_root_zone_depth_mm": 400.0
            },
            "historical_data_paths": {
                "hourly_weather_csv": "data/hourly_weather.csv" # Assume this exists in project
            },
            "crop_model_config": {
                "crop_name": "Test Corn",
                "initial_stage": "Emergence",
                "t_base_c": 10.0,
                "t_upper_c": 30.0,
                "harvest_index": 0.5,
                "water_stress_threshold_awc": 0.5,
                "anaerobic_stress_threshold_awc": 0.9,
                "radiation_use_efficiency_g_mj": 1.5,
                "gdd_thresholds": {
                    "Emergence": 0,
                    "Vegetative": 100,
                    "Flowering": 500,
                    "Maturity": 1000
                },
                "kc_per_stage": {
                    "Emergence": 0.4,
                    "Vegetative": 0.8,
                    "Flowering": 1.2,
                    "Maturity": 0.6
                },
                "light_interception_per_stage": {
                    "Emergence": 0.1,
                    "Vegetative": 0.5,
                    "Flowering": 0.9,
                    "Maturity": 0.7
                },
                "N_demand_kg_ha_per_stage": {
                    "Emergence": 0.5,
                    "Vegetative": 2.0,
                    "Flowering": 3.0,
                    "Maturity": 1.0
                },
                "kc_fallback": 0.5
            },
            "nutrient_model_config": {},
            "disease_model_config": {},
            "management_schedule": []
        }
    
    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_run_simulation(self):
        # Initialize service
        try:
            service = SimulationService(self.config, self.project_root)
        except Exception as e:
            self.fail(f"SimulationService init failed: {e}")

        output_csv = os.path.join(self.test_dir, 'test_output.csv')
        start_date = date(2023, 1, 1)
        
        # Run simulation
        result = service.run_simulation(start_date, sim_days=2, output_csv_path=output_csv)
        
        # Verify output file
        self.assertTrue(os.path.exists(output_csv), "Output CSV should be created")
        
        with open(output_csv, 'r') as f:
            lines = f.readlines()
            self.assertGreater(len(lines), 1, "CSV should have header and at least one data row")
            header = lines[0]
            self.assertIn("date", header)
            self.assertIn("total_biomass_kg_ha", header)
        
        # Verify result dict
        self.assertIn("final_yield_kg_ha", result)
        self.assertIn("total_biomass_kg_ha", result)

if __name__ == '__main__':
    unittest.main()
