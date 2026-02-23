
import os
import sys
import unittest
import json
from datetime import date
import tempfile
import shutil
import pandas as pd
import numpy as np

# Add project root
sys.path.append(os.getcwd())

from app.models.crop_model import CropModel
from app.services.weather_service import WeatherService
from app.utils.exceptions import ConfigValidationError

def test_crop_model_init():
    print("\n--- Testing CropModel Init ---")
    config = {
        "crop_name": "Test Corn",
        "initial_stage": "Emergence",
        "t_base_c": 10.0,
        "n_demand_per_stage": {
            "Emergence": 0.5,
            "Vegetative": 2.0,
            "Flowering": 3.0,
            "Maturity": 1.0
        },
        "water_stress_threshold_awc": 0.5,
        "anaerobic_stress_threshold_awc": 0.9,
        "radiation_use_efficiency_g_mj": 1.5,
        "light_interception_per_stage": {
            "Emergence": 0.1,
            "Vegetative": 0.5,
            "Flowering": 0.9,
            "Maturity": 0.7
        },
        "harvest_index": 0.5,
        "t_upper_c": 30.0,
        "gdd_thresholds": {
            "Emergence": 0,
            "Vegetative": 100,
            "Flowering": 500,
            "Maturity": 1000
        }
    }
    
    try:
        model = CropModel(**config)
        print("CropModel init success")
    except Exception as e:
        print(f"CropModel init failed: {e}")
        import traceback
        traceback.print_exc()

def test_weather_csv_priority():
    print("\n--- Testing Weather CSV Priority ---")
    tmp_dir = tempfile.mkdtemp()
    try:
        csv_path = os.path.join(tmp_dir, "test_weather.csv")
        dates = pd.date_range("2024-06-01", periods=48, freq="h")
        df = pd.DataFrame({
            "datetime": dates,
            "temp_c": 25.0,
            "humidity": 65.0,
            "precip_mm": 0.0,
            "daily_avg_wind_speed_m_s": 2.5,
            "daily_total_solar_rad_mj_m2": 22.0,
        })
        df.set_index("datetime", inplace=True)
        df.to_csv(csv_path)
        
        config = {
            "weather_service": {
                "openweathermap_api_key": "",
                "cache_enabled": False,
                "preferred_source": "csv",
            },
            "historical_data_paths": {"hourly_weather_csv": csv_path},
        }
        
        ws = WeatherService(config)
        data = ws.get_daily_weather(40.0, -88.0, date(2024, 6, 1))
        print(f"Source: {data['source']}")
        
    finally:
        shutil.rmtree(tmp_dir)

if __name__ == "__main__":
    test_crop_model_init()
    test_weather_csv_priority()
