"""
Simulation Facade - Simplified interface for RL environment.

Provides a clean API for the RL environment to interact with the simulation,
hiding internal model structure and reducing coupling.
"""

import logging
from typing import Dict, Any, Optional
from datetime import date

from app.services.simulation_service import SimulationService


class SimulationFacade:
    """
    Facade providing simplified interface to simulation for RL environment.
    
    Hides internal model structure and provides only the operations
    needed by the RL environment.
    """
    
    def __init__(self, simulation_service: SimulationService):
        """
        Initialize facade with simulation service.
        
        Args:
            simulation_service: The underlying simulation service
        """
        self.sim = simulation_service
        self.logger = logging.getLogger(__name__)
    
    # === Crop Information ===
    
    def get_crop_coefficient(self) -> float:
        """
        Get current crop coefficient (Kc) based on growth stage.
        
        Returns:
            Kc value (typically 0.3 to 1.2)
        """
        try:
            crop_status = self.sim.crop_model.get_status()
            current_stage = crop_status.get('current_stage', 'vegetative')
            
            kc_per_stage = self.sim.crop_config_conf.get("kc_per_stage", {})
            kc = kc_per_stage.get(current_stage, 0.7)
            
            return float(kc)
        except Exception as e:
            self.logger.error(f"Error getting crop coefficient: {e}")
            return 0.7  # Default value
    
    def get_crop_root_depth(self) -> float:
        """
        Get current crop root depth in mm.
        
        Returns:
            Root depth in mm
        """
        try:
            crop_status = self.sim.crop_model.get_status()
            return float(crop_status.get('root_depth_mm', 50.0))
        except Exception as e:
            self.logger.error(f"Error getting root depth: {e}")
            return 50.0
    
    def get_crop_status_summary(self) -> Dict[str, Any]:
        """
        Get summary of crop status for observation.
        
        Returns:
            Dictionary with normalized crop metrics
        """
        try:
            status = self.sim.crop_model.get_status()
            return {
                'stage_progress': status.get('stage_progress', 0.0),
                'biomass_normalized': min(status.get('biomass_kg_ha', 0.0) / 10000.0, 1.0),
                'lai': min(status.get('lai', 0.0) / 6.0, 1.0),  # Normalize by max LAI ~6
                'is_alive': status.get('is_alive', True)
            }
        except Exception as e:
            self.logger.error(f"Error getting crop status: {e}")
            return {'stage_progress': 0.0, 'biomass_normalized': 0.0, 'lai': 0.0, 'is_alive': True}
    
    # === Soil Information ===
    
    def get_soil_moisture_fraction(self) -> float:
        """
        Get soil moisture as fraction of available water capacity (AWC).
        
        Returns:
            Fraction (0.0 to 1.0+)
        """
        try:
            soil_status = self.sim.soil_model.get_soil_moisture_status()
            return float(soil_status.get('fraction_awc', 0.5))
        except Exception as e:
            self.logger.error(f"Error getting soil moisture: {e}")
            return 0.5
    
    def is_soil_stressed(self) -> bool:
        """
        Check if soil moisture is in stressed range.
        
        Returns:
            True if stressed, False otherwise
        """
        fraction_awc = self.get_soil_moisture_fraction()
        return fraction_awc < 0.3  # Below 30% AWC is typically stressed
    
    # === Weather Information ===
    
    def get_daily_weather(self, date: date) -> Dict[str, float]:
        """
        Get aggregated weather data for a specific date.
        
        Args:
            date: Date to get weather for
            
        Returns:
            Dictionary with weather variables (or defaults if missing)
        """
        try:
            weather = self.sim.data_manager.get_daily_aggregated_data(date)
            if weather:
                return weather
            else:
                # Return sensible defaults
                return {
                    'total_precip_mm': 0.0,
                    'avg_temp_c': 20.0,
                    'min_temp_c': 15.0,
                    'max_temp_c': 25.0,
                    'avg_humidity': 70.0,
                    'total_solar_rad_mj_m2': 20.0
                }
        except Exception as e:
            self.logger.error(f"Error getting weather data: {e}")
            return {'total_precip_mm': 0.0, 'avg_temp_c': 20.0}
    
    # === Management Actions ===
    
    def apply_irrigation(self, amount_mm: float) -> None:
        """
        Queue irrigation to be applied in next simulation step.
        
        Args:
            amount_mm: Irrigation amount in mm
        """
        # Note: Actual application happens in simulation update
        # This just validates the action
        if amount_mm < 0 or amount_mm > 100:
            self.logger.warning(f"Unusual irrigation amount: {amount_mm} mm")
    
    def apply_fertilizer(self, amount_kg: float, fertilizer_type: str = "Urea") -> None:
        """
        Apply fertilizer to the system.
        
        Args:
            amount_kg: Amount in kg/ha
            fertilizer_type: Type of fertilizer (default: Urea)
        """
        try:
            self.sim.nutrient_model.add_fertilizer(amount_kg, fertilizer_type)
            self.logger.debug(f"Applied {amount_kg} kg/ha of {fertilizer_type}")
        except Exception as e:
            self.logger.error(f"Error applying fertilizer: {e}")
    
    # === Simulation State ===
    
    def get_location_info(self) -> Dict[str, float]:
        """
        Get location information (lat, elevation).
        
        Returns:
            Dictionary with lat and elevation_m
        """
        try:
            return {
                'lat': self.sim.sim_settings_conf.get("latitude_degrees", 40.0),
                'elevation_m': self.sim.sim_settings_conf.get("elevation_m", 100.0)
            }
        except Exception as e:
            self.logger.error(f"Error getting location: {e}")
            return {'lat': 40.0, 'elevation_m': 100.0}
    
    def get_full_state(self) -> Dict[str, Any]:
        """
        Get complete state summary for observation.
        
        Returns:
            Dictionary with all relevant state information
        """
        return {
            'crop': self.get_crop_status_summary(),
            'soil_moisture': self.get_soil_moisture_fraction(),
            'crop_kc': self.get_crop_coefficient(),
            'root_depth': self.get_crop_root_depth()
        }
