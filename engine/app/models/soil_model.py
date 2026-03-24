
from typing import Any, Dict, Optional, List
import logging
from app.utils.validators import validate_positive, validate_soil_layer_capacity, validate_water_balance

logger = logging.getLogger(__name__)

class SoilLayer:
    def __init__(self, depth_mm: float, params: Dict[str, float]):
        # Validate inputs
        validate_positive(depth_mm, "Layer depth", allow_zero=False)
        
        self.depth_mm = depth_mm
        # Hydraulic properties (volumetric)
        self.theta_fc = params["fc"]   # Field Capacity
        self.theta_wp = params["wp"]   # Wilting Point
        self.theta_sat = params["sat"] # Saturation
        
        # Validate hydraulic property relationships (0 <= WP <= FC <= SAT <= 1.0)
        if not (0 <= self.theta_wp <= self.theta_fc <= self.theta_sat <= 1.0):
            raise ValueError(
                f"Invalid soil hydraulic properties. Must have: "
                f"0 <= WP ({self.theta_wp:.3f}) <= FC ({self.theta_fc:.3f}) <= "
                f"SAT ({self.theta_sat:.3f}) <= 1.0"
            )
        
        # Absolute water contents in mm
        self.water_at_fc_mm = self.theta_fc * self.depth_mm
        self.water_at_wp_mm = self.theta_wp * self.depth_mm
        self.water_at_sat_mm = self.theta_sat * self.depth_mm
        self.awc_mm = self.water_at_fc_mm - self.water_at_wp_mm
        
        # State
        self.current_water_mm = self.water_at_fc_mm * 0.8 # Start at 80% FC by default
        
        # Validate calculated values using validator utility
        validate_soil_layer_capacity(
            current=self.current_water_mm,
            field_capacity=self.water_at_fc_mm,
            saturation=self.water_at_sat_mm,
            wilting_point=self.water_at_wp_mm,
            layer_name=f"SoilLayer({depth_mm}mm)"
        )

    def add_water(self, amount_mm: float) -> float:
        """Adds water, returns drainage (excess over saturation)."""
        self.current_water_mm += amount_mm
        drainage = 0.0
        if self.current_water_mm > self.water_at_sat_mm:
            drainage = self.current_water_mm - self.water_at_sat_mm
            self.current_water_mm = self.water_at_sat_mm
        return drainage
    
    def drain_to_field_capacity(self) -> float:
        """Simulates rapid gravity drainage to FC. Returns drained amount."""
        drainage = 0.0
        if self.current_water_mm > self.water_at_fc_mm:
            drainage = self.current_water_mm - self.water_at_fc_mm
            self.current_water_mm = self.water_at_fc_mm
        return drainage

    def remove_water(self, amount_mm: float) -> float:
        """Removes water (ET), clamped to WP. Returns actual extracted."""
        # Plants generally can't extract below WP easily
        available = max(0.0, self.current_water_mm - self.water_at_wp_mm)
        extracted = min(available, amount_mm)
        self.current_water_mm -= extracted
        return extracted
        
    def get_fraction_awc(self) -> float:
        if self.awc_mm <= 0: return 0.0
        avail = max(0.0, self.current_water_mm - self.water_at_wp_mm)
        # Cap at 1.0 for AWC calc (even if super-saturated)
        return min(1.0, avail / self.awc_mm)

class SoilModel:
    def __init__(
        self,
        soil_type_name: str,
        soil_depth_mm: float = 1500.0, # Increased default to 1.5m
        initial_moisture_fraction_awc: float = 0.5,
        custom_soil_params: Optional[Dict[str, Any]] = None,
    ):
        self.soil_type_name = soil_type_name
        self.total_depth_mm = soil_depth_mm
        
        # Default Params if not provided
        if not custom_soil_params:
            # Silt Loam defaults
            custom_soil_params = {"fc": 0.28, "wp": 0.13, "sat": 0.43}
            
        # Define Layers
        # Layer 1: Surface (0-15cm) - Fast dynamics, evaporation zone
        # Layer 2: Subsoil (15-60cm) - Main root zone
        # Layer 3: Deep (60-150cm) - Deep storage
        
        self.layers: List[SoilLayer] = []

        # Depth-proportional three-layer geometry so that the profile always
        # sums exactly to soil_depth_mm, regardless of requested depth.
        #   L1 (surface / evaporation zone): top 25%, capped at 300 mm
        #   L2 (main root zone):             next 50%, capped at 600 mm
        #   L3 (deep storage):               remainder
        l1_depth = min(300.0, soil_depth_mm * 0.25)
        l2_depth = min(600.0, soil_depth_mm * 0.50)
        l3_depth = max(0.0, soil_depth_mm - l1_depth - l2_depth)

        self.layers.append(SoilLayer(l1_depth, custom_soil_params))
        self.layers.append(SoilLayer(l2_depth, custom_soil_params))
        if l3_depth > 0:
            self.layers.append(SoilLayer(l3_depth, custom_soil_params))

        # PAW sanity check for field-scale profiles (>= 800 mm)
        total_paw_mm = sum(l.awc_mm for l in self.layers)
        if soil_depth_mm >= 800:
            assert 150 < total_paw_mm < 400, (
                f"PAW {total_paw_mm:.1f} mm outside expected 150–400 mm for a "
                f"{soil_depth_mm:.0f} mm soil profile. "
                f"Check field_capacity_mm and wilting_point_mm in config."
            )
            
        # Initialize Moisture
        for layer in self.layers:
            # Set to specific fraction AWC
            water_content = layer.water_at_wp_mm + (layer.awc_mm * initial_moisture_fraction_awc)
            layer.current_water_mm = min(layer.water_at_sat_mm, max(layer.water_at_wp_mm, water_content))
            
        self.runoff_mm = 0.0
        self.deep_percolation_mm = 0.0

    def update_daily(
        self,
        precipitation_mm: float,
        irrigation_mm: float,
        et0_mm: float,
        crop_coefficient_kc: float = 1.0,
        root_depth_mm: float = 50.0 # New parameter
    ) -> Dict[str, float]:
        
        # VALIDATION: Track initial water for mass balance check
        initial_total_water = sum(layer.current_water_mm for layer in self.layers)
        
        # 1. Infiltration (Cascading Bucket)
        inflow = precipitation_mm + irrigation_mm
        
        # Add to Layer 1
        drainage = self.layers[0].add_water(inflow)
        
        # Cascade drainage down
        for i in range(1, len(self.layers)):
            if drainage <= 0: break
            drainage = self.layers[i].add_water(drainage)
        
        # Any remaining drainage from bottom layer is saturation excess
        # This becomes runoff or immediate deep percolation
        # For now, we'll add it to deep_percolation (will be set properly later)
        initial_saturation_excess = drainage
            
        # Final drainage from last layer is runoff (if saturation excess) or deep percolation?
        # Actually simplified: Saturation excess usually becomes runoff immediately at surface if Ksat exceeded,
        # but here we treat "bucket overflow" as saturation flow.
        # Let's say overflow from L1 -> L2. Overflow from Bottom -> Deep Percolation.
        # But wait, we also need "Drainage to FC" step (gravity drainage).
        
        # To model "Holding Capacity", we usually allow saturation for a timestep, 
        # then drain everything > FC to the next layer.
        
        # Re-do Cascade for Gravity Drainage
        # The key insight: we need to drain layers from TOP to BOTTOM,
        # but we must ACCUMULATE drainage water and apply it all at once after determining
        # how much can be held.
        
        # Start with any saturation excess from infiltration
        self.deep_percolation_mm = initial_saturation_excess
        
        # Collect drainage from each layer
        layer_drainages = []
        for layer in self.layers:
            drainage = layer.drain_to_field_capacity()
            layer_drainages.append(drainage)
        
        # Now distribute the drained water downwards
        # Start from top layer's drainage
        cascading_water = 0.0
        for i in range(len(self.layers)):
            # This layer drained X amount
            cascading_water += layer_drainages[i]
            
            # Try to put this cascading water into the next layer
            if i < len(self.layers) - 1:
                # There's a layer below
                next_layer = self.layers[i + 1]
                # How much space does the next layer have?
                space = next_layer.water_at_sat_mm - next_layer.current_water_mm
                
                # Add as much as we can
                accepted = min(cascading_water, space)
                next_layer.current_water_mm += accepted
                cascading_water -= accepted
                
                # If there's still cascading water, it will be added to the next iteration
            else:
                # This is the bottom layer, all cascading water becomes deep percolation
                self.deep_percolation_mm += cascading_water
                cascading_water = 0.0  # Reset for clarity
                 
        # 2. Evapotranspiration
        etc_mm = et0_mm * crop_coefficient_kc
        
        # Split ET into Evaporation (Surface) and Transpiration (Roots)
        # Simplified: If crop is small, mostly Evap. If large, mostly Transp.
        # But for compatibility, we just extract `etc_mm` from accessible layers.
        
        remaining_demand = etc_mm
        total_extracted = 0.0
        
        # Calculate accessible layers based on root depth
        current_depth_map = 0.0
        
        # We extract from Top to Bottom (or weighted? roots take from where water is easiest).
        # Simple approach: Extract proportionally from root zone.
        
        accessible_layers = []
        for layer in self.layers:
            layer_top = current_depth_map
            layer_bottom = current_depth_map + layer.depth_mm
            
            # Intersection of layer and root zone
            overlap_top = layer_top
            overlap_bottom = min(layer_bottom, max(root_depth_mm, 100.0)) # Min 100mm for evap
            
            overlap = max(0.0, overlap_bottom - overlap_top)
            if overlap > 0:
                fraction_accessible = overlap / layer.depth_mm
                accessible_layers.append((layer, fraction_accessible))
            
            current_depth_map += layer.depth_mm
            
        # Extraction logic: Try to satisfy demand from accessible layers
        # Weighted by water availability? Or just simple top-down?
        # Top down is risky (dries top too fast).
        # Uniform demand distribution is better.
        
        if len(accessible_layers) > 0:
            demand_per_layer = remaining_demand / len(accessible_layers)
            # First pass: Extract proportionally from each layer
            for layer, frac in accessible_layers:
                got = layer.remove_water(demand_per_layer)
                total_extracted += got
                remaining_demand -= got
                 
            # Second pass: Distribute remaining demand proportionally by available water
            # This prevents over-extraction from a single layer
            if remaining_demand > 0.1:
                # Calculate available water in each accessible layer
                available_water = []
                for layer, frac in accessible_layers:
                    avail = max(0.0, layer.current_water_mm - layer.water_at_wp_mm)
                    available_water.append(avail)
                
                total_available = sum(available_water)
                
                if total_available > 0:
                    # Distribute remaining demand proportionally
                    for (layer, frac), avail in zip(accessible_layers, available_water):
                        proportion = avail / total_available
                        demand_from_layer = remaining_demand * proportion
                        got = layer.remove_water(demand_from_layer)
                        total_extracted += got
                        remaining_demand -= got

        # VALIDATION: Check water balance
        final_total_water = sum(layer.current_water_mm for layer in self.layers)
        total_inputs = precipitation_mm + irrigation_mm
        total_outputs = total_extracted + self.deep_percolation_mm
        
        # Use validation utility with tolerance for numerical errors
        try:
            validate_water_balance(
                initial_water=initial_total_water,
                inputs=total_inputs,
                outputs=total_outputs,
                final_water=final_total_water,
                tolerance_mm=1.0,  # Allow 1mm error for numerical precision
                context="SoilModel.update_daily"
            )
        except ValueError as e:
            # Log error but don't crash the simulation
            logger.error(f"Water balance error: {e}")
            # Optionally: You could raise here in debug mode

        return {
            "runoff_mm": 0.0, # Simplified
            "actual_eta_mm": total_extracted,
            "deep_percolation_mm": self.deep_percolation_mm,
        }

    def get_wfps(self) -> float:
        """
        Water-filled pore space (0–1).

        WFPS = current volumetric water / saturation pore volume
             = sum(layer.current_water_mm) / sum(layer.water_at_sat_mm)

        Saturated when WFPS ≥ 0.90 (anaerobic threshold for BNF suppression).
        """
        total_water = sum(l.current_water_mm for l in self.layers)
        total_sat   = sum(l.water_at_sat_mm   for l in self.layers)
        return min(1.0, total_water / total_sat) if total_sat > 0 else 0.0

    def get_soil_moisture_status(self) -> Dict[str, Any]:
        """
        Returns status. Includes aggregate for validation and per-layer for detail.
        """
        total_water = sum(l.current_water_mm for l in self.layers)
        total_fc = sum(l.water_at_fc_mm for l in self.layers)
        total_wp = sum(l.water_at_wp_mm for l in self.layers)
        total_sat = sum(l.water_at_sat_mm for l in self.layers)
        total_awc = total_fc - total_wp

        avail = max(0.0, total_water - total_wp)
        fraction_awc = avail / total_awc if total_awc > 0 else 0.0
        fraction_awc = min(1.0, fraction_awc)

        # Water-filled pore space: current water / pore volume at saturation
        wfps = round(min(1.0, total_water / total_sat), 3) if total_sat > 0 else 0.0
        
        # Status Category
        if fraction_awc >= 0.75: status = "Wet"
        elif fraction_awc >= 0.35: status = "Moist"
        else: status = "Dry"

        # Layer Details for Dashboard
        layer_details = {}
        for i, layer in enumerate(self.layers):
            layer_details[f"L{i+1}_frac_awc"] = round(layer.get_fraction_awc(), 2)
            layer_details[f"L{i+1}_water_mm"] = round(layer.current_water_mm, 1)

        return {
            "current_water_mm": round(total_water, 2),
            "fraction_awc": round(fraction_awc, 3),
            "wfps": wfps,
            "status_category": status,
            "deep_percolation_mm": round(self.deep_percolation_mm, 2),
            **layer_details,
        }
