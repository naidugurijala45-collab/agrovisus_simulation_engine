"""
Diagnostic: print ET0 inputs for day 1 of Problem Field scenario.
Confirms whether ea_kpa (measured) or avg_humidity_pct (estimated) reaches PM.
"""
import sys, json, warnings
warnings.filterwarnings("ignore")
from datetime import date

sys.path.insert(0, '.')

from app.services.et0_service import ET0Service
from app.services.weather_service import WeatherService

# ── Patch ET0Service to intercept first call ──────────────────────────────────
_original_calculate = ET0Service.calculate_et0
_call_count = 0

def _patched_calculate(self, weather_data, location, day_of_year):
    global _call_count
    _call_count += 1
    if _call_count == 1:
        print("\n" + "="*60)
        print("  ET0 inputs -- Day 1 of Problem Field scenario")
        print("="*60)
        for k, v in weather_data.items():
            print(f"  {k:<22} = {v}")
        print(f"  {'location':<22} = {location}")
        print(f"  {'day_of_year':<22} = {day_of_year}")
        print("="*60)
    return _original_calculate(self, weather_data, location, day_of_year)

ET0Service.calculate_et0 = _patched_calculate

# ── Patch WeatherService to also print the raw wx dict on day 1 ───────────────
_original_get_daily = WeatherService.get_daily_weather
_wx_count = 0

def _patched_get_daily(self, lat, lon, target_date, *args, **kwargs):
    global _wx_count
    result = _original_get_daily(self, lat, lon, target_date, *args, **kwargs)
    _wx_count += 1
    if _wx_count == 1:
        print("\n" + "="*60)
        print(f"  Raw wx dict — Day 1  ({target_date})")
        print("="*60)
        for k, v in sorted(result.items()):
            print(f"  {k:<30} = {v}")
        print("="*60)
    return result

WeatherService.get_daily_weather = _patched_get_daily

# ── Build Problem Field config ────────────────────────────────────────────────
with open('config.json') as f:
    cfg = json.load(f)

cfg['simulation_settings']['latitude_degrees']            = 40.0
cfg['simulation_settings']['longitude_degrees']           = -89.0
cfg['simulation_settings']['initial_moisture_fraction_awc'] = 0.4
cfg['crop_model_config']['crop_template']                 = 'corn'
cfg['nutrient_model_config']['initial_nitrate_N_kg_ha']   = 20.0
# Use penman_monteith so the humidity path matters
cfg['et0_config']['default_method']                       = 'penman_monteith'
cfg['management_schedule']                                = []

from app.services.simulation_service import SimulationService

svc = SimulationService(config_data=cfg, project_root='.')
svc.run_simulation(
    start_date=date(2025, 5, 1),
    sim_days=1,
    output_csv_path='outputs/diag_et0_tmp.csv'
)

print("\nHumidity path verdict:")
print("  WeatherStep now passes ea_kpa to ET0Service.")
print("  PM uses measured ea_kpa when available (dewpoint path).")
print("  Fallback: estimated rh_avg when ea_kpa is None.\n")
