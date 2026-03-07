"""
Unit tests for soil model bug fixes.
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from app.models.soil_model import SoilModel, SoilLayer


def test_vanishing_water_bug():
    """Water must not vanish when intermediate layers are saturated."""
    soil = SoilModel(
        soil_type_name="Test Soil",
        soil_depth_mm=600.0,
        initial_moisture_fraction_awc=0.5
    )
    soil.layers[1].current_water_mm = soil.layers[1].water_at_sat_mm

    initial_total_water = sum(layer.current_water_mm for layer in soil.layers)
    heavy_rain_mm = 100.0

    output = soil.update_daily(
        precipitation_mm=heavy_rain_mm,
        irrigation_mm=0.0,
        et0_mm=0.0,
        crop_coefficient_kc=1.0,
        root_depth_mm=100.0
    )

    final_total_water = sum(layer.current_water_mm for layer in soil.layers)
    deep_perc = output['deep_percolation_mm']
    expected_final = initial_total_water + heavy_rain_mm - deep_perc

    assert abs(expected_final - final_total_water) < 1.0, (
        f"Water balance failed: expected {expected_final:.2f} mm, "
        f"got {final_total_water:.2f} mm (lost {expected_final - final_total_water:.2f} mm)"
    )


def test_water_extraction_balance():
    """ET extraction must draw from all accessible layers, not just L1."""
    soil = SoilModel(
        soil_type_name="Test Soil",
        soil_depth_mm=600.0,
        initial_moisture_fraction_awc=0.7
    )

    initial_l1 = soil.layers[0].current_water_mm
    initial_l2 = soil.layers[1].current_water_mm

    soil.update_daily(
        precipitation_mm=0.0,
        irrigation_mm=0.0,
        et0_mm=15.0,
        crop_coefficient_kc=1.0,
        root_depth_mm=600.0
    )

    l1_extracted = initial_l1 - soil.layers[0].current_water_mm
    l2_extracted = initial_l2 - soil.layers[1].current_water_mm

    assert l2_extracted > 0, "L2 was never extracted — extraction is not balanced across layers"

    if l1_extracted > 0 and l2_extracted > 0:
        ratio = l1_extracted / l2_extracted
        assert 0.5 <= ratio <= 2.0, (
            f"Extraction ratio L1/L2 = {ratio:.2f} is outside acceptable range [0.5, 2.0]"
        )


def test_gravity_drainage_cascade():
    """Extra water on fully saturated soil must all exit as deep percolation."""
    soil = SoilModel(
        soil_type_name="Test Soil",
        soil_depth_mm=1500.0,
        initial_moisture_fraction_awc=0.5
    )
    for layer in soil.layers:
        layer.current_water_mm = layer.water_at_sat_mm

    extra_water = 50.0
    output = soil.update_daily(
        precipitation_mm=extra_water,
        irrigation_mm=0.0,
        et0_mm=0.0,
        crop_coefficient_kc=1.0,
        root_depth_mm=100.0
    )

    deep_perc = output['deep_percolation_mm']
    # On fully saturated soil the gravity-drain step also expels water already above FC,
    # so deep_perc will be >= extra_water. The key invariant is that all extra input exits.
    assert deep_perc >= extra_water - 1.0, (
        f"Expected at least {extra_water} mm deep percolation on saturated soil, got {deep_perc:.2f} mm"
    )
