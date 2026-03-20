"""simulation_pipeline.py — day-level pipeline for the AgroVisus simulation engine.

Step execution order (strict dependency ordering):
  1. ManagementStep      — apply irrigation/fertilizer events to models
  2. WeatherStep         — fetch weather + compute ET₀
  3. SoilStep            — capture pre-update crop state, then update soil water balance
  4. NutrientStep        — N transformations, uptake, NNI-based nitrogen stress
  5. DiseaseStep         — disease pressure update (uses pre-update crop state)
  6. CropStep            — biomass accumulation, stage advance, root growth
  7. RuleEvaluationStep  — evaluate alert rule engine against combined state
  8. ReportingStep       — collect daily output row via ReportingService

State is a mutable DayState dataclass threaded through every step.
Model instances (CropModel, SoilModel, …) live on SimulationService and are
mutated in-place; this file only orchestrates the call sequence.

Architecture note — two parallel systems that do NOT overlap:
  • DiseaseModel (DiseaseStep)   : mechanistic infection model; its
    disease_stress_factor directly reduces daily biomass in CropStep.
  • RuleEvaluator (RuleEvalStep) : pattern-matching alert system; fires
    advisory rules for the farmer (drought, N deficiency, disease risk).
  Both consume the same weather inputs but produce independent outputs
  (float stress vs. advisory dict); no field is computed twice.

ROI is computed at the API layer (backend/routers/simulation.py) after the
run completes — it requires field_acres and commodity price from the request
and does not belong in the engine pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.simulation_service import SimulationService

from app.utils.leaf_wetness_model import calculate_leaf_wetness_duration

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Day state
# ---------------------------------------------------------------------------

@dataclass
class DayState:
    """Mutable state bag for one simulation day, threaded through all steps."""

    sim_date: date
    day_num: int

    # ── Management ──────────────────────────────────────────────────────────
    irrigation_mm: float = 0.0
    fertilization_events: List[Dict[str, Any]] = field(default_factory=list)

    # ── Weather ─────────────────────────────────────────────────────────────
    avg_temp_c: float = 15.0
    min_temp_c: float = 10.0
    max_temp_c: float = 20.0
    precipitation_mm: float = 0.0
    solar_rad_mj_m2: float = 15.0
    avg_humidity_pct: float = 70.0
    wind_speed_ms: float = 2.0
    et0_mm: float = 0.0

    # ── Soil ────────────────────────────────────────────────────────────────
    deep_percolation_mm: float = 0.0
    soil_status: Dict[str, Any] = field(default_factory=dict)

    # ── Pre-update crop state (captured before CropModel.update_daily) ──────
    # Used by SoilStep (kc / root depth) and DiseaseStep (stage / LAI / stress).
    crop_status_pre: Dict[str, Any] = field(default_factory=dict)
    kc_today: float = 0.7

    # ── Nutrients ───────────────────────────────────────────────────────────
    crop_n_demand: float = 0.0
    actual_n_uptake: float = 0.0
    nni: float = 1.0
    n_stress: float = 1.0

    # ── Disease ─────────────────────────────────────────────────────────────
    lwd_hours: float = 0.0          # leaf wetness duration, also used by RuleEvalStep
    disease_status: Dict[str, Any] = field(default_factory=dict)
    disease_stress: float = 1.0

    # ── Post-update crop + nutrient state ───────────────────────────────────
    crop_status: Dict[str, Any] = field(default_factory=dict)
    nutrient_status: Dict[str, Any] = field(default_factory=dict)

    # ── Rules ───────────────────────────────────────────────────────────────
    triggered_rules: List[str] = field(default_factory=list)
    triggered_rule_dicts: List[Dict[str, Any]] = field(default_factory=list)

    # ── Reporting ───────────────────────────────────────────────────────────
    daily_report: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Step base class
# ---------------------------------------------------------------------------

class _Step:
    """Base class for a pipeline step."""

    name: str = "unnamed"

    def run(self, state: DayState, svc: "SimulationService") -> None:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"


# ---------------------------------------------------------------------------
# Step implementations
# ---------------------------------------------------------------------------

class ManagementStep(_Step):
    """Apply irrigation and fertilizer management events for the day."""

    name = "management"

    def run(self, state: DayState, svc: "SimulationService") -> None:
        for event in svc.management_events.get(state.day_num, []):
            etype = event.get("type")
            if etype == "irrigation":
                amount = svc._safe_float(event.get("amount_mm"), 0.0)
                state.irrigation_mm += amount
                svc.logger.info(
                    f"MANAGEMENT EVENT: Applying {amount:.1f} mm irrigation."
                )
            elif etype == "fertilizer":
                amount_n = svc._safe_float(event.get("amount_kg_ha"), 0.0)
                fert_type = event.get("fertilizer_type", "unknown")
                state.fertilization_events.append(
                    {"amount_kg_ha": amount_n, "type": fert_type}
                )
                svc.logger.info(
                    f"MANAGEMENT EVENT: Applying {amount_n:.1f} kg N/ha as {fert_type}."
                )
                svc.nutrient_model.add_fertilizer(amount_n, fert_type)


class WeatherStep(_Step):
    """Fetch daily weather and compute ET₀."""

    name = "weather"

    def run(self, state: DayState, svc: "SimulationService") -> None:
        lat = svc._safe_float(svc.sim_settings_conf.get("latitude_degrees", 40.0))
        lon = svc._safe_float(svc.sim_settings_conf.get("longitude_degrees", 0.0))
        elev = svc._safe_float(svc.sim_settings_conf.get("elevation_m", 100.0))

        wx = svc.weather_service.get_daily_weather(
            lat=lat, lon=lon, target_date=state.sim_date
        )
        state.precipitation_mm = wx.get("total_precip_mm", 0.0)
        state.min_temp_c = wx.get("min_temp_c", 10.0)
        state.max_temp_c = wx.get("max_temp_c", 20.0)
        state.avg_temp_c = wx.get("avg_temp_c", 15.0)
        state.avg_humidity_pct = wx.get("avg_humidity", 70.0)
        state.solar_rad_mj_m2 = wx.get("total_solar_rad_mj_m2", 20.0)
        state.wind_speed_ms = wx.get("avg_wind_speed_m_s", 2.0)

        state.et0_mm = svc.et0_service.calculate_et0(
            weather_data={
                "t_min": state.min_temp_c,
                "t_max": state.max_temp_c,
                "t_avg": state.avg_temp_c,
                "rh_avg": state.avg_humidity_pct,
                "rs_mj_m2": state.solar_rad_mj_m2,
                "u2_m_s": state.wind_speed_ms,
            },
            location={"lat": lat, "elevation_m": elev},
            day_of_year=state.sim_date,
        )


class SoilStep(_Step):
    """Update soil water balance.

    Crop state is captured here (before CropModel.update_daily) because kc and
    root depth must reflect yesterday's stage, not today's potential advance.
    This pre-update snapshot is also consumed by DiseaseStep.
    """

    name = "soil"

    def run(self, state: DayState, svc: "SimulationService") -> None:
        state.crop_status_pre = svc.crop_model.get_status()
        kc_map = svc.crop_config_conf.get("kc_per_stage", {})
        state.kc_today = kc_map.get(
            state.crop_status_pre["current_stage"],
            svc.crop_config_conf.get("kc_fallback", 0.7),
        )
        root_depth = state.crop_status_pre.get("root_depth_mm", 50.0)

        soil_updates = svc.soil_model.update_daily(
            precipitation_mm=state.precipitation_mm,
            irrigation_mm=state.irrigation_mm,
            et0_mm=state.et0_mm,
            crop_coefficient_kc=state.kc_today,
            root_depth_mm=root_depth,
        )
        state.deep_percolation_mm = soil_updates["deep_percolation_mm"]
        state.soil_status = svc.soil_model.get_soil_moisture_status()


class NutrientStep(_Step):
    """Update N transformations, compute uptake, derive NNI-based nitrogen stress.

    NNI uses cumulative plant N uptake vs. Plénet-Lemaire critical-N curve.
    Stress: APSIM floored-quadratic — nni² for NNI 0.5–1.0, floor 0.10 below 0.5.
    """

    name = "nutrients"

    def run(self, state: DayState, svc: "SimulationService") -> None:
        state.crop_n_demand = svc.crop_model.get_daily_n_demand()

        # ── BNF inputs ───────────────────────────────────────────────────────
        # NDS: normalised development stage = accumulated_gdd / max_gdd_at_maturity
        gdd_thresholds = svc.crop_model.gdd_thresholds
        max_gdd = max(gdd_thresholds.values()) if gdd_thresholds else 1500.0
        nds = min(1.0, svc.crop_model.accumulated_gdd / max_gdd) if max_gdd > 0 else 0.0
        # Root DM proxy: ~15% of total biomass, converting kg/ha → g/m² (÷10 × 0.15 = ×0.015)
        root_dm_g_m2 = max(5.0, svc.crop_model.total_biomass_kg_ha * 0.015)

        state.actual_n_uptake = svc.nutrient_model.update_daily(
            state.crop_n_demand,
            state.deep_percolation_mm,
            state.avg_temp_c,
            state.soil_status,
            root_dm_g_m2=root_dm_g_m2,
            soil_temp_25cm=state.avg_temp_c,   # surface air T as soil-T proxy
            nds=nds,
            wfps=None,                          # WFPS not currently tracked in SoilModel
        )

        biomass_Mg_ha = svc.crop_model.total_biomass_kg_ha / 1000.0
        state.nni = svc.nutrient_model.compute_NNI(
            biomass_Mg_ha, svc.nutrient_model.cumulative_N_uptake_kg_ha
        )
        svc.nutrient_model._nni = state.nni

        if state.nni >= 1.0:
            state.n_stress = 1.0
        elif state.nni >= 0.5:
            state.n_stress = state.nni ** 2
        else:
            state.n_stress = max(0.1, state.nni ** 2)


class DiseaseStep(_Step):
    """Update disease pressure models and aggregate worst-case disease status.

    Uses the pre-update crop state (stage, LAI) captured by SoilStep so the
    disease update reflects yesterday's canopy — consistent with Magarey et al.
    infection models.
    """

    name = "disease"

    def run(self, state: DayState, svc: "SimulationService") -> None:
        non_disease_stress = min(
            state.crop_status_pre["nitrogen_stress_factor"],
            state.crop_status_pre["water_stress_factor"],
        )
        hourly_df = svc.data_manager.get_hourly_data_for_simulation_day(state.sim_date)
        hourly_list = hourly_df.to_dict("records") if hourly_df is not None else []
        state.lwd_hours = (
            calculate_leaf_wetness_duration(hourly_list) if hourly_list else 0.0
        )

        for dm in svc.disease_models:
            dm.update_daily(
                daily_weather={"avg_temp_c": state.avg_temp_c},
                hourly_weather=hourly_list,
                crop_growth_stage=state.crop_status_pre["current_stage"],
                crop_lai=state.crop_status_pre.get("lai", 0.0),
                crop_non_disease_stress_factor=non_disease_stress,
            )

        all_states = [dm.get_current_state() for dm in svc.disease_models]
        worst = max(all_states, key=lambda s: s["disease_severity"])
        state.disease_status = {
            "disease_severity": worst["disease_severity"],
            "disease_severity_percent": worst["disease_severity"] * 100,
            "latent_infections": worst["latent_infections"],
            "disease_stress_factor": min(s["disease_stress_factor"] for s in all_states),
        }
        state.disease_stress = state.disease_status["disease_stress_factor"]


class CropStep(_Step):
    """Update biomass, stage, root growth; capture post-update state."""

    name = "crop"

    def run(self, state: DayState, svc: "SimulationService") -> None:
        svc.crop_model.update_daily(
            state.min_temp_c,
            state.max_temp_c,
            state.solar_rad_mj_m2,
            state.actual_n_uptake,
            state.soil_status,
            state.disease_stress,
            nitrogen_stress_override=state.n_stress,
            nni=state.nni,
        )
        state.crop_status = svc.crop_model.get_status()
        state.nutrient_status = svc.nutrient_model.get_status()

        svc.logger.info(
            f"  Crop Status: Stage='{state.crop_status['current_stage']}'"
            f"  GDD={state.crop_status['accumulated_gdd']:.1f}"
            f"  Root={state.crop_status.get('root_depth_mm', 0):.0f}mm"
            f"  Veg/Rep Bio={state.crop_status.get('vegetative_biomass_kg_ha', 0):.1f}"
            f"/{state.crop_status.get('reproductive_biomass_kg_ha', 0):.1f}"
            f"  N-Stress={state.crop_status['nitrogen_stress_factor']:.2f}"
            f"  H2O-Stress={state.crop_status['water_stress_factor']:.2f}"
        )
        svc.logger.info(
            f"  Disease Status: Severity={state.disease_status['disease_severity']:.4f}"
            f"  Stress Factor={state.disease_stress:.2f}"
        )
        svc.logger.info(
            f"  Nutrient Status: Available N={state.nutrient_status['available_N_kg_ha']:.2f} kg/ha"
            f"  (Urea: {state.nutrient_status['urea_N_kg_ha']:.2f}"
            f"  NH4: {state.nutrient_status['ammonium_N_kg_ha']:.2f}"
            f"  NO3: {state.nutrient_status['nitrate_N_kg_ha']:.2f})"
        )
        svc.logger.info(
            f"  Soil: Total AWC={state.soil_status['fraction_awc']:.2f}"
            f"  | L1(0-15cm): {state.soil_status.get('L1_frac_awc', 0):.2f}"
            f"  | L2(15-60cm): {state.soil_status.get('L2_frac_awc', 0):.2f}"
            f"  | DP={state.deep_percolation_mm:.1f}mm"
        )


class RuleEvaluationStep(_Step):
    """Evaluate the alert rule engine against the combined simulation state."""

    name = "rules"

    def run(self, state: DayState, svc: "SimulationService") -> None:
        input_data = {
            "weather": {
                "humidity_percent": float(state.avg_humidity_pct),
                "current_temp_c": float(state.avg_temp_c),
                "leaf_wetness_hours": state.lwd_hours,
            },
            "soil": {**state.soil_status},
            "crop": {**state.crop_status},
            "nutrients": {**state.nutrient_status},
            "disease": {**state.disease_status},
        }
        fired = svc.rule_evaluator.evaluate_rules(input_data) or []
        state.triggered_rule_dicts = fired
        state.triggered_rules = [r["rule_id"] for r in fired]
        for rule in fired:
            svc.logger.info(
                f"--- >>> Rule {rule.get('rule_id')} ('{rule.get('name')}') TRIGGERED <<< ---"
            )


class ReportingStep(_Step):
    """Collect the daily output row via ReportingService."""

    name = "reporting"

    def run(self, state: DayState, svc: "SimulationService") -> None:
        state.daily_report = svc.reporting_service.get_daily_report_data(
            current_date=state.sim_date,
            daily_weather={
                "avg_temp_c": state.avg_temp_c,
                "min_temp_c": state.min_temp_c,
                "max_temp_c": state.max_temp_c,
                "precipitation_mm": state.precipitation_mm,
                "solar_radiation_mj_m2": state.solar_rad_mj_m2,
                "avg_humidity_percent": state.avg_humidity_pct,
                "et0_mm": state.et0_mm,
            },
            daily_irrigation_mm=state.irrigation_mm,
            daily_fertilization_events=state.fertilization_events,
            triggered_rules_for_day=state.triggered_rules,
        )


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------

class SimulationPipeline:
    """Day-level simulation pipeline.

    ``steps`` defines the execution order.  Each step mutates ``state``
    in-place and may read from ``svc`` (the live SimulationService that
    holds all model instances).

    To add a new simulation concern (e.g. carbon accounting), subclass
    ``_Step``, implement ``run(state, svc)``, and insert the instance into
    the ``steps`` list at the correct position.
    """

    steps: List[_Step] = [
        ManagementStep(),
        WeatherStep(),
        SoilStep(),
        NutrientStep(),
        DiseaseStep(),
        CropStep(),
        RuleEvaluationStep(),
        ReportingStep(),
    ]

    def run_day(self, state: DayState, svc: "SimulationService") -> DayState:
        """Run all pipeline steps for one simulation day."""
        for step in self.steps:
            logger.debug("Pipeline step: %s", step.name)
            step.run(state, svc)
        return state
