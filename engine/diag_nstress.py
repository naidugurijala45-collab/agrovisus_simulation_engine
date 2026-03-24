"""Diagnostic: first 30 days NNI + n_factor for Problem Field scenario."""
import sys, json, warnings
warnings.filterwarnings("ignore")
from datetime import date
sys.path.insert(0, '.')
from app.services.simulation_service import SimulationService
from app.models.crop_model import CropModel

# Monkey-patch update_daily to emit diagnostics for first 30 days
_orig = CropModel.update_daily
_day = [0]

def _patched(self, t_min_c, t_max_c, solar_rad_mj_m2, actual_n_uptake_kg_ha,
             soil_status, disease_stress_factor=1.0,
             nitrogen_stress_override=None, nni=1.0):
    _day[0] += 1
    if _day[0] <= 30:
        # Compute n_factor as current code does
        if nni >= 0.9:
            n_factor = self.rue_stress.get("n_moderate", 1.0) if nni < 0.9 else 1.0
        if nni >= 0.9:   n_factor_cur = 1.0
        elif nni >= 0.7: n_factor_cur = self.rue_stress.get("n_moderate", 0.80)
        else:            n_factor_cur = self.rue_stress.get("n_severe", 0.65)

        # What APSIM linear would give:
        if nni >= 1.0:       n_factor_new = 1.0
        elif nni <= 0.4:     n_factor_new = 0.0
        else:                n_factor_new = (nni - 0.4) / 0.6

        rue_veg = getattr(self, 'rue_veg', 3.8)
        rue_eff_cur = rue_veg * n_factor_cur
        rue_eff_new = rue_veg * n_factor_new
        print(f"  Day {_day[0]:3d} | NNI={nni:.3f} | n_factor_cur={n_factor_cur:.3f} "
              f"| n_factor_new={n_factor_new:.3f} | rue_cur={rue_eff_cur:.2f} | rue_new={rue_eff_new:.2f} "
              f"| n_stress={nitrogen_stress_override:.3f}" if nitrogen_stress_override else
              f"  Day {_day[0]:3d} | NNI={nni:.3f} | n_factor_cur={n_factor_cur:.3f} "
              f"| n_factor_new={n_factor_new:.3f} | rue_cur={rue_eff_cur:.2f} | rue_new={rue_eff_new:.2f}")
    return _orig(self, t_min_c, t_max_c, solar_rad_mj_m2, actual_n_uptake_kg_ha,
                 soil_status, disease_stress_factor, nitrogen_stress_override, nni)

CropModel.update_daily = _patched

with open('config.json') as f:
    cfg = json.load(f)
cfg['simulation_settings']['latitude_degrees']  = 40.0
cfg['simulation_settings']['longitude_degrees'] = -89.0
cfg['simulation_settings']['initial_moisture_fraction_awc'] = 0.4
cfg['crop_model_config']['crop_template'] = 'corn'
cfg['nutrient_model_config']['initial_nitrate_N_kg_ha'] = 20.0
cfg['et0_config']['default_method'] = 'hargreaves'
cfg['management_schedule'] = []

print("Day | NNI   | n_factor(cur) | n_factor(new) | rue_eff(cur) | rue_eff(new)")
print("-" * 75)
svc = SimulationService(config_data=cfg, project_root='.')
result = svc.run_simulation(
    start_date=date(2025, 5, 1), sim_days=30,
    output_csv_path='outputs/diag_out.csv'
)
print(f"\nDay-30 biomass: {result.get('total_biomass_kg_ha', 0):,.0f} kg/ha")
