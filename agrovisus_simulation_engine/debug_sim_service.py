
import os
import sys
import unittest
import json
from datetime import date
import logging

# Add project root
sys.path.append(os.getcwd())

from app.services.simulation_service import SimulationService
from app.utils.exceptions import ConfigValidationError

def test_simulation_service_init_with_mock_config():
    print("\n--- Testing SimulationService Init ---")
    
    # This is the EXACT config from test_simulation_service.py (after my fix)
    config = {
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
    
    with open("outputs/debug_sim.log", "w") as f:
        try:
            service = SimulationService(config, os.getcwd())
            f.write("SimulationService init success\n")
        except Exception as e:
            f.write(f"SimulationService init failed: {e}\n")
            import traceback
            traceback.print_exc(file=f)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_simulation_service_init_with_mock_config()
