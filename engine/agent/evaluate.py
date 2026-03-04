"""
Evaluate / Diagnose trained AgroVisus RL agents.

Usage (from agrovisus_simulation_engine/):
    python -m agent.evaluate
"""
import os
import sys
import traceback

from stable_baselines3 import PPO

# Project root is one level up from this file's directory
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from app.env.agrovisus_env import AgroVisusEnv
from app.utils.config_loader import load_config


def diagnose_v3():
    print("--- 🩺 Diagnosing V3 Agent ---")
    config = load_config()

    # Init Env
    env = AgroVisusEnv(config, project_root)

    # Check if we can load model
    model_path = os.path.join(project_root, "models", "ppo", "agrovisus_ppo_v3")

    if not os.path.exists(model_path + ".zip"):
        print(f"❌ Model not found at {model_path}.zip")
        model_path = os.path.join(project_root, "models", "ppo", "agrovisus_ppo_v2")
        if not os.path.exists(model_path + ".zip"):
            print("❌ No models found. Using Random Agent.")
            model = None
        else:
            print(f"⚠️ Falling back to v2: {model_path}")
            model = PPO.load(model_path)
    else:
        print(f"✅ Loaded v3: {model_path}")
        model = PPO.load(model_path)

    obs, _ = env.reset()
    print("\nStarting Episode...")

    total_reward = 0
    headers = ["Day", "Action", "L1(Surf)", "L2(Root)", "H2O_Stress", "Reward", "BioGain"]
    print(f"{headers[0]:<4} {headers[1]:<10} {headers[2]:<8} {headers[3]:<8} {headers[4]:<10} {headers[5]:<8} {headers[6]:<8}")
    print("-" * 70)

    term = False
    trunc = False
    day = 0

    while not (term or trunc):
        if model:
            action, _ = model.predict(obs, deterministic=True)
        else:
            action = env.action_space.sample()

        obs, reward, term, trunc, info = env.step(action)

        # Get detailed state
        soil_st = env.simulation_service.soil_model.get_soil_moisture_status()
        crop_st = env.simulation_service.crop_model.get_status()

        action_name = ["Wait", "Irr_Low", "Irr_High", "Fert"][int(action)]

        print(f"{day:<4} {action_name:<10} {soil_st.get('L1_frac_awc', 0):.2f}     {soil_st.get('L2_frac_awc', 0):.2f}     {crop_st['water_stress_factor']:.2f}       {reward:+.2f}     {crop_st['vegetative_biomass_kg_ha']:.1f}")

        total_reward += reward
        day += 1

        if day > 20 and total_reward < -50:
            print("... (Skipping output for brevity) ...")
            if day > 30:
                break

    print("-" * 70)
    print(f"Episode Finished. Total Reward: {total_reward:.2f}")
    if term:
        print("Result: TERMINATED (Death or Completion)")
    if trunc:
        print("Result: TRUNCATED")


if __name__ == "__main__":
    try:
        diagnose_v3()
    except Exception as e:
        print(f"Crash: {e}")
        traceback.print_exc()
