"""Run both demo scenarios and report yield, yield gap, and alert counts."""
import sys, json, warnings
warnings.filterwarnings("ignore")
from datetime import date
sys.path.insert(0, '.')
from app.services.simulation_service import SimulationService

def run_scenario(label, no3_kg_ha, awc, management):
    with open('config.json') as f:
        cfg = json.load(f)
    cfg['simulation_settings']['latitude_degrees']  = 40.0
    cfg['simulation_settings']['longitude_degrees'] = -89.0
    cfg['simulation_settings']['initial_moisture_fraction_awc'] = awc
    cfg['crop_model_config']['crop_template'] = 'corn'
    cfg['nutrient_model_config']['initial_nitrate_N_kg_ha'] = no3_kg_ha
    cfg['et0_config']['default_method'] = 'hargreaves'
    cfg['management_schedule'] = management

    svc = SimulationService(config_data=cfg, project_root='.')
    result = svc.run_simulation(
        start_date=date(2025, 5, 1), sim_days=120,
        output_csv_path='outputs/verify_tmp.csv'
    )

    biomass = result.get('total_biomass_kg_ha', 0)
    # Corn harvest index 0.5 → grain yield; 1 Mg/ha = 15.92 bu/acre
    grain_kg_ha = result.get('final_yield_kg_ha', 0) or biomass * 0.5
    bu_acre = grain_kg_ha / 62.77  # 1 bu corn = 25.4 kg → 1 kg/ha = 1/62.77 bu/acre...
    # Actually: 1 bu/acre corn = 62.77 kg/ha. So bu/acre = kg/ha / 62.77

    rules = result.get('triggered_rules', [])
    high_count = 0
    mod_count = 0
    for day_entry in rules:
        for rule in day_entry.get('rules', []):
            sev = rule.get('severity', '').lower()
            if sev == 'high':   high_count += 1
            elif sev == 'moderate': mod_count += 1

    print(f"\n{'='*55}")
    print(f"  {label}")
    print(f"{'='*55}")
    print(f"  Biomass:       {biomass:>10,.0f} kg/ha")
    print(f"  Grain yield:   {grain_kg_ha:>10,.0f} kg/ha  ({bu_acre:>6.1f} bu/acre)")
    print(f"  HIGH alerts:   {high_count}")
    print(f"  MOD alerts:    {mod_count}")
    return bu_acre

print("\nRunning Problem Field  (10 ppm N, no fertilizer, dry soil)...")
y1 = run_scenario(
    "PROBLEM FIELD — Drought + N Deficiency",
    no3_kg_ha=20.0,   # 10 ppm × 2
    awc=0.4,
    management=[]
)

print("\nRunning Well-Managed Field  (45 ppm N, day-7 urea, normal soil)...")
y2 = run_scenario(
    "WELL-MANAGED FIELD — Optimal Management",
    no3_kg_ha=90.0,   # 45 ppm × 2
    awc=0.85,
    management=[{"day": 7, "type": "fertilizer", "amount_kg_ha": 120, "fertilizer_type": "urea"}]
)

gap = y2 - y1
print(f"\n{'='*55}")
print(f"  Yield gap: {gap:.1f} bu/acre")
print(f"  ROI at $4.50/bu × 100 acres: ${gap * 4.5 * 100:,.0f}")
print(f"{'='*55}\n")
