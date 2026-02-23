import os
import sys
import gymnasium as gym
from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.callbacks import EvalCallback, StopTrainingOnRewardThreshold
from stable_baselines3.common.vec_env import DummyVecEnv

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)

from app.env.agrovisus_env import AgroVisusEnv

from app.utils.config_loader import load_config

def train():
    log_dir = "logs"
    models_dir = "models/ppo"
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(models_dir, exist_ok=True)

    config = load_config()
    
    # Create Environment
    # We wrap it in a lambda for Stable Baselines vectorization
    env = DummyVecEnv([lambda: AgroVisusEnv(config, project_root)])

    # Initialize PPO Agent
    model = PPO('MlpPolicy', env, verbose=1, tensorboard_log=log_dir)

    print("--- Starting Training ---")
    TIMESTEPS = 200000 
    model.learn(total_timesteps=TIMESTEPS, progress_bar=True)
    print("--- Training Finished ---")

    # Save Model
    model_path = f"{models_dir}/agrovisus_ppo_v3"
    model.save(model_path)
    print(f"Model saved to {model_path}")

    # Evaluation
    print("--- Evaluating Agent ---")
    obs = env.reset()
    total_rewards = []
    for _ in range(5): # Evaluate over 5 episodes
        episode_reward = 0
        done = False
        while not done:
            action, _ = model.predict(obs) # Deterministic=False by default for PPO training, True for eval?
            obs, rewards, dones, info = env.step(action)
            episode_reward += rewards[0]
            done = dones[0]
        total_rewards.append(episode_reward)
        print(f"Episode Reward: {episode_reward:.2f}")
    
    print(f"Average Evaluation Reward: {sum(total_rewards)/len(total_rewards):.2f}")

if __name__ == "__main__":
    train()
