"""
Tests for crop template loading, validation, and integration.

Covers:
- Loading all 5 templates
- Validation of parameter ranges
- Template + override merging
- CropModel initialization from templates
- Error handling for bad templates
"""
import os
import sys
import json
import copy

import pytest

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from app.utils.crop_template_loader import CropTemplateLoader
from app.models.crop_model import CropModel
from app.utils.exceptions import ConfigValidationError


# ── Template Loading Tests ────────────────────────────────────


class TestTemplateLoading:

    def test_loader_initializes(self):
        loader = CropTemplateLoader()
        assert len(loader.list_available_crops()) >= 5

    def test_list_crops(self):
        loader = CropTemplateLoader()
        crops = loader.list_available_crops()
        assert "corn" in crops
        assert "wheat" in crops
        assert "rice" in crops
        assert "soybean" in crops
        assert "sorghum" in crops

    def test_load_each_template(self):
        """V2 templates nest growth params under 'growth' key."""
        loader = CropTemplateLoader()
        for crop in loader.list_available_crops():
            template = loader.load_template(crop)
            assert "crop_name" in template
            growth = template["growth"]
            assert "gdd_thresholds" in growth
            assert "t_base_c" in growth
            assert "harvest_index" in growth
            assert "initial_stage" in growth

    def test_template_is_deep_copy(self):
        loader = CropTemplateLoader()
        t1 = loader.load_template("corn")
        t2 = loader.load_template("corn")
        t1["growth"]["t_base_c"] = 999
        assert t2["growth"]["t_base_c"] != 999

    def test_unknown_crop_raises(self):
        loader = CropTemplateLoader()
        with pytest.raises(ConfigValidationError) as exc_info:
            loader.load_template("banana_tree")
        assert "banana_tree" in str(exc_info.value)
        assert "Available" in exc_info.value.suggestion

    def test_case_insensitive(self):
        loader = CropTemplateLoader()
        t = loader.load_template("Corn")
        assert t["crop_name"] == "Corn (Maize)"

    def test_v2_sections_present(self):
        """V2 templates include soil, irrigation, nutrients, diseases."""
        loader = CropTemplateLoader()
        for crop in loader.list_available_crops():
            template = loader.load_template(crop)
            assert "soil" in template, f"{crop} missing soil"
            assert "irrigation" in template, f"{crop} missing irrigation"
            assert "nutrients" in template, f"{crop} missing nutrients"
            assert "diseases" in template, f"{crop} missing diseases"
            assert len(template["diseases"]) >= 1


# ── Template Validation Tests ─────────────────────────────────


class TestTemplateValidation:

    def test_all_templates_pass_validation(self):
        """merge_with_overrides flattens and validates."""
        loader = CropTemplateLoader()
        for crop in loader.list_available_crops():
            config = loader.merge_with_overrides(crop, {})
            warnings = loader.validate_crop_config(config)
            # Warnings are OK, errors would raise

    def test_missing_required_field_raises(self):
        loader = CropTemplateLoader()
        bad_config = {"crop_name": "Bad Crop"}
        with pytest.raises(ConfigValidationError):
            loader.validate_crop_config(bad_config)

    def test_bad_initial_stage_raises(self):
        loader = CropTemplateLoader()
        config = loader.merge_with_overrides("corn", {})
        config["initial_stage"] = "NonExistentStage"
        with pytest.raises(ConfigValidationError):
            loader.validate_crop_config(config)

    def test_gdd_monotonicity_warning(self):
        loader = CropTemplateLoader()
        config = loader.merge_with_overrides("corn", {})
        # Break monotonicity
        stages = list(config["gdd_thresholds"].keys())
        config["gdd_thresholds"][stages[1]] = 9999
        warnings = loader.validate_crop_config(config)
        assert any("not increasing" in w for w in warnings)


# ── Merge Override Tests ──────────────────────────────────────


class TestMergeOverrides:

    def test_scalar_override(self):
        loader = CropTemplateLoader()
        overrides = {"t_base_c": 8.0, "crop_template": "corn"}
        result = loader.merge_with_overrides("corn", overrides)
        assert result["t_base_c"] == 8.0

    def test_dict_merge(self):
        loader = CropTemplateLoader()
        overrides = {"gdd_thresholds": {"VE": 10}}
        result = loader.merge_with_overrides("corn", overrides)
        # VE should be overridden
        assert result["gdd_thresholds"]["VE"] == 10
        # Other stages should remain from template
        assert result["gdd_thresholds"]["V2"] == 120

    def test_override_preserves_template_fields(self):
        loader = CropTemplateLoader()
        overrides = {"harvest_index": 0.55}
        result = loader.merge_with_overrides("corn", overrides)
        assert result["harvest_index"] == 0.55
        # Template fields should still exist
        assert "max_root_depth_mm" in result
        assert "daily_root_growth_rate_mm" in result


# ── CropModel Integration Tests ──────────────────────────────


class TestCropModelFromTemplate:

    def _make_model(self, config):
        """Create a CropModel from a flattened config dict."""
        return CropModel(
            initial_stage=config["initial_stage"],
            gdd_thresholds=config["gdd_thresholds"],
            t_base_c=config["t_base_c"],
            t_upper_c=config.get("t_upper_c"),
            n_demand_per_stage=config["N_demand_kg_ha_per_stage"],
            water_stress_threshold_awc=config.get("water_stress_threshold_awc", 0.5),
            anaerobic_stress_threshold_awc=config.get("anaerobic_stress_threshold_awc", 0.95),
            radiation_use_efficiency_g_mj=config["radiation_use_efficiency_g_mj"],
            light_interception_per_stage=config["light_interception_per_stage"],
            harvest_index=config["harvest_index"],
            max_root_depth_mm=config.get("max_root_depth_mm", 1200),
            daily_root_growth_rate_mm=config.get("daily_root_growth_rate_mm", 15),
            vegetative_stages=config.get("vegetative_stages"),
            reproductive_stages=config.get("reproductive_stages"),
        )

    def test_corn_model_init(self):
        loader = CropTemplateLoader()
        config = loader.merge_with_overrides("corn", {})
        model = self._make_model(config)
        assert model.current_stage == "VE"
        assert model.max_root_depth_mm == 1200.0

    def test_all_templates_create_valid_models(self):
        loader = CropTemplateLoader()
        for crop in loader.list_available_crops():
            config = loader.merge_with_overrides(crop, {})
            model = self._make_model(config)
            status = model.get_status()
            assert status["current_stage"] == config["initial_stage"]

    def test_bad_harvest_index_rejected(self):
        loader = CropTemplateLoader()
        config = loader.merge_with_overrides("corn", {})
        config["harvest_index"] = 1.5  # Invalid
        with pytest.raises(ConfigValidationError):
            self._make_model(config)

    def test_root_params_from_template(self):
        loader = CropTemplateLoader()
        config = loader.merge_with_overrides("rice", {})
        model = self._make_model(config)
        # Rice has shallow roots (600mm) vs corn default (1200mm)
        assert model.max_root_depth_mm == 600.0

    def test_vegetative_stages_from_template(self):
        loader = CropTemplateLoader()
        config = loader.merge_with_overrides("corn", {})
        model = self._make_model(config)
        assert "VE" in model.vegetative_stages
        assert "V6" in model.vegetative_stages
        assert "R1" not in model.vegetative_stages


# ── New V2 Accessor Tests ────────────────────────────────────


class TestV2Accessors:

    def test_get_soil_defaults(self):
        loader = CropTemplateLoader()
        soil = loader.get_soil_defaults("corn")
        assert "field_capacity_mm" in soil
        assert "wilting_point_mm" in soil
        assert soil["preferred_type"] == "Silt Loam"

    def test_get_diseases(self):
        loader = CropTemplateLoader()
        diseases = loader.get_diseases("corn")
        assert len(diseases) >= 2
        assert diseases[0]["id"] == "nclb"
        assert "susceptibility_by_stage" in diseases[0]

    def test_get_irrigation_strategy(self):
        loader = CropTemplateLoader()
        irrigation = loader.get_irrigation_strategy("rice")
        assert irrigation["strategy"] == "flooded"
        assert irrigation["method"] == "flood"

    def test_get_nutrient_schedule(self):
        loader = CropTemplateLoader()
        nutrients = loader.get_nutrient_schedule("soybean")
        assert nutrients["total_N_kg_ha"] == 40.0
        assert len(nutrients["application_schedule"]) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
