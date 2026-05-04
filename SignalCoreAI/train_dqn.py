import numpy as np
import torch
import os
import sys
import random
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from SignalCoreAI.scm_engine import StochasticSCMSimulator, HOURLY_TARGETS, get_category_sim_params
from SignalCoreAI.data_utils import generate_demand_signals, load_sku_demand_profiles
from SignalCoreAI.dqn_engine import DQNAgent

def train_dqn(epochs=50, cluster_size=10, data_mode="real"):
    """
    Train DQN on a cluster of SKUs using either synthetic or real enterprise data.
    """
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting ML Scaling: Multi-SKU Training (Mode: {data_mode})")
    
    # 1. Load Data
    csv_path = os.path.join("backend", "reliance_20stores_500skus_mar2026_with_leadtime.csv")
    if data_mode == "real":
        try:
            profiles = load_sku_demand_profiles(csv_path)
            all_sku_ids = list(profiles.keys())
            # Select a cluster of SKUs
            training_skus = all_sku_ids[:cluster_size]
            print(f"Loaded real profiles for {len(training_skus)} SKUs from Reliance dataset.")
        except Exception as e:
            print(f"Warning: Failed to load real data ({e}). Falling back to synthetic.")
            data_mode = "synthetic"
    
    if data_mode == "synthetic":
        training_skus = [f"SYNTH-{i}" for i in range(cluster_size)]
        profiles = {
            sku: {
                "demand": generate_demand_signals(days=90)["Demand"].values,
                "promo_signal": generate_demand_signals(days=90)["Promo_Signal"].values,
                "avg_lead_time": 3,
                "category": "Grocery"
            } for sku in training_skus
        }

    # 2. Setup Agent
    targets = HOURLY_TARGETS
    # We enable embeddings for the total number of SKUs we'll ever see
    agent = DQNAgent(targets=targets, num_skus=len(training_skus), embedding_dim=16)
    
    # Mapping SKU string ID to integer index for embedding
    sku_to_idx = {sku: i for i, sku in enumerate(training_skus)}
    
    history = []
    
    # 3. Training Loop
    for epoch in range(epochs):
        epoch_rewards = []
        epoch_losses = []
        
        # Shuffle SKUs each epoch to prevent bias
        random.shuffle(training_skus)
        
        for sku in training_skus:
            profile = profiles[sku]
            demand = profile["demand"]
            signals = profile["promo_signal"]
            sku_idx = sku_to_idx[sku]
            
            # Setup Simulator for this SKU's category
            h, s, sp, wc = get_category_sim_params(profile.get("category", "Grocery"))
            sim = StochasticSCMSimulator(
                lead_time=profile["avg_lead_time"],
                holding_cost=h,
                stockout_cost=s,
                spoilage_rate=sp,
                waste_unit_cost=wc,
                time_unit="days"
            )
            
            inv = 100.0
            pipeline_sum = 0.0
            n = len(demand)
            max_eta_offset = 20
            arrivals = np.zeros(n + max_eta_offset, dtype=np.float32)
            
            sku_reward = 0.0
            
            for t in range(n - 1):
                arrival_today = arrivals[t]
                pipeline_sum -= arrival_today
                
                # State: (Inv, Pipeline, Signal)
                current_state = np.array([inv, pipeline_sum, signals[t]], dtype=np.float32)
                
                # Action (Epsilon-Greedy with SKU Embedding)
                action = agent.act(inv, pipeline_sum, signals[t], sku_id=sku_idx)
                action_idx = targets.index(action)
                
                # Update Arrivals
                if action > 0:
                    eta_offset = int(np.random.poisson(sim.lead_time))
                    eta_offset = min(eta_offset, max_eta_offset - 1)
                    eta = t + eta_offset
                    if eta < len(arrivals):
                        arrivals[eta] += action
                        pipeline_sum += action
                
                # Simulation Step
                n_inv, cost, unmet = sim.step(inv, demand[t], signals[t], arrival_today)
                reward = -cost
                
                # Next State
                n_ps = pipeline_sum - (arrivals[t+1] if t+1 < len(arrivals) else 0)
                next_state = np.array([n_inv, n_ps, signals[t+1]], dtype=np.float32)
                
                # Memory
                done = (t == n - 2)
                agent.memory.push(current_state, sku_idx, action_idx, reward, next_state, sku_idx, done)
                
                # Optimization Step
                loss = agent.learn()
                if loss is not None:
                    epoch_losses.append(loss)
                
                inv = n_inv
                sku_reward += reward
                
            epoch_rewards.append(sku_reward / n)
            
        avg_reward = np.mean(epoch_rewards)
        avg_loss = np.mean(epoch_losses) if epoch_losses else 0
        history.append(avg_reward)
        
        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(f"Epoch {epoch+1}/{epochs} | Avg Cluster Reward: {avg_reward:.2f} | Avg Loss: {avg_loss:.4f} | Epsilon: {agent.epsilon:.3f}")

    # 4. Export Scaled Model
    model_path = os.path.join(os.path.dirname(__file__), "dqn_weights_scaled_v1.pt")
    agent.save(model_path)
    print(f"\nMulti-SKU Training Complete. Model saved to {model_path}")
    
    return history

if __name__ == "__main__":
    # Start with a pilot of 10 SKUs for 30 epochs
    train_dqn(epochs=30, cluster_size=10, data_mode="real")
