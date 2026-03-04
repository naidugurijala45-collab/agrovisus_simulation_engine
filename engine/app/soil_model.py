# AGROVISUS_SIMULATION_ENGINE/app/models/soil_model.py

from typing import Any, Dict, Optional

# Predefined soil parameters (example values, units need to be consistent!)
# Volumetric water content (m^3/m^3 or fraction) is common for FC, WP, SAT.
# Depth in mm.
DEFAULT_SOIL_PROFILES = {
    "sandy_loam": {
        "fc": 0.18,  # Field Capacity (m^3/m^3) - water content after drainage
        "wp": 0.08,  # Wilting Point (m^3/m^3) - water content where plants wilt
        "sat": 0.45,  # Saturation (m^3/m^3) - all pores filled
        "description": "Sandy Loam: Drains well, moderate water holding.",
    },
    "clay": {
        "fc": 0.35,
        "wp": 0.20,
        "sat": 0.50,
        "description": "Clay: Holds a lot of water, drains slowly.",
    },
    "silt_loam": {
        "fc": 0.28,
        "wp": 0.12,
        "sat": 0.48,
        "description": "Silt Loam: Good water holding capacity.",
    },
    "black_soil": {  # Example for "black soil" (often rich in organic matter, like a loam or clay loam)
        "fc": 0.30,
        "wp": 0.15,
        "sat": 0.52,
        "description": "Black Soil: Generally fertile, good water retention.",
    },
}


class SoilModel:
    def __init__(
        self,
        soil_type_name: str,
        soil_depth_mm: float = 600.0,
        initial_moisture_fraction_awc: float = 0.5,
        custom_soil_params: Optional[Dict[str, float]] = None,
    ):
        """
        Initializes the SoilModel.
        ... (docstring remains the same) ...
        """
        if custom_soil_params:
            self.params = custom_soil_params
            self.soil_type_name = "custom"
            self.description = custom_soil_params.get(
                "description", "Custom soil profile."
            )
        elif soil_type_name in DEFAULT_SOIL_PROFILES:
            self.params = DEFAULT_SOIL_PROFILES[soil_type_name]
            self.soil_type_name = soil_type_name
            self.description = self.params.get("description", "N/A")
        else:
            raise ValueError(
                f"Soil type '{soil_type_name}' not recognized and no custom_soil_params provided."
            )

        for p in ["fc", "wp", "sat"]:
            if p not in self.params:
                raise ValueError(
                    f"Essential soil parameter '{p}' missing for soil '{self.soil_type_name}'."
                )

        self.soil_depth_mm = float(soil_depth_mm)
        self.theta_fc = float(self.params["fc"])
        self.theta_wp = float(self.params["wp"])
        self.theta_sat = float(self.params["sat"])

        if not (0 < self.theta_wp < self.theta_fc < self.theta_sat < 1.0):
            raise ValueError(
                "Soil hydraulic properties (WP, FC, SAT) are not in the expected order or range."
            )

        self.water_at_wp_mm = self.theta_wp * self.soil_depth_mm
        self.water_at_fc_mm = self.theta_fc * self.soil_depth_mm
        self.water_at_sat_mm = self.theta_sat * self.soil_depth_mm

        self.awc_mm = self.water_at_fc_mm - self.water_at_wp_mm
        if self.awc_mm <= 0:
            raise ValueError(
                "Field Capacity must be greater than Wilting Point, resulting in AWC > 0."
            )

        initial_moisture_fraction_awc = max(
            0.0, min(1.0, initial_moisture_fraction_awc)
        )
        self.current_water_mm = self.water_at_wp_mm + (
            initial_moisture_fraction_awc * self.awc_mm
        )
        self.current_water_mm = max(
            self.water_at_wp_mm, min(self.current_water_mm, self.water_at_sat_mm)
        )

        # print statements in __init__ are removed, as per our cleanup task.

    ### MODIFICATION START ###
    def update_daily(
        self,
        precipitation_mm: float,
        irrigation_mm: float,
        et0_mm: float,
        crop_coefficient_kc: float = 1.0,
    ) -> Dict[str, float]:
        ### MODIFICATION END ###
        """
        Updates the soil moisture based on daily weather and management inputs.

        Args:
            precipitation_mm (float): Daily precipitation in mm.
            irrigation_mm (float): Daily irrigation in mm.
            et0_mm (float): Daily reference evapotranspiration in mm.
            crop_coefficient_kc (float, optional): Crop coefficient to adjust ET0 to ETc.

        Returns:
            dict: A dictionary containing the day's calculated water fluxes.
        """
        if any(
            val < 0
            for val in [precipitation_mm, irrigation_mm, et0_mm, crop_coefficient_kc]
        ):
            # This logic could be replaced with logging in the future.
            # print("Warning (SoilModel): Negative input values are not physical. Clamping to 0.")
            precipitation_mm = max(0, precipitation_mm)
            irrigation_mm = max(0, irrigation_mm)
            et0_mm = max(0, et0_mm)
            crop_coefficient_kc = max(0, crop_coefficient_kc)

        ### MODIFICATION START ###
        # 1. Combine all water inputs for the day
        total_water_input_mm = precipitation_mm + irrigation_mm
        water_after_input = self.current_water_mm + total_water_input_mm
        ### MODIFICATION END ###

        # 2. Account for runoff if water exceeds saturation
        runoff_mm = 0.0
        if water_after_input > self.water_at_sat_mm:
            runoff_mm = water_after_input - self.water_at_sat_mm
            water_after_input = self.water_at_sat_mm

        # 3. Calculate Potential Crop Evapotranspiration (ETc)
        etc_mm = et0_mm * crop_coefficient_kc

        # 4. Calculate Actual Evapotranspiration (ETa)
        available_water_for_et_mm = max(0.0, water_after_input - self.water_at_wp_mm)
        actual_eta_mm = min(etc_mm, available_water_for_et_mm)

        water_after_et = water_after_input - actual_eta_mm

        # 5. Account for deep percolation if water exceeds field capacity
        deep_percolation_mm = 0.0
        if water_after_et > self.water_at_fc_mm:
            deep_percolation_mm = water_after_et - self.water_at_fc_mm
            water_after_et = self.water_at_fc_mm

        # 6. Update current water content
        self.current_water_mm = max(self.water_at_wp_mm, water_after_et)

        ### MODIFICATION START ###
        # 7. Return the daily fluxes
        return {
            "runoff_mm": runoff_mm,
            "actual_eta_mm": actual_eta_mm,
            "deep_percolation_mm": deep_percolation_mm,
        }
        ### MODIFICATION END ###

    def get_soil_moisture_status(self) -> Dict[str, Any]:
        """
        Returns current soil moisture status.
        ... (this method remains unchanged) ...
        """
        if self.awc_mm > 0:
            water_in_awc_range = max(
                0, min(self.current_water_mm, self.water_at_fc_mm) - self.water_at_wp_mm
            )
            fraction_awc = water_in_awc_range / self.awc_mm
        else:
            fraction_awc = 0.0

        fraction_awc = max(0.0, min(1.0, fraction_awc))
        theta_current = (
            self.current_water_mm / self.soil_depth_mm if self.soil_depth_mm > 0 else 0
        )

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
            "awc_total_mm": round(self.awc_mm, 2),
        }


# The `if __name__ == '__main__':` block should be updated to test the new signature.
if __name__ == "__main__":
    print("--- Testing SoilModel Standalone ---")

    print("\nTest Case 1: Sandy Loam")
    sandy_model = SoilModel(
        soil_type_name="sandy_loam",
        soil_depth_mm=500,
        initial_moisture_fraction_awc=0.5,
    )

    print("\nSimulating days for Sandy Loam...")
    daily_inputs = [
        {"P": 10.0, "I": 0.0, "ET0": 3.0, "Kc": 0.7},  # Rain, no irrigation
        {"P": 0.0, "I": 15.0, "ET0": 4.0, "Kc": 0.75},  # No rain, irrigation
        {"P": 25.0, "I": 0.0, "ET0": 1.0, "Kc": 0.8},  # Heavy rain
    ]
    for i, day_input in enumerate(daily_inputs):
        print(
            f"  Day {i + 1} - Input P={day_input['P']}, I={day_input['I']}, ET0={day_input['ET0']}, Kc={day_input['Kc']}"
        )
        fluxes = sandy_model.update_daily(
            precipitation_mm=day_input["P"],
            irrigation_mm=day_input["I"],
            et0_mm=day_input["ET0"],
            crop_coefficient_kc=day_input["Kc"],
        )
        status = sandy_model.get_soil_moisture_status()
        print(
            f"    -> Fluxes: DP={fluxes['deep_percolation_mm']:.1f}mm, Runoff={fluxes['runoff_mm']:.1f}mm, ETa={fluxes['actual_eta_mm']:.1f}mm"
        )
        print(
            f"    -> Status: Water={status['current_water_mm']:.1f}mm, Frac_AWC={status['fraction_awc']:.2f}, Cat='{status['status_category']}'"
        )
