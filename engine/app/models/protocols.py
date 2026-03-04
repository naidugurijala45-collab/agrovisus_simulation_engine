"""
Model Protocols - Define interfaces for simulation models.

These protocols define the contract that each model must satisfy,
allowing for type checking and reducing coupling between components.
"""

from typing import Protocol, Dict, Any, Optional


class ICropModel(Protocol):
    """Protocol for crop growth models."""
    
    def update_daily(
        self,
        gdd_today: float,
        swf_today: float,
        anoxia_factor: float,
        par_intercepted: float,
        n_stress_factor: float
    ) -> None:
        """Update crop state for one day."""
        ...
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current crop status.
        
        Returns:
            Dictionary with keys: current_stage, gdd_accumulated, 
            biomass_kg_ha, lai, root_depth_mm, etc.
        """
        ...
    
    def reset(self, initial_stage: Optional[str] = None) -> None:
        """Reset crop to initial state."""
        ...


class ISoilModel(Protocol):
    """Protocol for soil water balance models."""
    
    def update_daily(
        self,
        precipitation_mm: float,
        irrigation_mm: float,
        et0_mm: float,
        crop_coefficient_kc: float,
        root_depth_mm: float
    ) -> Dict[str, float]:
        """
        Update soil water balance for one day.
        
        Returns:
            Dictionary with keys: runoff_mm, actual_eta_mm, deep_percolation_mm
        """
        ...
    
    def get_soil_moisture_status(self) -> Dict[str, Any]:
        """
        Get current soil moisture status.
        
        Returns:
            Dictionary with keys: total_water_mm, fraction_awc, status, etc.
        """
        ...


class INutrientModel(Protocol):
    """Protocol for nutrient cycling models."""
    
    def add_fertilizer(self, amount_kg: float, fertilizer_type: str) -> None:
        """Add fertilizer to the system."""
        ...
    
    def update_daily(
        self,
        crop_n_demand: float,
        root_depth_mm: float,
        soil_water_fraction_awc: float,
        daily_temp_c: float
    ) -> float:
        """
        Update nutrient cycling for one day.
        
        Returns:
            N stress factor (0-1, where 1 is no stress)
        """
        ...
    
    def get_status(self) -> Dict[str, Any]:
        """Get current nutrient status."""
        ...


class IDiseaseModel(Protocol):
    """Protocol for disease pressure models."""
    
    def update_daily(
        self,
        avg_temp_c: float,
        avg_humidity_percent: float,
        precipitation_mm: float,
        leaf_wetness_hours: float
    ) -> None:
        """Update disease pressure for one day."""
        ...
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current disease status.
        
        Returns:
            Dictionary with keys: total_severity, disease_pressures, etc.
        """
        ...


class ISimulationService(Protocol):
    """Protocol for simulation service."""
    
    @property
    def crop_model(self) -> ICropModel:
        """Get crop model instance."""
        ...
    
    @property
    def soil_model(self) -> ISoilModel:
        """Get soil model instance."""
        ...
    
    @property
    def nutrient_model(self) -> INutrientModel:
        """Get nutrient model instance."""
        ...
    
    @property
    def disease_model(self) -> IDiseaseModel:
        """Get disease model instance."""
        ...
    
    def run_simulation(self, days: int) -> Dict[str, Any]:
        """Run simulation for specified number of days."""
        ...
    
    def get_simulation_state(self) -> Dict[str, Any]:
        """Get current state of all models."""
        ...
