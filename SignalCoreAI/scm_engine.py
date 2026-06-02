import numpy as np
import random

SHELF_LIFE_HORIZON = 14


# ── Per-category economics for category-aware Q-tables ──────────────
# Format: (holding_cost, stockout_cost, spoilage_rate, waste_unit_cost)
# waste_unit_cost: per-unit penalty for spoiled inventory (perishables high)
CATEGORY_ECONOMICS = {
    "Grocery":       (0.15, 8.0,  0.03,  1.5),
    "Electronics":   (0.30, 15.0, 0.001, 0.1),
    "Fashion":       (0.20, 5.0,  0.005, 0.2),
    "Home":          (0.15, 7.0,  0.002, 0.1),
    "Beauty":        (0.12, 6.0,  0.01,  0.5),
    "Toys":          (0.10, 5.0,  0.003, 0.1),
    "Sports":        (0.12, 6.0,  0.002, 0.1),
    "Books":         (0.05, 4.0,  0.001, 0.05),
    "Pharmacy":      (0.10, 12.0, 0.02,  2.0),
    "Fruits":        (0.08, 9.0,  0.06,  8.0),
    "Vegetables":    (0.08, 9.0,  0.07,  8.0),
    "Dairy":         (0.10, 10.0, 0.05,  6.0),
    "Bakery":        (0.10, 8.0,  0.04,  5.0),
    "Beverages":     (0.08, 7.0,  0.01,  1.0),
    "Snacks":        (0.10, 6.0,  0.02,  1.5),
    "Spirits":       (0.05, 12.0, 0.001, 0.1),
    "Pulp & Puree":  (0.10, 7.0,  0.04,  5.0),
    "Dry Fruits":    (0.08, 8.0,  0.01,  1.0),
    "Oils":          (0.06, 7.0,  0.005, 0.3),
    "Spices":        (0.06, 6.0,  0.005, 0.2),
}
_DEFAULT_ECONOMICS = (0.10, 10.0, 0.01, 1.0)


def get_category_sim_params(category: str) -> tuple:
    """Return (holding_cost, stockout_cost, spoilage_rate, waste_unit_cost)."""
    return CATEGORY_ECONOMICS.get(category, _DEFAULT_ECONOMICS)


class StochasticSCMSimulator:
    def __init__(self, lead_time=3, holding_cost=0.1, stockout_cost=10.0,
                 spoilage_rate=0.01, waste_unit_cost=1.0, time_unit="days"):
        self.lead_time = lead_time
        self.holding_cost = holding_cost
        self.stockout_cost = stockout_cost
        self.waste_unit_cost = waste_unit_cost
        self.time_unit = time_unit
        # Scale spoilage for hourly simulation (÷24)
        if time_unit == "hours":
            self.spoilage_rate = spoilage_rate / 24.0
        else:
            self.spoilage_rate = spoilage_rate

    def step(self, age_matrix: np.ndarray, fresh_overflow: float, demand: float, promo_active: bool, arrival_qty: float, shelf_life: int):
        # 1. Aging and Spoilage (Bucket 0 expires)
        spoiled_qty = float(age_matrix[0])
        
        # Shift matrix left (items age by 1 period)
        age_matrix[:-1] = age_matrix[1:]
        age_matrix[-1] = 0.0
        
        # Transfer from overflow into the newest bucket (approximate)
        transfer = fresh_overflow * 0.05
        age_matrix[-1] += transfer
        fresh_overflow -= transfer

        # 2. Inbound Freight (deposit into correct bucket)
        if shelf_life <= SHELF_LIFE_HORIZON:
            idx = max(0, shelf_life - 1)
            age_matrix[idx] += arrival_qty
        else:
            fresh_overflow += arrival_qty

        # 3. Fulfillment (FEFO)
        unmet = demand
        for i in range(SHELF_LIFE_HORIZON):
            if unmet <= 0:
                break
            sold = min(age_matrix[i], unmet)
            age_matrix[i] -= sold
            unmet -= sold
            
        if unmet > 0:
            sold = min(fresh_overflow, unmet)
            fresh_overflow -= sold
            unmet -= sold

        # 4. Strategic Costing
        total_inv = float(np.sum(age_matrix) + fresh_overflow)
        multiplier = 5.0 if promo_active else 1.0
        cost = (
            (unmet * self.stockout_cost * multiplier)
            + (total_inv * self.holding_cost)
            + (spoiled_qty * self.waste_unit_cost)
        )

        return age_matrix, fresh_overflow, cost, unmet


# Order targets for different modes
DAILY_TARGETS = [0, 2500, 5000, 7500, 10000, 15000]
HOURLY_TARGETS = [0, 10, 25, 50, 100, 200]  # Smaller, more frequent orders


class QLearningAgent:
    def __init__(self, targets=None):
        self.targets = targets if targets else DAILY_TARGETS
        self.q, self.epsilon, self.alpha, self.gamma = {}, 0.3, 0.2, 0.95

    def get_state(self, inv, pipe_sum, signal):
        # Discretization for state-space stability
        return (int(inv // 2500), int(pipe_sum // 2500), int(signal))

    def act(self, inv, pipe_sum, signal, explore=True):
        state = self.get_state(inv, pipe_sum, signal)
        if (explore and random.random() < self.epsilon) or state not in self.q:
            return random.choice(self.targets)
        return self.targets[np.argmax(self.q[state])]

    def learn(self, s, ps, sig, action, reward, ns, nps, nsig):
        state, nstate = self.get_state(s, ps, sig), self.get_state(ns, nps, nsig)
        idx = self.targets.index(action)
        if state not in self.q: self.q[state] = np.zeros(len(self.targets))
        if nstate not in self.q: self.q[nstate] = np.zeros(len(self.targets))
        self.q[state][idx] += self.alpha * (reward + self.gamma * np.max(self.q[nstate]) - self.q[state][idx])


def train_agent_stochastic(sim, agent, df, epochs=250):
    """Trains the agent directly against stochastic arrival delays."""
    demand, signals = df['Demand'].values, df['Promo_Signal'].values
    n = len(demand)
    history = []
    
    # Pre-allocate buffer for arrivals to avoid dictionary iteration overhead.
    # Adds a buffer of 100 time periods to safely hold delayed deliveries beyond N.
    max_eta_offset = 100
    arrivals = np.zeros(n + max_eta_offset, dtype=np.float32)

    for epoch in range(epochs):
        age_matrix = np.zeros(SHELF_LIFE_HORIZON, dtype=np.float32)
        fresh_overflow = 5000.0  # start with bulk inventory
        shelf_life = 30  # arbitrary for QL synthetic training
        epoch_reward = 0.0
        pipeline_sum = 0.0
        arrivals.fill(0)

        for t in range(n - 1):
            arrival_today = arrivals[t]
            pipeline_sum -= arrival_today
            
            total_inv = np.sum(age_matrix) + fresh_overflow
            action = agent.act(total_inv, pipeline_sum, signals[t])

            if action > 0:
                eta_offset = int(np.random.poisson(sim.lead_time))
                eta_offset = min(eta_offset, max_eta_offset - 1)
                eta = t + eta_offset
                arrivals[eta] += action
                pipeline_sum += action

            age_matrix, fresh_overflow, cost, _ = sim.step(age_matrix, fresh_overflow, demand[t], signals[t], arrival_today, shelf_life)
            
            n_ps = pipeline_sum - arrivals[t + 1]
            n_inv = np.sum(age_matrix) + fresh_overflow
            
            agent.learn(total_inv, pipeline_sum, signals[t], action, -cost, n_inv, n_ps, signals[t + 1])
            epoch_reward -= cost

        history.append(epoch_reward / n)
        agent.epsilon *= 0.98  # Gradual exploration decay
    return agent, history


def train_agent_from_demand_series(
    sim, agent, demand_array, signal_array, epochs=15
):
    """Train an agent on raw demand/signal arrays (e.g. from real CSV data).

    Unlike train_agent_stochastic which expects a DataFrame, this accepts
    plain numpy arrays — suitable for aggregated real sales data.
    """
    demand = np.asarray(demand_array, dtype=float)
    signals = np.asarray(signal_array, dtype=float)
    n = len(demand)
    if n < 2:
        return agent, []

    history = []
    max_eta_offset = 100
    arrivals = np.zeros(n + max_eta_offset, dtype=np.float32)

    for epoch in range(epochs):
        inv = 5000.0
        epoch_reward = 0.0
        pipeline_sum = 0.0
        arrivals.fill(0)

        for t in range(n - 1):
            arrival_today = arrivals[t]
            pipeline_sum -= arrival_today

            action = agent.act(inv, pipeline_sum, signals[t])

            if action > 0:
                eta_offset = int(np.random.poisson(sim.lead_time))
                eta_offset = min(eta_offset, max_eta_offset - 1)
                eta = t + eta_offset
                arrivals[eta] += action
                pipeline_sum += action

            n_inv, cost, _ = sim.step(inv, demand[t], signals[t], arrival_today)
            
            n_ps = pipeline_sum - arrivals[t + 1]
            agent.learn(inv, pipeline_sum, signals[t], action, -cost, n_inv, n_ps, signals[t + 1])
            
            inv = n_inv
            epoch_reward -= cost

        history.append(epoch_reward / n)
        agent.epsilon *= 0.98
    return agent, history