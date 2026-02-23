# AGROVISUS_SIMULATION_ENGINE/app/utils/leaf_wetness_model.py

from typing import Any, Dict, List


def calculate_leaf_wetness_duration(
    hourly_weather_data: List[Dict[str, Any]],
    rh_threshold: float = 90.0,
    rain_threshold: float = 0.1,
) -> float:
    wet_hours = 0
    if not hourly_weather_data:
        return 0.0

    for hour_data in hourly_weather_data:
        try:
            rh = float(hour_data.get("humidity", 0))
            precip = float(hour_data.get("precip_mm", 0))

            if rh > rh_threshold or precip > rain_threshold:
                wet_hours += 1
        except (ValueError, TypeError) as e:
            print(
                f"Warning: Skipping invalid data point in LWD calculation: {hour_data}. Error: {e}"
            )
            continue

    return float(wet_hours)


if __name__ == "__main__":
    # Example usage:
    mock_data_wet = [
        {"humidity": 95, "precip_mm": 0.0},  # Wet
        {"humidity": 85, "precip_mm": 0.5},  # Wet
        {"humidity": 80, "precip_mm": 0.0},  # Dry
        {"humidity": 92, "precip_mm": 0.0},  # Wet
    ]
    duration = calculate_leaf_wetness_duration(mock_data_wet)
    print(f"Example 1: Calculated LWD: {duration} hours (Expected: 3.0)")

    mock_data_mostly_dry = [
        {"humidity": 80, "precip_mm": 0.0},
        {"humidity": 70, "precip_mm": 0.0},
    ]
    duration_dry = calculate_leaf_wetness_duration(mock_data_mostly_dry)
    print(f"Example 2: Calculated LWD: {duration_dry} hours (Expected: 0.0)")

    mock_data_empty = []
    duration_empty = calculate_leaf_wetness_duration(mock_data_empty)
    print(
        f"Example 3: Calculated LWD with empty data: {duration_empty} hours (Expected: 0.0)"
    )

    mock_data_invalid = [
        {"humidity": "high", "precip_mm": 0.0},
        {"humidity": 90, "precip_mm": "some_rain"},
    ]
    duration_invalid = calculate_leaf_wetness_duration(mock_data_invalid)
    print(
        f"Example 4: Calculated LWD with invalid data: {duration_invalid} hours (Expected: 0.0 with warnings)"
    )
