import random
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from collections import deque
from SignalCoreAI.scm_engine import SHELF_LIFE_HORIZON

# ── Configuration ─────────────────────────────────────────────────────

PIPELINE_HORIZON = 14  # Legacy (kept for compat)
MAX_PIPELINE_SEQUENCE = 50  # Max pending orders (Qty, ETA) tuples
DEFAULT_NUM_CATEGORIES = 25  # Max product categories for embedding
DEFAULT_METADATA_DIM = 4     # [price_tier, lead_time, shelf_life_norm, avg_sales_norm]

class PipelineTransformer(nn.Module):
    """Processes variable-length lists of (Quantity, Days_Until_Arrival)."""
    def __init__(self, d_model=32, nhead=4, num_layers=2):
        super().__init__()
        self.input_proj = nn.Linear(2, d_model)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, batch_first=True, dim_feedforward=128
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
    def forward(self, seq):
        # seq: (batch, seq_len, 2)
        x = self.input_proj(seq)
        x = self.transformer(x)
        # Mean pooling over valid (non-padded) tokens
        mask = (seq[:, :, 0] != 0).float().unsqueeze(-1)
        x = x * mask
        sum_x = x.sum(dim=1)
        count = mask.sum(dim=1).clamp(min=1.0)
        return sum_x / count

# ── Neural Network Architecture ───────────────────────────────────────
# Fix #3: Metadata-Augmented Embeddings for Cold Start Mitigation
# Fix #2: Pipeline vector input instead of scalar pipeline_sum

class DQNNetwork(nn.Module):
    """Deep Q-Network for SCM RL with metadata-augmented embeddings.

    Architecture:
    Input: [Inventory, Signal, Pipeline_Window[0..K-1],
            SKU_Embedding, Category_Embedding, Metadata_Projection]
    Output: Q-Values for each discrete action target.

    Cold Start Mitigation:
        New SKUs benefit from learned category/metadata patterns even
        before accumulating sufficient training samples, because the
        category embedding and metadata projection layers capture
        cross-SKU structural similarities.

    Pipeline Awareness:
        Instead of a single pipeline_sum scalar, the network receives
        a vector of expected arrivals over the next PIPELINE_HORIZON
        periods, preserving chronological order information.
    """
    def __init__(self, output_dim, num_skus=1, embedding_dim=8,
                 num_categories=DEFAULT_NUM_CATEGORIES,
                 metadata_dim=DEFAULT_METADATA_DIM,
                 pipeline_horizon=PIPELINE_HORIZON):
        super(DQNNetwork, self).__init__()

        # State features: age_matrix(SHELF_LIFE_HORIZON) + fresh_overflow(1) + signal(1)
        state_static_dim = SHELF_LIFE_HORIZON + 1 + 1
        
        # Transformer for pipeline sequence
        self.pipeline_transformer = PipelineTransformer(d_model=32)

        # Hybrid embedding: learnable SKU ID + category ID + continuous metadata
        self.sku_embedding = nn.Embedding(num_skus, embedding_dim)
        self.cat_embedding = nn.Embedding(num_categories, 8)
        self.meta_proj = nn.Linear(metadata_dim, 8)

        total_input = state_static_dim + 32 + embedding_dim + 8 + 8  # static + seq + sku + cat + meta

        # MLP Layers
        self.fc = nn.Sequential(
            nn.Linear(total_input, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, output_dim)
        )

    def forward(self, state, sku_id, cat_id=None, metadata=None):
        """Forward pass with optional category and metadata inputs.

        Parameters
        ----------
        state : Tensor (batch, 2 + pipeline_horizon + 1)
            [inventory, signal, pipe_t+1, ..., pipe_t+K, overflow_sum]
        sku_id : Tensor (batch,)
            Integer SKU embedding index.
        cat_id : Tensor (batch,), optional
            Integer category embedding index. Defaults to zeros.
        metadata : Tensor (batch, metadata_dim), optional
            Continuous features [price_tier, lead_time, shelf_life, avg_sales].
            Defaults to zeros.
        """
        batch_size = state.shape[0]
        device = state.device

        # Split flat state into static and sequence
        state_static_dim = SHELF_LIFE_HORIZON + 1 + 1
        state_static = state[:, :state_static_dim]
        pipeline_flat = state[:, state_static_dim:]
        pipeline_seq = pipeline_flat.view(batch_size, MAX_PIPELINE_SEQUENCE, 2)
        
        # Process sequence
        seq_embed = self.pipeline_transformer(pipeline_seq)

        sku_embed = self.sku_embedding(sku_id.long())

        if cat_id is not None:
            cat_embed = self.cat_embedding(cat_id.long())
        else:
            cat_embed = self.cat_embedding(torch.zeros(batch_size, dtype=torch.long, device=device))

        if metadata is not None:
            meta_embed = self.meta_proj(metadata)
        else:
            meta_embed = self.meta_proj(torch.zeros(batch_size, self.meta_proj.in_features, device=device))

        x = torch.cat([state_static, seq_embed, sku_embed, cat_embed, meta_embed], dim=1)
        return self.fc(x)


# ── Prioritized Replay Buffer ────────────────────────────────────────
# Fix #4: Prioritized Experience Replay for sample efficiency

class PrioritizedReplayBuffer:
    """Experience replay with TD-error-based priority sampling.

    Transitions with higher TD error (i.e., more surprising or
    informative experiences) are sampled more frequently, improving
    sample efficiency — critical for supply chain environments where
    stockout/spoilage events are rare but high-impact.

    Parameters
    ----------
    capacity : int
        Maximum buffer size.
    alpha : float
        Prioritization exponent. 0 = uniform, 1 = fully prioritized.
    """
    def __init__(self, capacity=20000, alpha=0.6):
        self.buffer = deque(maxlen=capacity)
        self.priorities = deque(maxlen=capacity)
        self.alpha = alpha
        self._max_priority = 1.0

    def push(self, state, sku_id, cat_id, metadata, action_idx, reward,
             next_state, next_sku_id, next_cat_id, next_metadata, done):
        """Store a transition with maximum priority (ensures it gets sampled at least once)."""
        self.buffer.append((
            state, sku_id, cat_id, metadata, action_idx, reward,
            next_state, next_sku_id, next_cat_id, next_metadata, done
        ))
        self.priorities.append(self._max_priority)

    def sample(self, batch_size, beta=0.4):
        """Sample a prioritized mini-batch with importance sampling weights.

        Parameters
        ----------
        batch_size : int
        beta : float
            Importance sampling exponent for bias correction.
            Should anneal from ~0.4 to 1.0 over training.

        Returns
        -------
        tuple of tensors + weights + indices for priority updates
        """
        n = len(self.buffer)
        if n < batch_size:
            return None

        priorities = np.array(self.priorities, dtype=np.float64)
        probs = priorities ** self.alpha
        probs /= probs.sum()

        indices = np.random.choice(n, batch_size, p=probs, replace=False)

        # Importance sampling weights for bias correction
        weights = (n * probs[indices]) ** (-beta)
        weights /= weights.max()

        batch = [self.buffer[i] for i in indices]
        (states, sku_ids, cat_ids, metadatas, actions, rewards,
         next_states, next_sku_ids, next_cat_ids, next_metadatas, dones) = zip(*batch)

        return (
            torch.FloatTensor(np.array(states)),
            torch.LongTensor(np.array(sku_ids)),
            torch.LongTensor(np.array(cat_ids)),
            torch.FloatTensor(np.array(metadatas)),
            torch.LongTensor(np.array(actions)),
            torch.FloatTensor(np.array(rewards)),
            torch.FloatTensor(np.array(next_states)),
            torch.LongTensor(np.array(next_sku_ids)),
            torch.LongTensor(np.array(next_cat_ids)),
            torch.FloatTensor(np.array(next_metadatas)),
            torch.FloatTensor(np.array(dones)),
            torch.FloatTensor(weights),
            indices,
        )

    def update_priorities(self, indices, td_errors):
        """Update priorities based on observed TD errors."""
        for idx, td in zip(indices, td_errors):
            priority = abs(td) + 1e-6
            self.priorities[idx] = priority
            self._max_priority = max(self._max_priority, priority)

    def __len__(self):
        return len(self.buffer)


# ── Legacy Replay Buffer (backward compatibility) ────────────────────

class ReplayBuffer:
    """Simple uniform replay buffer (legacy, kept for backward compat)."""
    def __init__(self, capacity=10000):
        self.buffer = deque(maxlen=capacity)

    def push(self, state, sku_id, action_idx, reward, next_state, next_sku_id, done):
        self.buffer.append((state, sku_id, action_idx, reward, next_state, next_sku_id, done))

    def sample(self, batch_size):
        batch = random.sample(self.buffer, batch_size)
        states, sku_ids, actions, rewards, next_states, next_sku_ids, dones = zip(*batch)
        return (
            torch.FloatTensor(np.array(states)),
            torch.LongTensor(np.array(sku_ids)),
            torch.LongTensor(np.array(actions)),
            torch.FloatTensor(np.array(rewards)),
            torch.FloatTensor(np.array(next_states)),
            torch.LongTensor(np.array(next_sku_ids)),
            torch.FloatTensor(np.array(dones))
        )

    def __len__(self):
        return len(self.buffer)


# ── DQN Agent ───────────────────────────────────────────────────────

class DQNAgent:
    """DQN Agent with metadata-augmented embeddings, prioritized replay,
    gradient clipping, and Huber loss.

    Parameters
    ----------
    targets : list[int]
        Discrete action targets (order quantities).
    num_skus : int
        Number of unique SKUs for embedding table.
    embedding_dim : int
        Dimensionality of SKU embeddings.
    num_categories : int
        Number of product categories for category embedding.
    metadata_dim : int
        Number of continuous metadata features per SKU.
    pipeline_horizon : int
        Number of future time periods to track in pipeline vector.
    use_prioritized_replay : bool
        Whether to use prioritized experience replay (PER).
    """
    def __init__(self, targets, num_skus=100, embedding_dim=16,
                 num_categories=DEFAULT_NUM_CATEGORIES,
                 metadata_dim=DEFAULT_METADATA_DIM,
                 pipeline_horizon=PIPELINE_HORIZON,
                 use_prioritized_replay=True):
        self.targets = targets
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.pipeline_horizon = pipeline_horizon

        # Hyperparameters
        self.gamma = 0.99
        self.epsilon = 1.0
        self.epsilon_min = 0.05
        self.epsilon_decay = 0.995
        self.lr = 1e-3
        self.batch_size = 64
        self.target_update_freq = 10
        self.grad_clip_norm = 10.0  # Fix #4: Gradient clipping

        # Modeling
        output_dim = len(targets)

        self.policy_net = DQNNetwork(
            output_dim, num_skus, embedding_dim,
            num_categories, metadata_dim, pipeline_horizon
        ).to(self.device)
        self.target_net = DQNNetwork(
            output_dim, num_skus, embedding_dim,
            num_categories, metadata_dim, pipeline_horizon
        ).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())

        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=self.lr)

        # Fix #4: Prioritized Experience Replay
        self.use_prioritized_replay = use_prioritized_replay
        if use_prioritized_replay:
            self.memory = PrioritizedReplayBuffer(capacity=20000)
        else:
            self.memory = ReplayBuffer(capacity=20000)

        self.steps_done = 0
        self._beta = 0.4  # PER importance sampling beta, anneals to 1.0

    def _build_state_tensor(self, age_matrix, fresh_overflow, pipeline_window, signal, overflow=0.0):
        """Construct the state vector from age matrix, fresh overflow, signal, pipeline window, and overflow.

        Parameters
        ----------
        age_matrix : array-like
            Inventory quantities expiring in 1 to SHELF_LIFE_HORIZON periods.
        fresh_overflow : float
            Inventory that expires beyond SHELF_LIFE_HORIZON.
        pipeline_window : array-like
            Expected arrivals for the next pipeline_horizon periods.
        signal : float
            Promo/demand signal (0 or 1).
        overflow : float
            Sum of all pending arrivals BEYOND the pipeline_horizon window.
            Prevents blindness to long-lead-time deliveries.

        Returns
        -------
        Tensor (1, 2 + pipeline_horizon + 1)
        """
        pw = np.asarray(pipeline_window, dtype=np.float32)
        # Pad or truncate to pipeline_horizon
        if len(pw) < self.pipeline_horizon:
            pw = np.pad(pw, (0, self.pipeline_horizon - len(pw)))
        else:
            pw = pw[:self.pipeline_horizon]

        state = np.concatenate([age_matrix, [fresh_overflow, signal], pw, [overflow]]).astype(np.float32)
        return torch.FloatTensor(state).unsqueeze(0).to(self.device)

    def act(self, age_matrix, fresh_overflow, pipeline_seq, signal,
            sku_id=0, cat_id=0, metadata=None, explore=True):
        """Select an action using the epsilon-greedy policy."""
        state = _build_state_array(age_matrix, fresh_overflow, signal, pipeline_seq)
        state_t = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        if explore and random.random() < self.epsilon:
            return random.choice(self.targets)

        sku = torch.LongTensor([sku_id]).to(self.device)
        cat = torch.LongTensor([cat_id]).to(self.device)

        if metadata is not None:
            meta = torch.FloatTensor([metadata]).to(self.device)
        else:
            meta = None

        with torch.no_grad():
            q_values = self.policy_net(state_t, sku, cat, meta)
            action_idx = q_values.argmax(dim=1).item()

        return self.targets[action_idx]

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
            q_values = self.policy_net(state_t, sku_t, cat_t, meta_t)
            action_idxs = q_values.argmax(dim=1).cpu().numpy()
            probs = torch.softmax(q_values, dim=1)
            confidences = probs.max(dim=1)[0].cpu().numpy()

        actions = [self.targets[idx] for idx in action_idxs]
        return actions, confidences.tolist()

    def learn(self):
        """Update the Q-network weights using prioritized replay and Huber loss."""
        if len(self.memory) < self.batch_size:
            return None

        if self.use_prioritized_replay:
            sample = self.memory.sample(self.batch_size, beta=self._beta)
            if sample is None:
                return None
            (states, sku_ids, cat_ids, metadatas, actions, rewards,
             next_states, next_sku_ids, next_cat_ids, next_metadatas,
             dones, is_weights, indices) = sample

            # Move to device
            states = states.to(self.device)
            sku_ids = sku_ids.to(self.device)
            cat_ids = cat_ids.to(self.device)
            metadatas = metadatas.to(self.device)
            actions = actions.to(self.device)
            rewards = rewards.to(self.device)
            next_states = next_states.to(self.device)
            next_sku_ids = next_sku_ids.to(self.device)
            next_cat_ids = next_cat_ids.to(self.device)
            next_metadatas = next_metadatas.to(self.device)
            dones = dones.to(self.device)
            is_weights = is_weights.to(self.device)

            # Current Q-values
            current_q = self.policy_net(states, sku_ids, cat_ids, metadatas)
            current_q = current_q.gather(1, actions.unsqueeze(1))

            # Target Q-values (from frozen target network)
            with torch.no_grad():
                next_q = self.target_net(next_states, next_sku_ids, next_cat_ids, next_metadatas)
                next_q = next_q.max(1)[0].unsqueeze(1)
                target_q = rewards.unsqueeze(1) + (self.gamma * next_q * (1 - dones.unsqueeze(1)))

            # TD errors for priority updates
            td_errors = (current_q - target_q).detach().squeeze().cpu().numpy()

            # Fix #4: Huber Loss (SmoothL1) weighted by importance sampling
            element_wise_loss = nn.SmoothL1Loss(reduction='none')(current_q, target_q)
            loss = (element_wise_loss * is_weights.unsqueeze(1)).mean()

            self.optimizer.zero_grad()
            loss.backward()
            # Fix #4: Gradient clipping to prevent exploding gradients
            torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), self.grad_clip_norm)
            self.optimizer.step()

            # Update priorities in replay buffer
            self.memory.update_priorities(indices, td_errors)

            # Anneal beta towards 1.0
            self._beta = min(1.0, self._beta + 2e-5)

        else:
            # Legacy uniform replay path
            sample = self.memory.sample(self.batch_size)
            states, sku_ids, actions, rewards, next_states, next_sku_ids, dones = sample
            states = states.to(self.device)
            sku_ids = sku_ids.to(self.device)
            actions = actions.to(self.device)
            rewards = rewards.to(self.device)
            next_states = next_states.to(self.device)
            next_sku_ids = next_sku_ids.to(self.device)
            dones = dones.to(self.device)

            current_q = self.policy_net(states, sku_ids).gather(1, actions.unsqueeze(1))
            with torch.no_grad():
                next_q = self.target_net(next_states, next_sku_ids).max(1)[0].unsqueeze(1)
                target_q = rewards.unsqueeze(1) + (self.gamma * next_q * (1 - dones.unsqueeze(1)))

            loss = nn.SmoothL1Loss()(current_q, target_q)
            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), self.grad_clip_norm)
            self.optimizer.step()

        # Decay epsilon
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

        # Update target network
        self.steps_done += 1
        if self.steps_done % self.target_update_freq == 0:
            self.target_net.load_state_dict(self.policy_net.state_dict())

        return loss.item()

    def save(self, path):
        torch.save({
            'policy_net': self.policy_net.state_dict(),
            'optimizer': self.optimizer.state_dict(),
            'epsilon': self.epsilon,
            'beta': self._beta,
            'steps_done': self.steps_done,
        }, path)

    def load(self, path):
        checkpoint = torch.load(path, map_location=self.device, weights_only=False)
        self.policy_net.load_state_dict(checkpoint['policy_net'])
        self.target_net.load_state_dict(checkpoint['policy_net'])
        self.optimizer.load_state_dict(checkpoint['optimizer'])
        self.epsilon = checkpoint.get('epsilon', 0.05)
        self._beta = checkpoint.get('beta', 0.4)
        self.steps_done = checkpoint.get('steps_done', 0)


# ── Training Helper: Build Pipeline Window ────────────────────────────

def _build_pipeline_sequence(arrivals, t, max_seq=MAX_PIPELINE_SEQUENCE):
    """Extract pending arrivals into a padded flat sequence array of (Qty, ETA)."""
    seq = []
    for i in range(1, len(arrivals) - t):
        if arrivals[t + i] > 0:
            seq.append([arrivals[t + i], i])
        if len(seq) >= max_seq:
            break
    while len(seq) < max_seq:
        seq.append([0.0, 0.0])
    return np.array(seq, dtype=np.float32).flatten()

def _build_state_array(age_matrix, fresh_overflow, signal, pipeline_seq_flat):
    """Construct a flat state vector combining static features and flattened sequence."""
    static = np.concatenate([age_matrix, [fresh_overflow, signal]])
    return np.concatenate([static, pipeline_seq_flat]).astype(np.float32)


# ── Standalone Training Functions ─────────────────────────────────────
# These mirror scm_engine.train_agent_stochastic / train_agent_from_demand_series
# but drive DQN replay-buffer learning instead of tabular Q-updates.
# Updated with: pipeline vector state, metadata, and PER.


def train_dqn_stochastic(sim, agent, df, sku_id=0, cat_id=0,
                         metadata=None, epochs=30):
    """Train a DQN agent on synthetic demand via stochastic simulator.

    Parameters
    ----------
    sim : StochasticSCMSimulator
    agent : DQNAgent
    df : DataFrame with 'Demand' and 'Promo_Signal' columns
    sku_id : int — SKU embedding index
    cat_id : int — Category embedding index
    metadata : array-like or None — [price_tier, lead_time, shelf_life, avg_sales]
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
        shelf_life = 30  # Arbitrary default for synthetic training
        age_matrix = np.zeros(SHELF_LIFE_HORIZON, dtype=np.float32)
        fresh_overflow = 5000.0
        epoch_reward = 0.0
        arrivals.fill(0)

        for t in range(n - 1):
            arrival_today = arrivals[t]

            pipe_seq = _build_pipeline_sequence(arrivals, t)
            current_state = _build_state_array(age_matrix, fresh_overflow, signals[t], pipe_seq)

            action = agent.act(age_matrix, fresh_overflow, pipe_seq, signals[t],
                               sku_id=sku_id, cat_id=cat_id, metadata=metadata, explore=True)
            action_idx = agent.targets.index(action)

            if action > 0:
                eta_offset = int(np.random.poisson(sim.lead_time))
                eta_offset = min(eta_offset, max_eta_offset - 1)
                eta = t + eta_offset
                if eta < len(arrivals):
                    arrivals[eta] += action

            age_matrix, fresh_overflow, cost, _ = sim.step(age_matrix, fresh_overflow, demand[t], signals[t], arrival_today, shelf_life)
            reward = -cost

            next_pipe_seq = _build_pipeline_sequence(arrivals, t + 1)
            next_state = _build_state_array(age_matrix, fresh_overflow, signals[t + 1], next_pipe_seq)

            done = 1.0 if t == n - 2 else 0.0

            if agent.use_prioritized_replay:
                agent.memory.push(
                    current_state, sku_id, cat_id, metadata,
                    action_idx, reward,
                    next_state, sku_id, cat_id, metadata, done
                )
            else:
                agent.memory.push(current_state, sku_id, action_idx, reward,
                                  next_state, sku_id, done)

            agent.learn()
            epoch_reward -= cost

        history.append(epoch_reward / n)
    return agent, history


def train_dqn_from_demand_series(sim, agent, demand_array, signal_array,
                                  sku_id=0, cat_id=0, metadata=None,
                                  epochs=10):
    """Train a DQN agent on real demand/signal arrays.

    Parameters
    ----------
    sim : StochasticSCMSimulator
    agent : DQNAgent
    demand_array, signal_array : array-like — raw demand & promo time-series
    sku_id : int — SKU embedding index within the category
    cat_id : int — Category embedding index
    metadata : array-like or None
    epochs : int
    """
    demand = np.asarray(demand_array, dtype=float)
    signals = np.asarray(signal_array, dtype=float)
    n = len(demand)
    if n < 2:
        return agent, []

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

        for t in range(n - 1):
            arrival_today = arrivals[t]

            pipe_seq = _build_pipeline_sequence(arrivals, t)
            current_state = _build_state_array(age_matrix, fresh_overflow, signals[t], pipe_seq)

            action = agent.act(age_matrix, fresh_overflow, pipe_seq, signals[t],
                              sku_id=sku_id, cat_id=cat_id,
                              metadata=metadata, explore=True)
            action_idx = agent.targets.index(action)

            if action > 0:
                eta_offset = int(np.random.poisson(sim.lead_time))
                eta_offset = min(eta_offset, max_eta_offset - 1)
                eta = t + eta_offset
                if eta < len(arrivals):
                    arrivals[eta] += action

            age_matrix, fresh_overflow, cost, _ = sim.step(age_matrix, fresh_overflow, demand[t], signals[t], arrival_today, shelf_life)
            reward = -cost

            next_pipe_seq = _build_pipeline_sequence(arrivals, t + 1)
            next_state = _build_state_array(age_matrix, fresh_overflow, signals[t + 1], next_pipe_seq)

            done = 1.0 if t == n - 2 else 0.0

            if agent.use_prioritized_replay:
                agent.memory.push(
                    current_state, sku_id, cat_id, metadata,
                    action_idx, reward,
                    next_state, sku_id, cat_id, metadata, done
                )
            else:
                agent.memory.push(current_state, sku_id, action_idx, reward,
                                  next_state, sku_id, done)

            agent.learn()
            epoch_reward -= cost

        history.append(epoch_reward / n)
    return agent, history
