"""
Unit tests for validation utilities.
"""
import sys
import os

import pytest

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from app.utils.validators import (
    validate_positive,
    validate_range,
    validate_water_balance,
    validate_soil_layer_capacity,
    validate_config_value
)


def test_validate_positive_valid():
    """Test that positive validation accepts valid values."""
    assert validate_positive(5.0, "test") == 5.0
    assert validate_positive(0.0, "test") == 0.0
    assert validate_positive(0.001, "test", allow_zero=False) == 0.001


def test_validate_positive_invalid():
    """Test that positive validation rejects invalid values."""
    with pytest.raises(ValueError, match="must be >= 0"):
        validate_positive(-1.0, "test")
    
    with pytest.raises(ValueError, match="must be >= 0.001"):
        validate_positive(0.0, "test", allow_zero=False)


def test_validate_range_valid():
    """Test that range validation accepts valid values."""
    assert validate_range(5.0, 0.0, 10.0, "test") == 5.0
    assert validate_range(0.0, 0.0, 10.0, "test") == 0.0
    assert validate_range(10.0, 0.0, 10.0, "test") == 10.0


def test_validate_range_invalid():
    """Test that range validation rejects invalid values."""
    with pytest.raises(ValueError, match="must be in range"):
        validate_range(-1.0, 0.0, 10.0, "test")
    
    with pytest.raises(ValueError, match="must be in range"):
        validate_range(11.0, 0.0, 10.0, "test")


def test_validate_water_balance_valid():
    """Test water balance validation with valid inputs."""
    # Perfect balance
    assert validate_water_balance(
        initial_water=100.0,
        inputs=50.0,
        outputs=30.0,
        final_water=120.0,
        context="test"
    )
    
    # Within tolerance
    assert validate_water_balance(
        initial_water=100.0,
        inputs=50.0,
        outputs=30.0,
        final_water=120.5,  # 0.5mm error
        tolerance_mm=1.0,
        context="test"
    )


def test_validate_water_balance_invalid():
    """Test water balance validation with invalid inputs."""
    with pytest.raises(ValueError, match="Water balance violation"):
        validate_water_balance(
            initial_water=100.0,
            inputs=50.0,
            outputs=30.0,
            final_water=110.0,  # Should be 120, 10mm error
            tolerance_mm=1.0,
            context="test"
        )


def test_validate_soil_layer_capacity_valid():
    """Test soil layer capacity validation with valid inputs."""
    assert validate_soil_layer_capacity(
        current=80.0,
        field_capacity=100.0,
        saturation=150.0,
        wilting_point=40.0
    )


def test_validate_soil_layer_capacity_invalid_ordering():
    """Test soil layer capacity validation with invalid ordering"""
    with pytest.raises(ValueError, match="Invalid capacity relationship"):
        validate_soil_layer_capacity(
            current=80.0,
            field_capacity=150.0,  # FC > SAT is wrong!
            saturation=100.0,
            wilting_point=40.0
        )


def test_validate_soil_layer_capacity_invalid_current():
    """Test soil layer capacity validation with invalid current water."""
    with pytest.raises(ValueError, match="must be between"):
        validate_soil_layer_capacity(
            current=200.0,  # Over saturation!
            field_capacity=100.0,
            saturation=150.0,
            wilting_point=40.0
        )


def test_validate_config_value_valid():
    """Test config value extraction and validation."""
    config = {
        "soil": {
            "depth_mm": 600.0
        }
    }
    
    value = validate_config_value(config, "soil.depth_mm", float)
    assert value == 600.0


def test_validate_config_value_with_range():
    """Test config value with range validation."""
    config = {
        "economics": {
            "price": 0.05
        }
    }
    
    value = validate_config_value(
        config,
        "economics.price",
        float,
        min_val=0.0,
        max_val=1.0
    )
    assert value == 0.05


def test_validate_config_value_missing_with_default():
    """Test config value extraction with default."""
    config = {}
    
    value = validate_config_value(
        config,
        "missing.key",
        float,
        default=10.0
    )
    assert value == 10.0


def test_validate_config_value_missing_without_default():
    """Test config value extraction raises error when missing."""
    config = {}
    
    with pytest.raises(ValueError, match="not found"):
        validate_config_value(config, "missing.key", float)


if __name__ == "__main__":
    print("Running validator tests...")
    print("Note: Install pytest and run 'pytest tests/test_validators.py' for full test suite")
    
    # Run a few simple tests manually
    try:
        test_validate_positive_valid()
        print("✓ validate_positive works")
        
        test_validate_range_valid()
        print("✓ validate_range works")
        
        test_validate_water_balance_valid()
        print("✓ validate_water_balance works")
        
        test_validate_soil_layer_capacity_valid()
        print("✓ validate_soil_layer_capacity works")
        
        print("\nAll manual tests passed!")
    except Exception as e:
        print(f"✗ Test failed: {e}")
        raise
