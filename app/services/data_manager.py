# AGROVISUS_SIMULATION_ENGINE/app/services/data_manager.py
import os
import pandas as pd
from datetime import datetime, timedelta, date
import numpy as np
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class DataManager:
    def __init__(self, historical_weather_file: str):
        self.historical_weather_file = self._resolve_path(historical_weather_file)
        self.df_historical_weather = self._load_or_create_weather_data()
    
    def _resolve_path(self, file_path: str) -> str:
        """Resolves a relative path to be based on the project root."""
        # This assumes run.py is in the project root.
        # A more robust solution might use a known project root marker.
        if not os.path.isabs(file_path):
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            return os.path.join(project_root, file_path)
        return file_path

    def _load_or_create_weather_data(self) -> Optional[pd.DataFrame]:
        if not os.path.exists(self.historical_weather_file):
            logger.info(f"Dummy weather file not found. Creating: {self.historical_weather_file}")
            self._create_dummy_hourly_weather_csv_if_not_exists()
        
        if not os.path.exists(self.historical_weather_file):
            logger.critical(f"Dummy weather file could not be created at {self.historical_weather_file}")
            return None
    
        try:
            df = pd.read_csv(
                self.historical_weather_file,
                index_col='datetime',
                parse_dates=True
            )
            logger.info(f"Historical weather data from '{self.historical_weather_file}' loaded. "
                        f"Records: {len(df)}, Date range: {df.index.min()} to {df.index.max()}")
            return df
        except Exception as e:
            logger.critical(f"Failed to load or parse weather data from '{self.historical_weather_file}': {e}", exc_info=True)
            return None

    def _create_dummy_hourly_weather_csv_if_not_exists(self, days=90):
        dir_name = os.path.dirname(self.historical_weather_file)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        
        start_time = datetime.now()
        hourly_data = []
        
        # Pre-calculate daily values to ensure they are constant for each hour of a day
        daily_values = {
            day_num: {
                "solar_rad": np.random.uniform(15.0, 28.0),
                "wind_speed": np.random.uniform(1.5, 3.5)
            } for day_num in range(days)
        }
        
        for i in range(days * 24):
            current_time = start_time + timedelta(hours=i)
            hour_of_day = current_time.hour
            day_index = i // 24
            
            temp = 15 + 10 * np.sin((hour_of_day - 8) * (2 * np.pi / 24)) + np.random.uniform(-1, 1)
            humidity = 70 - 20 * np.sin((hour_of_day - 8) * (2 * np.pi / 24)) + np.random.uniform(-5, 5)
            precip = max(0, np.random.normal(0.1, 0.5)) if np.random.rand() < 0.1 else 0
            
            hourly_data.append({
                'datetime': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                'temp_c': round(temp, 2),
                'humidity': round(max(0, min(100, humidity)), 2),
                'precip_mm': round(precip, 2),
                'daily_total_solar_rad_mj_m2': round(daily_values[day_index]["solar_rad"], 2),
                'daily_avg_wind_speed_m_s': round(daily_values[day_index]["wind_speed"], 2)
            })
        
        df = pd.DataFrame(hourly_data)
        df.to_csv(self.historical_weather_file, index=False)
        logger.info(f"Successfully created dummy data in {self.historical_weather_file}")

    ### MODIFICATION START ###
    def get_hourly_data_for_simulation_day(self, simulation_date: date, lookback_hours: int = 24) -> Optional[pd.DataFrame]:
        """
        Retrieves hourly weather data for a given simulation date.
        The lookback_hours argument is kept for signature consistency but the logic
        returns all data for the specified calendar date.
        """
        if self.df_historical_weather is None or self.df_historical_weather.empty:
            return None
        
        day_data = self.df_historical_weather[self.df_historical_weather.index.date == simulation_date]
        
        if day_data.empty:
            return None
            
        return day_data
    ### MODIFICATION END ###

    def get_daily_aggregated_data(self, simulation_date: date) -> Optional[dict]:
        """
        Calculates daily aggregated weather data from hourly data.
        """
        day_data = self.get_hourly_data_for_simulation_day(simulation_date)
        if day_data is None or day_data.empty:
            return None

        agg_results = {
            'total_precip_mm': day_data['precip_mm'].sum(),
            'avg_temp_c': day_data['temp_c'].mean(),
            'min_temp_c': day_data['temp_c'].min(),
            'max_temp_c': day_data['temp_c'].max(),
            'avg_humidity': day_data['humidity'].mean(),
            'avg_wind_speed_m_s': day_data['daily_avg_wind_speed_m_s'].iloc[0] if not day_data.empty else None,
            'total_solar_rad_mj_m2': day_data['daily_total_solar_rad_mj_m2'].iloc[0] if not day_data.empty else None
        }
        return agg_results