import logging
from typing import Any, Dict, List

from app.utils.leaf_wetness_model import calculate_leaf_wetness_duration

logger = logging.getLogger(__name__)


class DiseaseModel:
    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the DiseaseModel with parameters from the configuration.
        """
        self.config = config
        self.disease_severity = 0.0  # Initial severity, 0.0 to 1.0 (0% to 100%)
        self.latent_infections = 0.0  # Infections not yet visible
        self.latent_period_days = config.get("latent_period_days", 7)

        # Load disease-specific parameters from config
        self.initial_inoculum = config.get("initial_inoculum", 0.0)
        self.max_severity_rate = config.get(
            "max_severity_rate", 0.05
        )  # Max daily % increase in severity

        # Temperature parameters for disease development
        self.temp_min = config.get("temp_min_c", 10.0)
        self.temp_optimum = config.get("temp_optimum_c", 25.0)
        self.temp_max = config.get("temp_max_c", 35.0)

        # Humidity/Wetness parameters for infection
        self.humidity_threshold = config.get("humidity_threshold_percent", 85.0)
        self.min_precipitation_for_wetness_mm = config.get(
            "min_precipitation_for_wetness_mm", 1.0
        )

        # Crop susceptibility by growth stage (multiplier)
        self.susceptibility_by_stage = config.get("susceptibility_by_stage", {})

        # Initialize severity based on initial inoculum
        if self.initial_inoculum > 0:
            self.disease_severity = self.initial_inoculum
            logger.info(
                f"DiseaseModel initialized with initial inoculum: {self.disease_severity:.4f}"
            )
        else:
            logger.info("DiseaseModel initialized with no initial inoculum.")

    def _calculate_temperature_factor(self, avg_temp_c: float) -> float:
        """
        Calculates a suitability factor (0-1) for disease development based on daily average temperature.
        Uses a triangular function: 0 below min, 1 at optimum, 0 above max.
        """
        if avg_temp_c < self.temp_min or avg_temp_c > self.temp_max:
            return 0.0
        elif self.temp_min <= avg_temp_c <= self.temp_optimum:
            # Linear increase from 0 at min_temp to 1 at opt_temp
            return (avg_temp_c - self.temp_min) / (self.temp_optimum - self.temp_min)
        else:  # self.temp_optimum < avg_temp_c <= self.temp_max
            # Linear decrease from 1 at opt_temp to 0 at max_temp
            return 1.0 - (
                (avg_temp_c - self.temp_optimum) / (self.temp_max - self.temp_optimum)
            )

    def _calculate_wetness_factor(self, hourly_weather: List[Dict[str, Any]]) -> float:
        """
        Calculates suitability factor (0-1) based on actual leaf wetness duration.
        Uses hourly weather data to determine how many hours leaves were wet.
        """
        lwd_hours = calculate_leaf_wetness_duration(
            hourly_weather,
            rh_threshold=self.humidity_threshold,
            rain_threshold=self.min_precipitation_for_wetness_mm,
        )

        # Map leaf wetness duration to disease favorability
        # Many fungal diseases need 6-12 hours of wetness for infection
        if lwd_hours >= 12:
            return 1.0
        elif lwd_hours >= 6:
            return 0.7
        elif lwd_hours >= 4:
            return 0.4
        elif lwd_hours >= 2:
            return 0.2
        else:
            return 0.0

    def _get_crop_susceptibility_factor(self, growth_stage: str) -> float:
        """
        Retrieves a susceptibility multiplier for the current crop growth stage.
        Defaults to 1.0 if the stage is not explicitly defined in the config.
        """
        return self.susceptibility_by_stage.get(growth_stage, 1.0)

    def update_daily(
        self,
        daily_weather: Dict[str, Any],
        hourly_weather: List[Dict[str, Any]],
        crop_growth_stage: str,
        crop_lai: float,  # Not directly used in current simple model, but good to pass for future
        crop_non_disease_stress_factor: float,
    ) -> None:
        """
        Updates the disease severity for the current day based on environmental conditions,
        crop stage, and crop stress.

        Args:
            daily_weather (Dict[str, Any]): Dictionary of daily weather data (avg_temp_c).
            hourly_weather (List[Dict[str, Any]]): List of hourly weather data for leaf wetness calculation.
            crop_growth_stage (str): Current phenological stage of the crop (e.g., "V6", "R1").
            crop_lai (float): Leaf Area Index of the crop. (Currently unused, but useful for future enhancements like canopy microclimate)
            crop_non_disease_stress_factor (float): The combined stress factor from other models (water, nitrogen),
                                                    ranging from 0 (extreme stress) to 1 (no stress).
        """
        avg_temp_c = daily_weather.get("avg_temp_c", 0.0)

        # 1. Determine Environmental Suitability for Disease
        temp_factor = self._calculate_temperature_factor(avg_temp_c)
        wetness_factor = self._calculate_wetness_factor(hourly_weather)
        environmental_factor = temp_factor * wetness_factor

        # If environmental conditions are not suitable, disease does not progress
        if environmental_factor <= 0:
            logger.debug(
                f"DiseaseModel Day Update: No environmental suitability (Env Factor={environmental_factor:.2f}). Severity remains {self.disease_severity:.4f}"
            )
            return  # No change in severity

        # 2. Determine Crop Susceptibility
        stage_susceptibility = self._get_crop_susceptibility_factor(crop_growth_stage)

        # Stressed plants might be more susceptible to disease.
        # If crop_non_disease_stress_factor is 1 (no stress), multiplier is 1.0.
        # If crop_non_disease_stress_factor is 0 (max stress), multiplier is 1.0 + 0.5 = 1.5 (50% more susceptible).
        stress_susceptibility_multiplier = (
            1.0 + (1.0 - crop_non_disease_stress_factor) * 0.5
        )

        total_susceptibility_factor = (
            stage_susceptibility * stress_susceptibility_multiplier
        )
        total_susceptibility_factor = min(
            total_susceptibility_factor, 2.0
        )  # Cap the total multiplier for realism

        # 3. Calculate Potential Daily Disease Increase
        # Calculate inoculum pressure: more disease = more spores = faster spread
        sporulation_threshold = 0.05  # 5% severity needed to produce significant spores
        if self.disease_severity > sporulation_threshold:
            # Exponential growth: existing disease accelerates spread
            inoculum_multiplier = 1.0 + (self.disease_severity * 3.0)
        else:
            # Limited initial inoculum before disease is established
            inoculum_multiplier = 0.1

        # Disease can only spread to healthy tissue.
        healthy_tissue_available = max(0.0, 1.0 - self.disease_severity)

        # The actual daily increase rate is a product of max rate, environmental factors,
        # crop susceptibility, inoculum pressure, and available healthy tissue.
        daily_potential_increase = (
            self.max_severity_rate
            * environmental_factor
            * total_susceptibility_factor
            * inoculum_multiplier
            * healthy_tissue_available
        )

        # 4. Update Disease Severity with Latent Period
        # New infections go into latent pool (not immediately visible)
        self.latent_infections += daily_potential_increase

        # Latent infections emerge after the latent period
        # Simplified: a fraction emerges each day based on latent period length
        emergence_rate = 1.0 / self.latent_period_days
        emerged_severity = self.latent_infections * emergence_rate

        # Update visible disease severity
        self.disease_severity += emerged_severity
        self.latent_infections -= emerged_severity

        # 5. Clamp severity to valid bounds
        self.disease_severity = max(0.0, min(1.0, self.disease_severity))

        logger.debug(
            f"DiseaseModel Day Update: Temp Factor={temp_factor:.2f}, Wetness Factor={wetness_factor:.2f}, "
            f"Env Factor={environmental_factor:.2f}, Susceptibility Factor={total_susceptibility_factor:.2f}, "
            f"Inoculum Multiplier={inoculum_multiplier:.2f}, Daily Increase={daily_potential_increase:.4f}, "
            f"Emerged={emerged_severity:.4f}, Latent={self.latent_infections:.4f}, Visible Severity={self.disease_severity:.4f}"
        )

    def get_disease_stress_factor(self) -> float:
        """
        Calculates the stress factor that the CropModel will use.
        Disease severity directly reduces growth: 50% disease = 50% growth reduction.
        Returns a value between 0.0 (extreme stress) and 1.0 (no stress).
        """
        return max(0.0, 1.0 - self.disease_severity)

    def get_current_state(self) -> Dict[str, Any]:
        """
        Returns a dictionary of the current state variables of the disease model.
        Useful for logging and external access.
        """
        return {
            "disease_severity": self.disease_severity,
            "latent_infections": self.latent_infections,
            "disease_stress_factor": self.get_disease_stress_factor(),
        }
