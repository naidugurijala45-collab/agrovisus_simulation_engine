import os
import sys
import gymnasium as gym
import numpy as np
import json
import logging

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.env.agrovisus_env import AgroVisusEnv

def test_random_agent():
    # Setup logging
    logging.basicConfig(level=logging.WARN)
    
    # Mock Config
    config = {
        "simulation_settings": {
            "simulation_days_default": 20,
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
            "hourly_weather_csv": "data/hourly_weather.csv"
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
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    print("Initializing Environment...")
    env = AgroVisusEnv(config=config, project_root=project_root, render_mode="human")
    
    print("Resetting Environment...")
    obs, info = env.reset()
    print(f"Initial Observation: {obs}")
    
    done = False
    total_reward = 0
    steps = 0
    
    print("Starting Episode...")
    while not done:
        action = env.action_space.sample() # Random action
        obs, reward, terminated, truncated, info = env.step(action)
        done = terminated or truncated
        total_reward += reward
        steps += 1
        
        # print(f"Step {steps}: Action={action}, Reward={reward:.2f}, Obs={obs}")
    
    print(f"Episode Finished. Total Steps: {steps}, Total Reward: {total_reward:.2f}")
    assert steps == 20, f"Expected 20 steps, got {steps}"
    print("TEST PASSED")

if __name__ == "__main__":
    test_random_agent()
