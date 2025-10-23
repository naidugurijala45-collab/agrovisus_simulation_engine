# AGROVISUS_SIMULATION_ENGINE/app/models/soil_model.py

from typing import Dict, Any, Optional

class SoilModel:
    def __init__(self,
                 soil_type_name: str,  # <<< THIS IS THE REQUIRED PARAMETER THAT WAS MISSING
                 soil_depth_mm: float = 600.0,
                 initial_moisture_fraction_awc: float = 0.5,
                 custom_soil_params: Optional[Dict[str, Any]] = None):
        """
        Initializes the SoilModel.
        """
        if custom_soil_params:
            self.params = custom_soil_params
            self.soil_type_name = custom_soil_params.get("description", "custom")
            self.description = custom_soil_params.get("description", "Custom soil profile.")
        else:
            # This part is now less likely to be used since run.py always sends custom params,
            # but it's good practice to keep it for standalone use.
            raise ValueError(f"Soil type '{soil_type_name}' not recognized and no custom_soil_params provided.")

        for p in ["fc", "wp", "sat"]:
            if p not in self.params:
                raise ValueError(f"Essential soil parameter '{p}' missing for soil '{self.soil_type_name}'.")

        self.soil_depth_mm = float(soil_depth_mm)
        self.theta_fc = float(self.params["fc"])
        self.theta_wp = float(self.params["wp"])
        self.theta_sat = float(self.params["sat"])

        if not (0 < self.theta_wp < self.theta_fc < self.theta_sat < 1.0):
            raise ValueError("Soil hydraulic properties (WP, FC, SAT) are not in the expected order or range.")

        self.water_at_wp_mm = self.theta_wp * self.soil_depth_mm
        self.water_at_fc_mm = self.theta_fc * self.soil_depth_mm
        self.water_at_sat_mm = self.theta_sat * self.soil_depth_mm
        
        self.awc_mm = self.water_at_fc_mm - self.water_at_wp_mm
        if self.awc_mm <= 0:
            raise ValueError("Field Capacity must be greater than Wilting Point, resulting in AWC > 0.")

        initial_moisture_fraction_awc = max(0.0, min(1.0, initial_moisture_fraction_awc))
        self.current_water_mm = self.water_at_wp_mm + (initial_moisture_fraction_awc * self.awc_mm)
        self.current_water_mm = max(self.water_at_wp_mm, min(self.current_water_mm, self.water_at_sat_mm))

    def update_daily(self,
                     precipitation_mm: float,
                     irrigation_mm: float,
                     et0_mm: float,
                     crop_coefficient_kc: float = 1.0) -> Dict[str, float]:
        """
        Updates the soil moisture based on daily weather and management inputs.
        """
        if any(val < 0 for val in [precipitation_mm, irrigation_mm, et0_mm, crop_coefficient_kc]):
            precipitation_mm = max(0, precipitation_mm)
            irrigation_mm = max(0, irrigation_mm)
            et0_mm = max(0, et0_mm)
            crop_coefficient_kc = max(0, crop_coefficient_kc)
        
        total_water_input_mm = precipitation_mm + irrigation_mm
        water_after_input = self.current_water_mm + total_water_input_mm
        
        runoff_mm = 0.0
        if water_after_input > self.water_at_sat_mm:
            runoff_mm = water_after_input - self.water_at_sat_mm
            water_after_input = self.water_at_sat_mm
            
        etc_mm = et0_mm * crop_coefficient_kc
        available_water_for_et_mm = max(0.0, water_after_input - self.water_at_wp_mm)
        actual_eta_mm = min(etc_mm, available_water_for_et_mm)
        water_after_et = water_after_input - actual_eta_mm
        
        deep_percolation_mm = 0.0
        if water_after_et > self.water_at_fc_mm:
            deep_percolation_mm = water_after_et - self.water_at_fc_mm
            water_after_et = self.water_at_fc_mm
            
        self.current_water_mm = max(self.water_at_wp_mm, water_after_et)
        
        return {
            "runoff_mm": runoff_mm,
            "actual_eta_mm": actual_eta_mm,
            "deep_percolation_mm": deep_percolation_mm,
        }

    def get_soil_moisture_status(self) -> Dict[str, Any]:
        """
        Returns current soil moisture status.
        """
        if self.awc_mm > 0:
            water_in_awc_range = max(0, min(self.current_water_mm, self.water_at_fc_mm) - self.water_at_wp_mm)
            fraction_awc = water_in_awc_range / self.awc_mm
        else:
            fraction_awc = 0.0 
        
        fraction_awc = max(0.0, min(1.0, fraction_awc))
        theta_current = self.current_water_mm / self.soil_depth_mm if self.soil_depth_mm > 0 else 0

        if fraction_awc >= 0.75:
            status_category = "Wet"
        elif fraction_awc >= 0.35:
            status_category = "Moist"
        else:
            status_category = "Dry"

        return {
            "current_water_mm": round(self.current_water_mm, 2),
            "theta_current_volumetric": round(theta_current, 3),
            "fraction_awc": round(fraction_awc, 3),
            "status_category": status_category,
            "water_at_wp_mm": round(self.water_at_wp_mm, 2),
            "water_at_fc_mm": round(self.water_at_fc_mm, 2),
            "water_at_sat_mm": round(self.water_at_sat_mm, 2),
            "awc_total_mm": round(self.awc_mm, 2)
        }

if __name__ == '__main__':
    # ... standalone test block ...
    pass