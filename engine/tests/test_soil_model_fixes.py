"""
Unit tests for soil model bug fixes.
"""
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from app.models.soil_model import SoilModel, SoilLayer


def test_vanishing_water_bug():
    """
    Test that water doesn't vanish when intermediate layers are saturated.
    
    Scenario: 3-layer soil, L2 is saturated. Add water to L1 causing drainage.
    Expected: Drainage should cascade to L3 or become deep percolation, not disappear.
    """
    print("\n=== Test 1: Vanishing Water Bug ===")
    
    # Create a soil with minimal depth for easy testing
    soil = SoilModel(
        soil_type_name="Test Soil",
        soil_depth_mm=600.0,  # L1=150, L2=450, L3=0 (not created)
        initial_moisture_fraction_awc=0.5
    )
    
    # Manually saturate L2 (index 1)
    soil.layers[1].current_water_mm = soil.layers[1].water_at_sat_mm
    print(f"L2 saturated: {soil.layers[1].current_water_mm:.2f} mm")
    
    # Check initial total water
    initial_total_water = sum(layer.current_water_mm for layer in soil.layers)
    print(f"Initial total water: {initial_total_water:.2f} mm")
    
    # Add heavy rainfall to L1
    heavy_rain_mm = 100.0
    print(f"Adding {heavy_rain_mm} mm of rain...")
    
    # Update soil (no ET for simplicity)
    output = soil.update_daily(
        precipitation_mm=heavy_rain_mm,
        irrigation_mm=0.0,
        et0_mm=0.0,
        crop_coefficient_kc=1.0,
        root_depth_mm=100.0
    )
    
    # Check final total water
    final_total_water = sum(layer.current_water_mm for layer in soil.layers)
    deep_perc = output['deep_percolation_mm']
    
    print(f"Final total water: {final_total_water:.2f} mm")
    print(f"Deep percolation: {deep_perc:.2f} mm")
    
    # Water balance check: initial + input = final + outputs
    expected_final = initial_total_water + heavy_rain_mm - deep_perc
    actual_final = final_total_water
    
    print(f"Expected final water: {expected_final:.2f} mm")
    print(f"Actual final water: {actual_final:.2f} mm")
    print(f"Difference: {abs(expected_final - actual_final):.2f} mm")
    
    # Allow small numerical errors (< 1mm)
    if abs(expected_final - actual_final) < 1.0:
        print("[PASS] Water balance preserved (no vanishing water)")
        return True
    else:
        print(f"[FAIL] Water vanished! Lost {expected_final - actual_final:.2f} mm")
        return False


def test_water_extraction_balance():
    """
    Test that water extraction is balanced across accessible layers.
    
    Scenario: 2-layer soil with equal water. Extract water and verify
    that both layers contribute proportionally.
    """
    print("\n=== Test 2: Water Extraction Balance ===")
    
    # Create soil with equal water in both layers
    soil = SoilModel(
        soil_type_name="Test Soil",
        soil_depth_mm=600.0,
        initial_moisture_fraction_awc=0.7  # Both layers start at 70% AWC
    )
    
    # Record initial state
    initial_l1_water = soil.layers[0].current_water_mm
    initial_l2_water = soil.layers[1].current_water_mm
    
    print(f"Initial L1 water: {initial_l1_water:.2f} mm")
    print(f"Initial L2 water: {initial_l2_water:.2f} mm")
    
    # Apply moderate ET that requires both layers
    et_demand = 15.0  # mm
    print(f"ET demand: {et_demand} mm")
    
    # Update with deep roots (can access both layers)
    output = soil.update_daily(
        precipitation_mm=0.0,
        irrigation_mm=0.0,
        et0_mm=et_demand,
        crop_coefficient_kc=1.0,
        root_depth_mm=600.0  # Access both layers
    )
    
    # Check final state
    final_l1_water = soil.layers[0].current_water_mm
    final_l2_water = soil.layers[1].current_water_mm
    
    l1_extracted = initial_l1_water - final_l1_water
    l2_extracted = initial_l2_water - final_l2_water
    
    print(f"L1 extracted: {l1_extracted:.2f} mm")
    print(f"L2 extracted: {l2_extracted:.2f} mm")
    print(f"Total extracted: {l1_extracted + l2_extracted:.2f} mm")
    print(f"Actual ET: {output['actual_eta_mm']:.2f} mm")
    
    # Check that extraction is reasonably balanced
    # (Shouldn't extract everything from L1 while L2 remains full)
    if l1_extracted > 0 and l2_extracted > 0:
        ratio = l1_extracted / l2_extracted
        print(f"Extraction ratio (L1/L2): {ratio:.2f}")
        
        # Ratio should be reasonable (0.5 to 2.0)
        if 0.5 <= ratio <= 2.0:
            print("[PASS] Extraction is balanced across layers")
            return True
        else:
            print(f"[FAIL] Extraction is unbalanced (ratio: {ratio:.2f})")
            return False
    elif l2_extracted > 0:
        print("[PASS] L2 extracted (not just L1)")
        return True
    else:
        print("[FAIL] Only L1 was extracted")
        return False


def test_gravity_drainage_cascade():
    """
    Test that gravity drainage properly cascades through multiple saturated layers.
    """
    print("\n=== Test 3: Gravity Drainage Cascade ===")
    
    # Create a 3-layer soil (need depth > 600mm)
    soil = SoilModel(
        soil_type_name="Test Soil",
        soil_depth_mm=1500.0,  # L1=150, L2=450, L3=900
        initial_moisture_fraction_awc=0.5
    )
    
    # Saturate all layers
    for i, layer in enumerate(soil.layers):
        layer.current_water_mm = layer.water_at_sat_mm
        print(f"L{i+1} saturated: {layer.current_water_mm:.2f} mm")
    
    initial_total = sum(layer.current_water_mm for layer in soil.layers)
    
    # Add more water on top
    extra_water = 50.0
    print(f"\nAdding {extra_water} mm of extra water to saturated soil...")
    
    output = soil.update_daily(
        precipitation_mm=extra_water,
        irrigation_mm=0.0,
        et0_mm=0.0,
        crop_coefficient_kc=1.0,
        root_depth_mm=100.0
    )
    
    final_total = sum(layer.current_water_mm for layer in soil.layers)
    deep_perc = output['deep_percolation_mm']
    
    print(f"\nDeep percolation: {deep_perc:.2f} mm")
    print(f"Water retained in profile: {final_total - initial_total:.2f} mm")
    
    # When all layers are saturated, extra water should become deep percolation
    expected_deep_perc = extra_water  # All extra should drain out
    
    if abs(deep_perc - expected_deep_perc) < 5.0:  # Allow 5mm tolerance
        print(f"[PASS] Cascading drainage works correctly")
        return True
    else:
        print(f"[FAIL] Expected ~{expected_deep_perc} mm deep perc, got {deep_perc:.2f} mm")
        return False


if __name__ == "__main__":
    print("Running Soil Model Bug Fix Tests...\n")
    
    results = []
    results.append(test_vanishing_water_bug())
    results.append(test_water_extraction_balance())
    results.append(test_gravity_drainage_cascade())
    
    print("\n" + "="*50)
    print(f"Tests Passed: {sum(results)}/{len(results)}")
    
    if all(results):
        print("[PASS] ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("[FAIL] SOME TESTS FAILED")
        sys.exit(1)
