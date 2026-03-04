"""
Input validation utilities for AgroVisus models.

Provides validation functions to ensure model inputs and outputs
meet physical constraints and prevent silent failures.
"""
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def validate_positive(value: float, name: str, allow_zero: bool = True) -> float:
    """
    Validate that a value is non-negative.
    
    Args:
        value: The value to validate
        name: Name of the parameter (for error messages)
        allow_zero: Whether zero is acceptable (default: True)
    
    Returns:
        The validated value
        
    Raises:
        ValueError: If value is negative (or zero when not allowed)
    """
    min_val = 0.0 if allow_zero else 0.001
    if value < min_val:
        raise ValueError(
            f"{name} must be >= {min_val}, got {value:.4f}"
        )
    return value


def validate_range(
    value: float,
    min_val: float,
    max_val: float,
    name: str
) -> float:
    """
    Validate that a value is within a specified range.
    
    Args:
        value: The value to validate
        min_val: Minimum acceptable value (inclusive)
        max_val: Maximum acceptable value (inclusive)
        name: Name of the parameter (for error messages)
    
    Returns:
        The validated value
        
    Raises:
        ValueError: If value is outside the range
    """
    if not (min_val <= value <= max_val):
        raise ValueError(
            f"{name} must be in range [{min_val}, {max_val}], got {value:.4f}"
        )
    return value


def validate_water_balance(
    initial_water: float,
    inputs: float,
    outputs: float,
    final_water: float,
    tolerance_mm: float = 1.0,
    context: str = ""
) -> bool:
    """
    Validate that water balance is conserved (mass balance check).
    
    Args:
        initial_water: Initial water content (mm)
        inputs: Total water inputs (precipitation + irrigation, mm)
        outputs: Total water outputs (ET + drainage + percolation, mm)
        final_water: Final water content (mm)
        tolerance_mm: Acceptable error tolerance (default: 1.0 mm)
        context: Description of where this check is being performed
        
    Returns:
        True if balance is valid
        
    Raises:
        ValueError: If water balance is violated beyond tolerance
    """
    expected = initial_water + inputs - outputs
    difference = abs(expected - final_water)
    
    if difference > tolerance_mm:
        error_msg = (
            f"Water balance violation{' in ' + context if context else ''}:\\n"
            f"  Initial: {initial_water:.2f} mm\\n"
            f"  + Inputs: {inputs:.2f} mm\\n"
            f"  - Outputs: {outputs:.2f} mm\\n"
            f"  = Expected: {expected:.2f} mm\\n"
            f"  Actual: {final_water:.2f} mm\\n"
            f"  Difference: {difference:.2f} mm (tolerance: {tolerance_mm} mm)"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    if difference > 0.1:
        # Warn if difference is noticeable but within tolerance
        logger.warning(
            f"Water balance check{' in ' + context if context else ''}: "
            f"{difference:.2f} mm difference (within tolerance)"
        )
    
    return True


def validate_soil_layer_capacity(
    current: float,
    field_capacity: float,
    saturation: float,
    wilting_point: float,
    layer_name: str = "Layer"
) -> bool:
    """
    Validate soil layer water relationships.
    
    Ensures: 0 <= WP <= FC <= SAT and 0 <= current <= SAT
    
    Args:
        current: Current water content (mm)
        field_capacity: Field capacity (mm)
        saturation: Saturation capacity (mm)
        wilting_point: Wilting point (mm)
        layer_name: Name of the layer for error messages
        
    Returns:
        True if valid
        
    Raises:
        ValueError: If relationships are violated
    """
    # Check ordering
    if not (0 <= wilting_point <= field_capacity <= saturation):
        raise ValueError(
            f"{layer_name}: Invalid capacity relationship. "
            f"Must have 0 <= WP ({wilting_point:.2f}) <= "
            f"FC ({field_capacity:.2f}) <= SAT ({saturation:.2f})"
        )
    
    # Check current is valid
    if not (0 <= current <= saturation):
        raise ValueError(
            f"{layer_name}: Current water ({current:.2f} mm) "
            f"must be between 0 and saturation ({saturation:.2f} mm)"
        )
    
    return True


def validate_config_value(
    config: dict,
    key_path: str,
    expected_type: type,
    default: Optional[Any] = None,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None
) -> Any:
    """
    Validate and extract a configuration value with type checking.
    
    Args:
        config: Configuration dictionary
        key_path: Dot-separated path to the value (e.g., "soil_parameters.field_capacity_mm")
        expected_type: Expected Python type
        default: Default value if key not found
        min_val: Minimum value (for numeric types)
        max_val: Maximum value (for numeric types)
        
    Returns:
        The validated configuration value
        
    Raises:
        ValueError: If validation fails and no default provided
    """
    keys = key_path.split('.')
    value = config
    
    try:
        for key in keys:
            value = value[key]
    except (KeyError, TypeError):
        if default is not None:
            logger.warning(f"Config key '{key_path}' not found, using default: {default}")
            return default
        raise ValueError(f"Required config key '{key_path}' not found")
    
    # Type check
    if not isinstance(value, expected_type):
        raise ValueError(
            f"Config key '{key_path}' has wrong type. "
            f"Expected {expected_type.__name__}, got {type(value).__name__}"
        )
    
    # Range check for numeric types
    if isinstance(value, (int, float)):
        if min_val is not None and value < min_val:
            raise ValueError(
                f"Config key '{key_path}' value {value} is below minimum {min_val}"
            )
        if max_val is not None and value > max_val:
            raise ValueError(
                f"Config key '{key_path}' value {value} is above maximum {max_val}"
            )
    
    return value
