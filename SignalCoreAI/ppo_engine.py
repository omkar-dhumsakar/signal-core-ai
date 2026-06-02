"""PPO (Proximal Policy Optimization) Agent for continuous-action inventory control.

Fix #1: Replaces the discrete DQN action space with a continuous policy
that can output any reorder quantity, eliminating the Action Explosion
problem when fine-grained ordering is needed.

Architecture:
    Actor-Critic with shared feature extractor:
    - Actor: Outputs (mean, log_std) for a Gaussian policy over order quantity
    - Critic: Outputs state value V(s) for advantage estimation

    Supports the same metadata-augmented embedding and pipeline vector
    state representation as DQN v2.

Usage:
    Set USE_PPO = True in rl_bridge.py to activate.
    The agent returns a continuous float order quantity instead of selecting
    from a discrete action set.
"""

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from collections import deque
from SignalCoreAI.scm_engine import SHELF_LIFE_HORIZON

from SignalCoreAI.dqn_engine import (
    PIPELINE_HORIZON,
    MAX_PIPELINE_SEQUENCE,
    DEFAULT_NUM_CATEGORIES,
    DEFAULT_METADATA_DIM,
    PipelineTransformer,
    _build_pipeline_sequence,
    _build_state_array,
)


class PPONetwork(nn.Module):
    """Actor-Critic network for continuous order quantities.

    Shared feature extractor feeds into separate Actor and Critic heads.

    Actor: Gaussian policy — outputs (mean, log_std) for order quantity.
           The mean is passed through a Softplus to ensure non-negative orders.
    Critic: Scalar state value V(s).
    """
    def __init__(self, num_skus=1, embedding_dim=16,
                 num_categories=DEFAULT_NUM_CATEGORIES,
                 metadata_dim=DEFAULT_METADATA_DIM,
                 pipeline_horizon=PIPELINE_HORIZON,
                 max_order_qty=200.0):
        super(PPONetwork, self).__init__()

        self.max_order_qty = max_order_qty
        
        state_static_dim = SHELF_LIFE_HORIZON + 1 + 1
        self.pipeline_transformer = PipelineTransformer(d_model=32)

        # Embeddings (shared with DQN v2 design)
        self.sku_embedding = nn.Embedding(num_skus, embedding_dim)
        self.cat_embedding = nn.Embedding(num_categories, 8)
        self.meta_proj = nn.Linear(metadata_dim, 8)

        total_input = state_static_dim + 32 + embedding_dim + 8 + 8

        # Shared feature extractor
        self.shared = nn.Sequential(
            nn.Linear(total_input, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
        )

        # Actor head: continuous action (order quantity)
        self.actor_mean = nn.Linear(64, 1)
        self.actor_log_std = nn.Parameter(torch.zeros(1))  # Learnable std

        # Critic head: state value
        self.critic = nn.Linear(64, 1)

    def forward(self, state, sku_id, cat_id=None, metadata=None):
        batch_size = state.shape[0]
        device = state.device

        state_static_dim = SHELF_LIFE_HORIZON + 1 + 1
        state_static = state[:, :state_static_dim]
        pipeline_flat = state[:, state_static_dim:]
        pipeline_seq = pipeline_flat.view(batch_size, MAX_PIPELINE_SEQUENCE, 2)
        
        seq_embed = self.pipeline_transformer(pipeline_seq)

        sku_embed = self.sku_embedding(sku_id.long())

        if cat_id is not None:
            cat_embed = self.cat_embedding(cat_id.long())
        else:
            cat_embed = self.cat_embedding(
                torch.zeros(batch_size, dtype=torch.long, device=device)
            )

        if metadata is not None:
            meta_embed = self.meta_proj(metadata)
        else:
            meta_embed = self.meta_proj(
                torch.zeros(batch_size, self.meta_proj.in_features, device=device)
            )

        x = torch.cat([state_static, seq_embed, sku_embed, cat_embed, meta_embed], dim=1)
        features = self.shared(x)

        # Actor: Gaussian mean (clamped to [0, max_order_qty])
        action_mean = torch.sigmoid(self.actor_mean(features)) * self.max_order_qty
        action_log_std = self.actor_log_std.expand_as(action_mean)
        action_std = torch.exp(action_log_std).clamp(min=1e-3)

        # Critic: state value
        value = self.critic(features)

        return action_mean, action_std, value


class RolloutBuffer:
    """Stores trajectory data for PPO update steps.

    Collects (state, action, reward, value, log_prob, done) tuples
    during rollout, then computes advantages via GAE (Generalized
    Advantage Estimation) for the policy update.
    """
    def __init__(self):
        self.states = []
        self.sku_ids = []
        self.cat_ids = []
        self.metadatas = []
        self.actions = []
        self.rewards = []
        self.values = []
        self.log_probs = []
        self.dones = []

    def push(self, state, sku_id, cat_id, metadata, action, reward,
             value, log_prob, done):
        self.states.append(state)
        self.sku_ids.append(sku_id)
        self.cat_ids.append(cat_id)
        self.metadatas.append(metadata)
        self.actions.append(action)
        self.rewards.append(reward)
        self.values.append(value)
        self.log_probs.append(log_prob)
        self.dones.append(done)

    def compute_advantages(self, gamma=0.99, lam=0.95):
        """Compute GAE (Generalized Advantage Estimation).

        Returns advantages and discounted returns.
        """
        n = len(self.rewards)
        advantages = np.zeros(n, dtype=np.float32)
        returns = np.zeros(n, dtype=np.float32)

        gae = 0.0
        next_value = 0.0

        for t in reversed(range(n)):
            delta = (self.rewards[t]
                     + gamma * next_value * (1 - self.dones[t])
                     - self.values[t])
            gae = delta + gamma * lam * (1 - self.dones[t]) * gae
            advantages[t] = gae
            returns[t] = advantages[t] + self.values[t]
            next_value = self.values[t]

        return advantages, returns

    def get_batches(self, batch_size, gamma=0.99, lam=0.95):
        """Yield mini-batches for PPO update.

        Computes advantages, shuffles, and yields fixed-size batches.
        """
        advantages, returns = self.compute_advantages(gamma, lam)

        # Normalize advantages
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        states = torch.FloatTensor(np.array(self.states))
        sku_ids = torch.LongTensor(np.array(self.sku_ids))
        cat_ids = torch.LongTensor(np.array(self.cat_ids))
        metadatas = torch.FloatTensor(np.array(self.metadatas))
        actions = torch.FloatTensor(np.array(self.actions))
        old_log_probs = torch.FloatTensor(np.array(self.log_probs))
        advantages_t = torch.FloatTensor(advantages)
        returns_t = torch.FloatTensor(returns)

        n = len(self.states)
        indices = np.arange(n)
        np.random.shuffle(indices)

        for start in range(0, n, batch_size):
            end = start + batch_size
            batch_idx = indices[start:end]

            yield (
                states[batch_idx],
                sku_ids[batch_idx],
                cat_ids[batch_idx],
                metadatas[batch_idx],
                actions[batch_idx],
                old_log_probs[batch_idx],
                advantages_t[batch_idx],
                returns_t[batch_idx],
            )

    def clear(self):
        self.states.clear()
        self.sku_ids.clear()
        self.cat_ids.clear()
        self.metadatas.clear()
        self.actions.clear()
        self.rewards.clear()
        self.values.clear()
        self.log_probs.clear()
        self.dones.clear()

    def __len__(self):
        return len(self.states)


class PPOAgent:
    """Proximal Policy Optimization agent for continuous order quantities.

    Parameters
    ----------
    num_skus : int
        Number of unique SKUs for embedding table.
    max_order_qty : float
        Maximum order quantity the agent can place.
    embedding_dim : int
        Dimensionality of SKU embeddings.
    num_categories : int
        Number of product categories.
    metadata_dim : int
        Continuous metadata features per SKU.
    pipeline_horizon : int
        Number of future periods to track in pipeline vector.
    """
    def __init__(self, num_skus=100, max_order_qty=200.0,
                 embedding_dim=16,
                 num_categories=DEFAULT_NUM_CATEGORIES,
                 metadata_dim=DEFAULT_METADATA_DIM,
                 pipeline_horizon=PIPELINE_HORIZON):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.max_order_qty = max_order_qty
        self.pipeline_horizon = pipeline_horizon

        # Hyperparameters
        self.gamma = 0.99
        self.lam = 0.95               # GAE lambda
        self.lr = 3e-4
        self.clip_epsilon = 0.2        # PPO clipping range
        self.entropy_coeff = 0.01      # Entropy bonus for exploration
        self.value_coeff = 0.5         # Value loss weight
        self.max_grad_norm = 0.5       # Gradient clipping
        self.ppo_epochs = 4            # Update epochs per rollout
        self.batch_size = 64
        self.rollout_length = 256      # Steps before update

        # Network
        self.network = PPONetwork(
            num_skus, embedding_dim, num_categories,
            metadata_dim, pipeline_horizon, max_order_qty
        ).to(self.device)

        self.optimizer = optim.Adam(self.network.parameters(), lr=self.lr)
        self.buffer = RolloutBuffer()

    def act(self, inv, pipeline_window, signal, sku_id=0, cat_id=0,
            metadata=None, explore=True):
        """Select a continuous order quantity.

        Parameters
        ----------
        inv : float
        pipeline_window : array-like
        signal : float
        sku_id, cat_id : int
        metadata : array-like or None
        explore : bool
            If False, returns the mean (greedy) action.
        """

    def act(self, age_matrix, fresh_overflow, pipeline_seq, signal,
            sku_id=0, cat_id=0, metadata=None, explore=True):
        """Select action using PPO continuous policy."""
        state = _build_state_array(age_matrix, fresh_overflow, signal, pipeline_seq)
        state_t = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        sku_t = torch.LongTensor([sku_id]).to(self.device)
        cat_t = torch.LongTensor([cat_id]).to(self.device)

        if metadata is not None:
            meta_t = torch.FloatTensor([metadata]).to(self.device)
        else:
            meta_t = None

        with torch.no_grad():
            mean, std, value = self.network(state_t, sku_t, cat_t, meta_t)

        if explore:
            # Sample from Gaussian
            dist = torch.distributions.Normal(mean, std)
            action = dist.sample()
            log_prob = dist.log_prob(action).sum(dim=-1)
        else:
            action = mean
            dist = torch.distributions.Normal(mean, std)
            log_prob = dist.log_prob(action).sum(dim=-1)

        # Clamp to valid range
        action = action.clamp(0, self.max_order_qty)

        return (
            float(action.item()),
            float(value.item()),
            float(log_prob.item()),
        )

    def act_batched(self, age_matrices, fresh_overflows, pipeline_seqs, signals, sku_ids, cat_ids, metadatas=None, explore=False):
        """Batched action selection for high-throughput inference across many SKUs."""
        batch_size = len(age_matrices)
        if batch_size == 0:
            return [], []

        states = []
        for am, fo, seq, sig in zip(age_matrices, fresh_overflows, pipeline_seqs, signals):
            states.append(_build_state_array(am, fo, sig, seq))
        
        states = np.array(states, dtype=np.float32)

        state_t = torch.FloatTensor(states).to(self.device)
        sku_t = torch.LongTensor(sku_ids).to(self.device)
        cat_t = torch.LongTensor(cat_ids).to(self.device)

        if metadatas is not None:
            meta_t = torch.FloatTensor(np.array(metadatas)).to(self.device)
        else:
            meta_t = None

        with torch.no_grad():
            mean, std, values = self.network(state_t, sku_t, cat_t, meta_t)

        if explore:
            dist = torch.distributions.Normal(mean, std)
            actions = dist.sample()
        else:
            actions = mean

        # Clamp to valid range
        actions = actions.clamp(0, self.max_order_qty).squeeze(-1).cpu().numpy()
        
        # Calculate confidences (tighter std = higher confidence)
        means_np = mean.squeeze(-1).cpu().numpy()
        stds_np = std.squeeze(-1).cpu().numpy()
        confidences = 1.0 / (1.0 + stds_np / np.maximum(means_np, 1.0))
        confidences = np.clip(confidences, 0.1, 0.99)

        if batch_size == 1:
            return [float(actions)], confidences.tolist()
        return actions.tolist(), confidences.tolist()

    def store_transition(self, state, sku_id, cat_id, metadata,
                         action, reward, value, log_prob, done):
        """Store a transition in the rollout buffer."""
        if metadata is None:
            metadata = np.zeros(DEFAULT_METADATA_DIM, dtype=np.float32)
        self.buffer.push(state, sku_id, cat_id, metadata,
                         action, reward, value, log_prob, done)

    def update(self):
        """Perform PPO update using collected rollout data.

        Returns average policy loss, value loss, and entropy.
        """
        if len(self.buffer) < self.batch_size:
            return None

        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy = 0.0
        num_updates = 0

        for _ in range(self.ppo_epochs):
            for batch in self.buffer.get_batches(
                self.batch_size, self.gamma, self.lam
            ):
                (states, sku_ids, cat_ids, metadatas, actions,
                 old_log_probs, advantages, returns) = batch

                states = states.to(self.device)
                sku_ids = sku_ids.to(self.device)
                cat_ids = cat_ids.to(self.device)
                metadatas = metadatas.to(self.device)
                actions = actions.to(self.device)
                old_log_probs = old_log_probs.to(self.device)
                advantages = advantages.to(self.device)
                returns = returns.to(self.device)

                # Forward pass
                mean, std, values = self.network(states, sku_ids, cat_ids, metadatas)
                dist = torch.distributions.Normal(mean.squeeze(), std.squeeze())
                new_log_probs = dist.log_prob(actions)
                entropy = dist.entropy().mean()

                # PPO clipped objective
                ratio = torch.exp(new_log_probs - old_log_probs)
                surr1 = ratio * advantages
                surr2 = torch.clamp(ratio, 1.0 - self.clip_epsilon,
                                    1.0 + self.clip_epsilon) * advantages
                policy_loss = -torch.min(surr1, surr2).mean()

                # Value loss (clipped)
                value_loss = nn.MSELoss()(values.squeeze(), returns)

                # Total loss
                loss = (policy_loss
                        + self.value_coeff * value_loss
                        - self.entropy_coeff * entropy)

                self.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(
                    self.network.parameters(), self.max_grad_norm
                )
                self.optimizer.step()

                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy += entropy.item()
                num_updates += 1

        self.buffer.clear()

        if num_updates > 0:
            return {
                "policy_loss": total_policy_loss / num_updates,
                "value_loss": total_value_loss / num_updates,
                "entropy": total_entropy / num_updates,
            }
        return None

    def save(self, path):
        torch.save({
            'network': self.network.state_dict(),
            'optimizer': self.optimizer.state_dict(),
        }, path)

    def load(self, path):
        checkpoint = torch.load(path, map_location=self.device, weights_only=False)
        self.network.load_state_dict(checkpoint['network'])
        self.optimizer.load_state_dict(checkpoint['optimizer'])


# ── Training Functions ────────────────────────────────────────────────

def train_ppo_stochastic(sim, agent, df, sku_id=0, cat_id=0,
                         metadata=None, epochs=30):
    """Train a PPO agent on synthetic demand via stochastic simulator.

    Parameters
    ----------
    sim : StochasticSCMSimulator
    agent : PPOAgent
    df : DataFrame with 'Demand' and 'Promo_Signal' columns
    sku_id : int
    cat_id : int
    metadata : array-like or None
    epochs : int
    """
    demand = df["Demand"].values.astype(float)
    signals = df["Promo_Signal"].values.astype(float)
    n = len(demand)
    history = []
    max_eta_offset = 50
    arrivals = np.zeros(n + max_eta_offset, dtype=np.float32)
    horizon = agent.pipeline_horizon

    if metadata is None:
        metadata = np.zeros(DEFAULT_METADATA_DIM, dtype=np.float32)
    else:
        metadata = np.asarray(metadata, dtype=np.float32)

    for epoch in range(epochs):
        shelf_life = 30
        age_matrix = np.zeros(SHELF_LIFE_HORIZON, dtype=np.float32)
        fresh_overflow = 5000.0
        epoch_reward = 0.0
        arrivals.fill(0)
        steps_since_update = 0

        for t in range(n - 1):
            arrival_today = arrivals[t]

            pipe_seq = _build_pipeline_sequence(arrivals, t)
            current_state = _build_state_array(age_matrix, fresh_overflow, signals[t], pipe_seq)

            action_qty, value, log_prob = agent.act(
                age_matrix, fresh_overflow, pipe_seq, signals[t],
                sku_id=sku_id, cat_id=cat_id, metadata=metadata, explore=True
            )

            action_int = max(0, round(action_qty))

            if action_int > 0:
                eta_offset = int(np.random.poisson(sim.lead_time))
                eta_offset = min(eta_offset, max_eta_offset - 1)
                eta = t + eta_offset
                if eta < len(arrivals):
                    arrivals[eta] += action_int

            age_matrix, fresh_overflow, cost, _ = sim.step(age_matrix, fresh_overflow, demand[t], signals[t], arrival_today, shelf_life)
            reward = -cost
            done = 1.0 if t == n - 2 else 0.0

            agent.store_transition(
                current_state, sku_id, cat_id, metadata,
                action_qty, reward, value, log_prob, done
            )
            steps_since_update += 1

            if steps_since_update >= agent.rollout_length:
                agent.update()
                steps_since_update = 0

            epoch_reward -= cost

        if steps_since_update > agent.batch_size:
            agent.update()

        history.append(epoch_reward / n)
    return agent, history
