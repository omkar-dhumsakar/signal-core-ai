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
from SignalCoreAI.dqn_engine import (
    DQNAgent, _build_pipeline_window, _build_state_array,
    PIPELINE_HORIZON, DEFAULT_METADATA_DIM,
)

# Category → integer index mapping for category embedding
_CATEGORY_INDEX = {}
_CATEGORY_COUNTER = 0

def _get_cat_idx(category: str) -> int:
    """Assign a stable integer index to each category string."""
    global _CATEGORY_COUNTER
    if category not in _CATEGORY_INDEX:
        _CATEGORY_INDEX[category] = _CATEGORY_COUNTER
        _CATEGORY_COUNTER += 1
    return _CATEGORY_INDEX[category]


def _build_metadata(profile: dict) -> np.ndarray:
    """Build a normalized metadata vector from a SKU profile.

    Returns [price_tier, lead_time_norm, shelf_life_norm, avg_sales_norm]
    """
    # Normalize features to roughly [0, 1] range
    avg_lead = profile.get("avg_lead_time", 3)
    avg_sales = profile.get("avg_daily_sales", 50)
    return np.array([
        0.5,                          # price_tier placeholder (no price in profile)
        min(avg_lead / 14.0, 1.0),    # lead_time normalized to 14-day max
        0.5,                          # shelf_life placeholder
        min(avg_sales / 200.0, 1.0),  # avg_sales normalized to 200 max
    ], dtype=np.float32)


def train_dqn(epochs=50, cluster_size=10, data_mode="real"):
    """
    Train DQN on a cluster of SKUs using either synthetic or real enterprise data.
    Updated for v2 architecture: metadata embeddings + pipeline vector state.
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
                "avg_daily_sales": random.uniform(20, 150),
                "category": random.choice(["Grocery", "Dairy", "Fruits", "Beverages", "Bakery"])
            } for sku in training_skus
        }

    # 2. Count unique categories and assign indices
    categories = set()
    for sku in training_skus:
        cat = profiles[sku].get("category", "Grocery")
        categories.add(cat)
        _get_cat_idx(cat)

    # 3. Setup Agent with metadata support
    targets = HOURLY_TARGETS
    agent = DQNAgent(
        targets=targets,
        num_skus=len(training_skus),
        embedding_dim=16,
        num_categories=max(len(categories), 25),
        pipeline_horizon=PIPELINE_HORIZON,
        use_prioritized_replay=True,
    )

    # Mapping SKU string ID to integer index for embedding
    sku_to_idx = {sku: i for i, sku in enumerate(training_skus)}

    history = []

    # 4. Training Loop
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
            cat_idx = _get_cat_idx(profile.get("category", "Grocery"))
            metadata = _build_metadata(profile)

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
            n = len(demand)
            max_eta_offset = 20
            arrivals = np.zeros(n + max_eta_offset, dtype=np.float32)
            horizon = agent.pipeline_horizon

            sku_reward = 0.0

            for t in range(n - 1):
                arrival_today = arrivals[t]

                # Build pipeline window (chronological arrivals)
                pipe_window = _build_pipeline_window(arrivals, t, horizon)
                current_state = _build_state_array(inv, signals[t], pipe_window, horizon)

                # Action with full context (SKU + category + metadata)
                action = agent.act(inv, pipe_window, signals[t],
                                   sku_id=sku_idx, cat_id=cat_idx,
                                   metadata=metadata)
                action_idx = targets.index(action)

                # Update Arrivals
                if action > 0:
                    eta_offset = int(np.random.poisson(sim.lead_time))
                    eta_offset = min(eta_offset, max_eta_offset - 1)
                    eta = t + eta_offset
                    if eta < len(arrivals):
                        arrivals[eta] += action

                # Simulation Step
                n_inv, cost, unmet = sim.step(inv, demand[t], signals[t], arrival_today)
                reward = -cost

                # Next State with pipeline window
                next_pipe_window = _build_pipeline_window(arrivals, t + 1, horizon)
                next_state = _build_state_array(n_inv, signals[t + 1], next_pipe_window, horizon)

                # Memory (prioritized replay)
                done = 1.0 if t == n - 2 else 0.0
                if agent.use_prioritized_replay:
                    agent.memory.push(
                        current_state, sku_idx, cat_idx, metadata,
                        action_idx, reward,
                        next_state, sku_idx, cat_idx, metadata, done
                    )
                else:
                    agent.memory.push(current_state, sku_idx, action_idx, reward,
                                      next_state, sku_idx, done)

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
            print(f"Epoch {epoch+1}/{epochs} | Avg Cluster Reward: {avg_reward:.2f} | "
                  f"Avg Loss: {avg_loss:.4f} | Epsilon: {agent.epsilon:.3f} | "
                  f"PER Beta: {agent._beta:.3f}")

    # 5. Export Scaled Model
    model_path = os.path.join(os.path.dirname(__file__), "dqn_weights_scaled_v1.pt")
    agent.save(model_path)
    print(f"\nMulti-SKU Training Complete. Model saved to {model_path}")

    return history

if __name__ == "__main__":
    # Start with a pilot of 10 SKUs for 30 epochs
    train_dqn(epochs=30, cluster_size=10, data_mode="real")
