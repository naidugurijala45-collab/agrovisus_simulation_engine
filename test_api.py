"""
Quick integration test - POST simulation request and print key results.
Run from CropDiagnosisPlatform/ directory.
"""
import sys
import urllib.request
import urllib.error
import json

BASE = "http://localhost:8000"


def post_json(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def main():
    # 1. Health check
    print("=== 1. Health Check ===")
    try:
        with urllib.request.urlopen(f"{BASE}/api/health", timeout=5) as r:
            print(json.loads(r.read().decode()))
    except Exception as e:
        print(f"  FAILED: {e}")
        print("  Is the backend running? Start with:")
        print("    python -m uvicorn backend.main:app --port 8000 --reload")
        sys.exit(1)

    # 2. Crop templates
    print("\n=== 2. Crop Templates ===")
    try:
        with urllib.request.urlopen(f"{BASE}/api/crops/templates", timeout=10) as r:
            data = json.loads(r.read().decode())
            templates = data.get("templates", [])
            print(f"  Found {len(templates)} templates: {[t['id'] for t in templates]}")
    except Exception as e:
        print(f"  FAILED: {e}")

    # 3. Run Simulation
    print("\n=== 3. Simulation (corn, 30 days) ===")
    payload = {
        "crop_template": "corn",
        "sim_days": 30,
        "latitude": 40.0,
        "longitude": -88.0,
        "elevation_m": 100.0,
        "management_schedule": []
    }
    try:
        result = post_json(f"{BASE}/api/simulation/run", payload)
        print("  PASS - Simulation complete!")
        print(f"  Total Biomass:    {result['total_biomass_kg_ha']:.1f} kg/ha")
        print(f"  Final Yield:      {result['final_yield_kg_ha']:.1f} kg/ha")
        print(f"  Total Irrigation: {result['total_irrigation_mm']:.1f} mm")
        print(f"  Max Disease:      {result['max_disease_severity']:.2f}%")
        print(f"  Daily data rows:  {len(result['daily_data'])}")
        print(f"  Triggered rules:  {len(result['triggered_rules'])}")
        if result['daily_data']:
            d = result['daily_data'][0]
            print(f"\n  Day 1 sample:")
            print(f"    Stage:    {d['crop_stage']}")
            print(f"    Biomass:  {d['biomass_kg_ha']:.2f} kg/ha")
            print(f"    Moisture: {d['soil_moisture']:.3f}")
            print(f"    Temp:     {d['avg_temp_c']:.1f} C")
            print(f"    Precip:   {d['precipitation_mm']:.1f} mm")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  FAILED HTTP {e.code}: {body}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  FAILED: {e}")


if __name__ == "__main__":
    main()
