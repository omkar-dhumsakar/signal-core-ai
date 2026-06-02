"""Bridge between FastAPI and the SignalCoreAI RL Agent.

Translates RL state/action representations into retail-friendly
directives for the StoreOps mobile app.
"""

import sys
import os
import random
import uuid
import time
import numpy as np
import torch
from datetime import datetime, date, timedelta
import pickle
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from SignalCoreAI.scm_engine import (
    QLearningAgent,
    StochasticSCMSimulator,
    train_agent_stochastic,
    train_agent_from_demand_series,
    get_category_sim_params,
    HOURLY_TARGETS,
    DAILY_TARGETS,
    SHELF_LIFE_HORIZON,
)
from SignalCoreAI.dqn_engine import (
    DQNAgent,
    train_dqn_stochastic,
    train_dqn_from_demand_series,
    PIPELINE_HORIZON,
    MAX_PIPELINE_SEQUENCE,
    DEFAULT_NUM_CATEGORIES,
    DEFAULT_METADATA_DIM,
)
from SignalCoreAI.ppo_engine import PPOAgent, train_ppo_stochastic
from SignalCoreAI.network_coordinator import (
    NetworkCoordinator, StoreCapacity, SupplierCapacity,
)
from SignalCoreAI.data_utils import generate_demand_signals, load_sku_demand_profiles

from models import (
    Directive,
    DirectiveStatus,
    AlertPriority,
    InventoryAuditResponse,
    MonsoonStatus,
    BudgetSummary,
    DarkStore,
    ShelfLifeStatus,
)

from data_utils import get_all_supplier_links

# ── Constants ─────────────────────────────────────────────────────────
MONSOON_MONTHS = {6, 7, 8, 9}
RL_TO_RETAIL_QTY = {
    0: 0,
    2500: 10,
    5000: 25,
    7500: 50,
    10000: 75,
    15000: 100
}
_DEFAULT_BASE_STOCK = 50

# Unit cost ranges per category (₹) — used when CSV has no price column
_CATEGORY_COST = {
    "Grocery":       (50, 200),
    "Electronics":   (500, 5000),
    "Fashion":       (300, 2000),
    "Home":          (200, 1500),
    "Beauty":        (100, 800),
    "Toys":          (150, 1000),
    "Sports":        (200, 1500),
    "Books":         (100, 600),
    "Pharmacy":      (50, 400),
    "Fruits":        (30, 150),
    "Vegetables":    (20, 100),
    "Dairy":         (30, 200),
    "Bakery":        (40, 250),
    "Beverages":     (25, 300),
    "Snacks":        (20, 150),
    "Spirits":       (200, 2000),
    "Pulp & Puree":  (60, 300),
    "Dry Fruits":    (150, 800),
    "Oils":          (80, 400),
    "Spices":        (50, 300),
}
_DEFAULT_COST_RANGE = (50, 500)

_PRIORITY_WEIGHTS = {
    AlertPriority.CRITICAL: 4.0,
    AlertPriority.HIGH: 3.0,
    AlertPriority.MEDIUM: 2.0,
    AlertPriority.LOW: 1.0,
}

_DEFAULT_DAILY_BUDGET = 50000.0  # ₹50,000
_VELOCITY_LABELS = ["Slow", "Medium", "Fast", "Ultra"]

# ── Dark Store Mode ─────────────────────────────────────────────────────────────
DARK_STORE_MODE = True  # Set False for traditional retail mode
USE_DQN = True          # True = neural DQN agents, False = tabular Q-learning
USE_PPO = False         # True = continuous PPO agent (overrides USE_DQN when True)

# Hourly RL action → retail quantity mapping (smaller, frequent orders)
RL_TO_RETAIL_QTY_HOURLY = {
    0: 0, 10: 5, 25: 10, 50: 20, 100: 40, 200: 80,
}

# Shelf life in hours per category (for expiry-based directives)
_SHELF_LIFE_HOURS = {
    "Fruits":       48,
    "Vegetables":   36,
    "Dairy":        120,
    "Bakery":       72,
    "Grocery":      2160,   # ~90 days
    "Beverages":    720,    # ~30 days
    "Snacks":       1440,   # ~60 days
    "Pharmacy":     4320,   # ~180 days
    "Pulp & Puree": 168,    # ~7 days
    "Dry Fruits":   2160,
    "Oils":         4320,
    "Spices":       4320,
    "Electronics":  87600,  # ~10 years
    "Fashion":      43800,  # ~5 years
    "Home":         43800,
    "Beauty":       8760,   # ~1 year
    "Toys":         43800,
    "Sports":       43800,
    "Books":        87600,
    "Spirits":      87600,
}
_DEFAULT_SHELF_LIFE = 2160  # 90 days

# Default stores — BigBasket's 3-Tier Bengaluru Network
_DEFAULT_STORES = [
    DarkStore(store_id="CDC-BLR-CENTRAL", name="BB Central Warehouse — Yelahanka", location="Yelahanka, Bengaluru", zone="Bengaluru", facility_type="cdc"),
    DarkStore(store_id="DS-BLR-KORAMANGALA", name="BB Now — Koramangala", location="Koramangala, Bengaluru", zone="South", facility_type="darkstore", parent_cdc="CDC-BLR-CENTRAL"),
    DarkStore(store_id="DS-BLR-HSR", name="BB Now — HSR Layout", location="HSR Layout, Bengaluru", zone="South", facility_type="darkstore", parent_cdc="CDC-BLR-CENTRAL"),
    DarkStore(store_id="DS-BLR-INDIRANAGAR", name="BB Now — Indiranagar", location="Indiranagar, Bengaluru", zone="East", facility_type="darkstore", parent_cdc="CDC-BLR-CENTRAL"),
    DarkStore(store_id="DS-BLR-WHITEFIELD", name="BB Now — Whitefield", location="Whitefield, Bengaluru", zone="East", facility_type="darkstore", parent_cdc="CDC-BLR-CENTRAL"),
    DarkStore(store_id="HUB-BLR-JAYANAGAR", name="BB Daily — Jayanagar", location="Jayanagar, Bengaluru", zone="South", facility_type="hub", parent_cdc="CDC-BLR-CENTRAL"),
]

def _infer_category(sku: str, supplier_name: str) -> str:
    """Infer BigBasket grocery category from SKU/supplier keywords."""
    name = f"{sku} {supplier_name}".lower()
    if any(k in name for k in ("milk", "curd", "paneer", "cheese", "egg", "butter", "yogurt")):
        return "Dairy & Eggs"
    if any(k in name for k in ("fruit", "veg", "tomato", "onion", "potato", "mango", "banana")):
        return "Fruits & Vegetables"
    if any(k in name for k in ("chicken", "mutton", "fish", "prawn", "meat", "seafood")):
        return "Meat & Seafood"
    if any(k in name for k in ("bread", "cake", "biscuit", "chips", "snack", "bakery")):
        return "Bakery & Snacks"
    if any(k in name for k in ("juice", "coffee", "tea", "water", "soda", "drink")):
        return "Beverages"
    if any(k in name for k in ("rice", "wheat", "atta", "dal", "flour", "grain", "oil", "sugar", "salt")):
        return "Staples & Grains"
    if any(k in name for k in ("spice", "pepper", "masala", "turmeric", "chilli")):
        return "Spices"
    if any(k in name for k in ("soap", "shampoo", "cream", "lotion", "care")):
        return "Personal Care"
    if any(k in name for k in ("detergent", "cleaner", "house")):
        return "Household"
    if any(k in name for k in ("cashew", "dry fruits", "almond", "raisin")):
        return "Dry Fruits & Nuts"
    return "General"

# ── CSV-driven product catalog ────────────────────────────────────────
_CSV_PATH = os.path.join(
    os.path.dirname(__file__),
    "bigbasket_40k_skus_bengaluru.csv",
)


def _load_catalog_from_csv() -> dict:
    """Load the product catalog from the Reliance Retail CSV.

    Deduplicates by sku_id, computes base_stock = round(avg daily_sales * avg lead_time),
    and uses the category and sku_name columns directly.
    """
    import pandas as pd

    if not os.path.exists(_CSV_PATH):
        print(f"[rl_bridge] WARNING: CSV not found at {_CSV_PATH}, using empty catalog")
        return {}

    df = pd.read_csv(_CSV_PATH)

    # Group by sku_id to get unique SKU metadata
    grouped = df.groupby("sku_id").agg(
        sku_name=("sku_name", "first"),
        category=("category", "first"),
        avg_daily_sales=("daily_sales", "mean"),
        avg_lead_time=("supplier_lead_time_days", "mean"),
    ).reset_index()

    catalog: dict = {}
    for _, row in grouped.iterrows():
        sku = row["sku_id"]
        category = row["category"]
        # base_stock = average daily sales × average lead time (safety buffer)
        base_stock = max(20, int(round(row["avg_daily_sales"] * row["avg_lead_time"])))
        # Generate deterministic unit cost from category
        lo, hi = _CATEGORY_COST.get(category, _DEFAULT_COST_RANGE)
        unit_cost = round(lo + (hash(sku) % 1000) / 1000 * (hi - lo), 2)
        avg_lead = float(row["avg_lead_time"])
        
        catalog[sku] = {
            "name": row["sku_name"],
            "category": category,
            "base_stock": base_stock,
            "unit_cost": unit_cost,
            "lead_time": round(avg_lead),
            "avg_daily_sales": float(row["avg_daily_sales"]),
        }

    return catalog


PRODUCT_CATALOG = _load_catalog_from_csv()




class StoreState:
    """Per-store inventory and agent state."""
    def __init__(self, store_id: str):
        self.store_id = store_id
        self.inventory_state: dict = {}
        self.feedback_log: list = []
        self.confirmed_orders: list = []


class RLBridge:
    def __init__(self):
        self.agents: dict = {}                        # keyed by category (DQN) or cluster (QL)
        self.sims: dict[str, StochasticSCMSimulator] = {}
        self._dynamic_catalog: dict = {}
        self.daily_budget: float = _DEFAULT_DAILY_BUDGET
        self._sku_cluster: dict[str, str] = {}        # sku → agent key
        self._sku_to_idx: dict[str, int] = {}         # sku → DQN embedding index
        self._cat_to_idx: dict[str, int] = {}         # category → DQN category embedding index
        self._sku_metadata: dict[str, np.ndarray] = {}  # sku → metadata vector

        # Multi-store support
        self.stores: dict[str, StoreState] = {}
        self.dark_stores: list[DarkStore] = list(_DEFAULT_STORES)

        # Initialize stores with inventory
        for ds in self.dark_stores:
            self.stores[ds.store_id] = StoreState(ds.store_id)
        self._init_all_stores()
        
        self.is_training: bool = False
        self._directive_cache: dict[str, dict] = {} # store_id -> {timestamp, directives}

        # ── Network Coordinator (Fix #5: multi-echelon constraints) ──
        store_caps = {}
        for ds in self.dark_stores:
            store_caps[ds.store_id] = StoreCapacity(
                store_id=ds.store_id,
                max_inbound_units=10000 if ds.facility_type == "cdc" else 3000,
                max_storage_units=50000 if ds.facility_type == "cdc" else 15000,
                facility_type=ds.facility_type,
                parent_cdc=ds.parent_cdc,
            )
        self.coordinator = NetworkCoordinator(store_capacities=store_caps)

        # PPO agents (separate from DQN agents)
        self._ppo_agents: dict = {}  # keyed by category

    @property
    def inventory_state(self) -> dict:
        """Backward-compatible: return central store's state."""
        return self.stores["DS-BLR-INDIRANAGAR"].inventory_state

    @property
    def feedback_log(self) -> list:
        return self.stores["DS-BLR-INDIRANAGAR"].feedback_log

    @property
    def confirmed_orders(self) -> list:
        return self.stores["DS-BLR-INDIRANAGAR"].confirmed_orders

    def _get_store(self, store_id: str | None = None) -> StoreState:
        """Return store state, defaulting to DS-INDIRANAGAR."""
        sid = store_id or "DS-BLR-INDIRANAGAR"
        if sid not in self.stores:
            raise ValueError(f"Unknown store: {sid}")
        return self.stores[sid]

    def _init_all_stores(self):
        for ds in self.dark_stores:
            store = self.stores[ds.store_id]
            for sku, info in PRODUCT_CATALOG.items():
                stock = info["base_stock"]
                seed_offset = hash(ds.store_id + sku) % 20 - 10
                variance = random.randint(-int(stock * 0.3), int(stock * 0.1)) + seed_offset
                shelf_life = _SHELF_LIFE_HOURS.get(info["category"], _DEFAULT_SHELF_LIFE)
                batch_age_hours = random.randint(1, max(1, int(shelf_life * 0.6)))
                
                qty = max(5, stock + variance)
                age_matrix = np.zeros(SHELF_LIFE_HORIZON, dtype=np.float32)
                fresh_overflow = 0.0
                
                # Assign initial inventory to a bucket based on simulated shelf life remaining
                rem_life = max(1, shelf_life - batch_age_hours)
                if rem_life <= SHELF_LIFE_HORIZON:
                    age_matrix[rem_life - 1] = qty
                else:
                    fresh_overflow = float(qty)

                pipeline_seq = []
                init_pipe = random.choice([0, 0, 0, 10, 20, 30])
                if init_pipe > 0:
                    arrival_slot = random.randint(1, min(5, PIPELINE_HORIZON - 1))
                    pipeline_seq.append([init_pipe, arrival_slot])
                store.inventory_state[sku] = {
                    "age_matrix": age_matrix.tolist(),
                    "fresh_overflow": fresh_overflow,
                    "on_hand": float(np.sum(age_matrix) + fresh_overflow),
                    "pipeline_seq": pipeline_seq,
                    "pipeline_sum": float(init_pipe),
                    "signal": random.choice([0, 0, 1]),
                    "oldest_batch_hours": batch_age_hours,
                    "shelf_life_hours": shelf_life,
                }

    def load_dynamic_catalog(self):
        """Load uploaded SKUs from the supplier DB and merge into the catalog."""
        supplier_links = get_all_supplier_links()
        new_count = 0
        for sku, info in supplier_links.items():
            if sku not in PRODUCT_CATALOG and sku not in self._dynamic_catalog:
                category = _infer_category(sku, info.get("supplier_name", ""))
                base_stock = _DEFAULT_BASE_STOCK
                self._dynamic_catalog[sku] = {
                    "name": sku.replace("-", " ").title(),
                    "category": category,
                    "base_stock": base_stock,
                }
                # Initialize inventory with random variance
                variance = random.randint(-int(base_stock * 0.5), int(base_stock * 0.2))
                qty = max(5, base_stock + variance)
                
                shelf_life = _SHELF_LIFE_HOURS.get(category, _DEFAULT_SHELF_LIFE)
                age_matrix = np.zeros(SHELF_LIFE_HORIZON, dtype=np.float32)
                fresh_overflow = 0.0
                if shelf_life <= SHELF_LIFE_HORIZON:
                    age_matrix[max(0, shelf_life - 1)] = qty
                else:
                    fresh_overflow = float(qty)

                self.inventory_state[sku] = {
                    "age_matrix": age_matrix.tolist(),
                    "fresh_overflow": fresh_overflow,
                    "on_hand": float(np.sum(age_matrix) + fresh_overflow),
                    "pipeline_seq": [],
                    "pipeline_sum": random.choice([0, 0, 0, 5, 10]),
                    "signal": random.choice([0, 0, 0, 1]),
                    "oldest_batch_hours": 0,
                    "shelf_life_hours": shelf_life,
                }
                new_count += 1
        return new_count

    def get_full_catalog(self) -> dict:
        """Return the merged catalog (static + dynamic)."""
        merged = dict(PRODUCT_CATALOG)
        merged.update(self._dynamic_catalog)
        return merged

    def get_all_categories(self) -> list[str]:
        """Return sorted unique categories across the full catalog."""
        cats = set()
        for info in self.get_full_catalog().values():
            cats.add(info["category"])
        return sorted(cats)

    # ── Clustering helpers ─────────────────────────────────────────

    @staticmethod
    def _velocity_label(avg_sales: float, quartiles: list[float]) -> str:
        """Assign a velocity label based on sales percentile thresholds."""
        for i, q in enumerate(quartiles):
            if avg_sales <= q:
                return _VELOCITY_LABELS[i]
        return _VELOCITY_LABELS[-1]

    def _build_clusters(self, catalog: dict) -> dict[str, list[str]]:
        """Cluster SKUs into (category × velocity_quartile) groups.

        Returns {cluster_key: [sku_id, ...]} and populates self._sku_cluster.
        """
        import pandas as pd

        rows = [
            {"sku": sku, "category": info["category"],
             "avg_daily_sales": info.get("avg_daily_sales", 50)}
            for sku, info in catalog.items()
        ]
        if not rows:
            return {}

        df = pd.DataFrame(rows)

        clusters: dict[str, list[str]] = {}
        for cat, grp in df.groupby("category"):
            sales = grp["avg_daily_sales"]
            # Compute quartile thresholds within this category
            q25, q50, q75 = sales.quantile([0.25, 0.5, 0.75]).tolist()
            quartiles = [q25, q50, q75]

            for _, row in grp.iterrows():
                vel = self._velocity_label(row["avg_daily_sales"], quartiles)
                key = f"{cat}_{vel}"
                clusters.setdefault(key, []).append(row["sku"])
                self._sku_cluster[row["sku"]] = key

        return clusters

    _QL_CACHE_PATH = os.path.join(os.path.dirname(__file__), ".rl_cache.pkl")
    _DQN_CACHE_PATH = os.path.join(os.path.dirname(__file__), ".dqn_cache.pt")

    @property
    def _CACHE_PATH(self):
        """Backward-compat alias used by old references."""
        return self._DQN_CACHE_PATH if USE_DQN else self._QL_CACHE_PATH

    def load_or_train_agents(self, force=False):
        """Train RL agents and cache for fast restart.

        When USE_DQN is True, trains one DQNAgent per product category
        with per-SKU embeddings.  Otherwise falls back to tabular
        Q-Learning agents per (category × velocity) cluster.
        """
        import pickle, time

        self.is_training = True

        if USE_DQN:
            self._load_or_train_dqn(force)
        else:
            self._load_or_train_ql(force)

        self.is_training = False

    # ── DQN training path ─────────────────────────────────────────

    def _load_or_train_dqn(self, force=False):
        import time

        # Try loading cached DQN weights
        if not force and os.path.exists(self._DQN_CACHE_PATH):
            try:
                cached = torch.load(self._DQN_CACHE_PATH, map_location="cpu",
                                    weights_only=False)
                self._sku_cluster = cached["sku_cluster"]
                self._sku_to_idx = cached["sku_to_idx"]
                self._cat_to_idx = cached.get("cat_to_idx", {})
                self._sku_metadata = cached.get("sku_metadata", {})
                self.sims = cached["sims"]
                targets = HOURLY_TARGETS if DARK_STORE_MODE else None

                for cat, state in cached["agent_states"].items():
                    agent = DQNAgent(
                        targets=targets or [0, 2500, 5000, 7500, 10000, 15000],
                        num_skus=state["num_skus"],
                        embedding_dim=16,
                        num_categories=state.get("num_categories", DEFAULT_NUM_CATEGORIES),
                        pipeline_horizon=state.get("pipeline_horizon", PIPELINE_HORIZON),
                        use_prioritized_replay=True,
                    )
                    agent.policy_net.load_state_dict(state["policy_net"])
                    agent.target_net.load_state_dict(state["policy_net"])
                    agent.epsilon = state["epsilon"]
                    self.agents[cat] = agent

                print(f"[rl_bridge] Loaded {len(self.agents)} DQN v2 agents from cache")
                return
            except Exception as e:
                print(f"[rl_bridge] DQN cache load failed ({e}), retraining...")

        t0 = time.time()
        catalog = self.get_full_catalog()

        # Group SKUs by category
        cat_skus: dict[str, list[str]] = {}
        for sku, info in catalog.items():
            cat = info["category"]
            cat_skus.setdefault(cat, []).append(sku)

        # Assign embedding indices, category indices, and metadata
        cat_counter = 0
        for cat, skus in cat_skus.items():
            if cat not in self._cat_to_idx:
                self._cat_to_idx[cat] = cat_counter
                cat_counter += 1
            for idx, sku in enumerate(skus):
                self._sku_to_idx[sku] = idx
                self._sku_cluster[sku] = cat
                # Build metadata vector: [price_tier, lead_time_norm, shelf_life_norm, avg_sales_norm]
                info = catalog[sku]
                lo, hi = _CATEGORY_COST.get(cat, _DEFAULT_COST_RANGE)
                price_tier = (info.get("unit_cost", (lo+hi)/2) - lo) / max(hi - lo, 1)
                lead_norm = min(info.get("lead_time", 3) / 14.0, 1.0)
                shelf_hours = _SHELF_LIFE_HOURS.get(cat, _DEFAULT_SHELF_LIFE)
                shelf_norm = min(shelf_hours / 8760.0, 1.0)  # Normalize to 1 year
                sales_norm = min(info.get("avg_daily_sales", 50) / 200.0, 1.0)
                self._sku_metadata[sku] = np.array(
                    [price_tier, lead_norm, shelf_norm, sales_norm], dtype=np.float32
                )

        # DQN uses synthetic data for fast initial training.
        # Real demand adaptation happens via online refinement (Kafka events).
        targets = HOURLY_TARGETS if DARK_STORE_MODE else None

        for cat, skus in cat_skus.items():
            h, s, sp, wc = get_category_sim_params(cat)
            lead_times = [catalog[sk].get("lead_time", 3) for sk in skus]
            avg_lead = max(1, int(round(sum(lead_times) / len(lead_times))))
            if DARK_STORE_MODE:
                avg_lead *= 8

            sim = StochasticSCMSimulator(
                lead_time=avg_lead, holding_cost=h, stockout_cost=s,
                spoilage_rate=sp, waste_unit_cost=wc,
                time_unit="hours" if DARK_STORE_MODE else "days",
            )

            agent = DQNAgent(
                targets=targets or [0, 2500, 5000, 7500, 10000, 15000],
                num_skus=len(skus),
                embedding_dim=16,
                num_categories=max(len(cat_skus), DEFAULT_NUM_CATEGORIES),
                pipeline_horizon=PIPELINE_HORIZON,
                use_prioritized_replay=True,
            )

            # Fast training: 5 representative SKUs × 2 epochs of synthetic data
            sample_count = min(5, len(skus))
            train_skus = skus[:sample_count]

            for sku in train_skus:
                sku_idx = self._sku_to_idx[sku]
                cat_idx = self._cat_to_idx.get(cat, 0)
                metadata = self._sku_metadata.get(sku)
                df_synth = generate_demand_signals(days=30)
                train_dqn_stochastic(sim, agent, df_synth,
                                    sku_id=sku_idx, cat_id=cat_idx,
                                    metadata=metadata, epochs=2)

            agent.epsilon = 0.05
            self.agents[cat] = agent
            self.sims[cat] = sim
            print(f"[rl_bridge] DQN trained: {cat} ({len(skus)} SKUs, "
                  f"sampled {sample_count})")

        elapsed = time.time() - t0
        print(f"[rl_bridge] Trained {len(self.agents)} DQN agents in {elapsed:.1f}s")

        # Save DQN cache
        try:
            agent_states = {}
            for cat, agent in self.agents.items():
                agent_states[cat] = {
                    "policy_net": agent.policy_net.state_dict(),
                    "epsilon": agent.epsilon,
                    "num_skus": agent.policy_net.sku_embedding.num_embeddings,
                    "num_categories": agent.policy_net.cat_embedding.num_embeddings,
                    "pipeline_horizon": agent.pipeline_horizon,
                }
            torch.save({
                "agent_states": agent_states,
                "sims": self.sims,
                "sku_cluster": self._sku_cluster,
                "sku_to_idx": self._sku_to_idx,
                "cat_to_idx": self._cat_to_idx,
                "sku_metadata": self._sku_metadata,
            }, self._DQN_CACHE_PATH)
            print(f"[rl_bridge] DQN cache saved to {self._DQN_CACHE_PATH}")
        except Exception as e:
            print(f"[rl_bridge] DQN cache save failed: {e}")

    # ── Q-Learning training path (fallback) ───────────────────────

    def _load_or_train_ql(self, force=False):
        import pickle, time

        if not force and os.path.exists(self._QL_CACHE_PATH):
            try:
                with open(self._QL_CACHE_PATH, "rb") as f:
                    cached = pickle.load(f)
                self.agents = cached["agents"]
                self.sims = cached["sims"]
                self._sku_cluster = cached["sku_cluster"]
                print(f"[rl_bridge] Loaded {len(self.agents)} QL agents from cache")
                return
            except Exception as e:
                print(f"[rl_bridge] QL cache load failed ({e}), retraining...")

        t0 = time.time()
        catalog = self.get_full_catalog()
        clusters = self._build_clusters(catalog)

        try:
            profiles = load_sku_demand_profiles(_CSV_PATH)
            use_real_data = True
            print(f"[rl_bridge] Loaded real demand profiles for {len(profiles)} SKUs")
        except Exception as e:
            profiles = {}
            use_real_data = False
            print(f"[rl_bridge] WARNING: Could not load demand profiles ({e})")

        for cluster_key, sku_list in clusters.items():
            cat = cluster_key.rsplit("_", 1)[0]
            h, s, sp, wc = get_category_sim_params(cat)
            lead_times = [catalog[sk].get("lead_time", 3) for sk in sku_list]
            avg_lead = max(1, int(round(sum(lead_times) / len(lead_times))))
            if DARK_STORE_MODE:
                avg_lead *= 8

            sim = StochasticSCMSimulator(
                lead_time=avg_lead, holding_cost=h, stockout_cost=s,
                spoilage_rate=sp, waste_unit_cost=wc,
                time_unit="hours" if DARK_STORE_MODE else "days",
            )
            agent = QLearningAgent(
                targets=HOURLY_TARGETS if DARK_STORE_MODE else None
            )

            if use_real_data:
                demands = [profiles[sk]["demand"] for sk in sku_list if sk in profiles]
                signals = [profiles[sk]["promo_signal"] for sk in sku_list if sk in profiles]
                if demands:
                    min_len = min(len(d) for d in demands)
                    avg_demand = np.mean([d[:min_len] for d in demands], axis=0)
                    avg_signal = np.mean([s[:min_len] for s in signals], axis=0)
                    avg_signal = (avg_signal > 0.3).astype(float)
                    train_agent_from_demand_series(sim, agent, avg_demand, avg_signal, epochs=5)
                else:
                    df_synth = generate_demand_signals(days=60)
                    train_agent_stochastic(sim, agent, df_synth, epochs=5)
            else:
                df_synth = generate_demand_signals(days=60)
                train_agent_stochastic(sim, agent, df_synth, epochs=5)

            agent.epsilon = 0.05
            self.agents[cluster_key] = agent
            self.sims[cluster_key] = sim

        elapsed = time.time() - t0
        print(f"[rl_bridge] Trained {len(self.agents)} QL cluster agents in {elapsed:.1f}s")

        try:
            with open(self._QL_CACHE_PATH, "wb") as f:
                pickle.dump({
                    "agents": self.agents,
                    "sims": self.sims,
                    "sku_cluster": self._sku_cluster,
                }, f)
            print(f"[rl_bridge] QL cache saved to {self._QL_CACHE_PATH}")
        except Exception as e:
            print(f"[rl_bridge] QL cache save failed: {e}")

    def _get_agent_for_sku(self, sku: str):
        """Return the agent for a SKU (DQN or QLearning depending on mode)."""
        cluster = self._sku_cluster.get(sku)
        if cluster and cluster in self.agents:
            return self.agents[cluster]

        # Fallback: find by category
        catalog = self.get_full_catalog()
        cat = catalog.get(sku, {}).get("category", "Grocery")
        # Try any agent key matching that category
        for key, agent in self.agents.items():
            if key.startswith(cat) or key == cat:
                return agent

        # Last resort: lazy-init a new agent for this category
        h, s, sp, wc = get_category_sim_params(cat)
        lead_time = catalog.get(sku, {}).get("lead_time", 3)
        self.sims[cat] = StochasticSCMSimulator(
            lead_time=lead_time, holding_cost=h, stockout_cost=s,
            spoilage_rate=sp, waste_unit_cost=wc,
        )

        if USE_DQN:
            agent = DQNAgent(
                targets=HOURLY_TARGETS if DARK_STORE_MODE else [0, 2500, 5000, 7500, 10000, 15000],
                num_skus=100,  # generous default
                embedding_dim=16,
                num_categories=DEFAULT_NUM_CATEGORIES,
                pipeline_horizon=PIPELINE_HORIZON,
                use_prioritized_replay=True,
            )
            cat_idx = self._cat_to_idx.get(cat, 0)
            # Build minimal metadata for this SKU
            info = catalog.get(sku, {})
            sales_norm = min(info.get("avg_daily_sales", 50) / 200.0, 1.0)
            lead_norm = min(info.get("lead_time", 3) / 14.0, 1.0)
            metadata = np.array([0.5, lead_norm, 0.5, sales_norm], dtype=np.float32)
            self._sku_metadata[sku] = metadata

            df_synth = generate_demand_signals(days=60)
            train_dqn_stochastic(self.sims[cat], agent, df_synth,
                                sku_id=0, cat_id=cat_idx,
                                metadata=metadata, epochs=3)
            agent.epsilon = 0.05
            self._sku_to_idx[sku] = 0
        else:
            agent = QLearningAgent()
            df_synth = generate_demand_signals(days=90)
            train_agent_stochastic(self.sims[cat], agent, df_synth, epochs=30)
            agent.epsilon = 0.05

        self.agents[cat] = agent
        self._sku_cluster[sku] = cat
        return agent

    def _get_ppo_agent_for_sku(self, sku: str) -> PPOAgent:
        """Return or lazy-init a PPO agent for a SKU's category."""
        cat = self._sku_cluster.get(sku)
        if not cat:
            catalog = self.get_full_catalog()
            cat = catalog.get(sku, {}).get("category", "Grocery")
            self._sku_cluster[sku] = cat

        if cat in self._ppo_agents:
            return self._ppo_agents[cat]

        # Lazy-init: create and train a new PPO agent for this category
        catalog = self.get_full_catalog()
        cat_skus = [s for s, info in catalog.items() if info["category"] == cat]

        h, s, sp, wc = get_category_sim_params(cat)
        lead_times = [catalog[sk].get("lead_time", 3) for sk in cat_skus]
        avg_lead = max(1, int(round(sum(lead_times) / max(len(lead_times), 1))))
        if DARK_STORE_MODE:
            avg_lead *= 8

        sim = StochasticSCMSimulator(
            lead_time=avg_lead, holding_cost=h, stockout_cost=s,
            spoilage_rate=sp, waste_unit_cost=wc,
            time_unit="hours" if DARK_STORE_MODE else "days",
        )

        max_qty = max(HOURLY_TARGETS) if DARK_STORE_MODE else 15000
        ppo_agent = PPOAgent(
            num_skus=max(len(cat_skus), 100),
            max_order_qty=float(max_qty),
            num_categories=DEFAULT_NUM_CATEGORIES,
            pipeline_horizon=PIPELINE_HORIZON,
        )

        # Quick training on synthetic data
        df_synth = generate_demand_signals(days=30)
        sku_idx = self._sku_to_idx.get(sku, 0)
        cat_idx = self._cat_to_idx.get(cat, 0)
        metadata = self._sku_metadata.get(sku)
        train_ppo_stochastic(sim, ppo_agent, df_synth,
                            sku_id=sku_idx, cat_id=cat_idx,
                            metadata=metadata, epochs=3)

        self._ppo_agents[cat] = ppo_agent
        print(f"[rl_bridge] PPO agent trained for category: {cat}")
        return ppo_agent

    def _get_rl_action(self, sku: str, store_id: str | None = None) -> int | float:
        store = self._get_store(store_id)
        state = store.inventory_state[sku]
        
        age_mat = np.asarray(state.get("age_matrix", np.zeros(SHELF_LIFE_HORIZON)), dtype=np.float32) * 50
        fresh_ovr = state.get("fresh_overflow", 0.0) * 50
        inv_scaled = float(np.sum(age_mat) + fresh_ovr)

        pad_seq = lambda seq: np.array([[q * 50, eta] for q, eta in seq] + [[0.0, 0.0]] * max(0, MAX_PIPELINE_SEQUENCE - len(seq)), dtype=np.float32).flatten()

        # ── PPO path: continuous action ──
        if USE_PPO:
            cat = self._sku_cluster.get(sku, "Grocery")
            ppo_agent = self._get_ppo_agent_for_sku(sku)
            pipeline_seq = pad_seq(state.get("pipeline_seq", []))
            sku_idx = self._sku_to_idx.get(sku, 0)
            cat_idx = self._cat_to_idx.get(cat, 0)
            metadata = self._sku_metadata.get(sku)
            action_qty, _, _ = ppo_agent.act(
                age_mat, fresh_ovr, pipeline_seq, state["signal"],
                sku_id=sku_idx, cat_id=cat_idx,
                metadata=metadata, explore=False,
            )
            # PPO returns continuous qty — round to int for retail
            return max(0, round(action_qty))

        # ── DQN path: discrete action ──
        agent = self._get_agent_for_sku(sku)

        if USE_DQN and isinstance(agent, DQNAgent):
            sku_idx = self._sku_to_idx.get(sku, 0)
            cat = self._sku_cluster.get(sku, "Grocery")
            cat_idx = self._cat_to_idx.get(cat, 0)
            metadata = self._sku_metadata.get(sku)
            pipeline_seq = pad_seq(state.get("pipeline_seq", []))
            raw_action = agent.act(
                age_mat, fresh_ovr, pipeline_seq, state["signal"],
                sku_id=sku_idx, cat_id=cat_idx,
                metadata=metadata, explore=False,
            )
        else:
            pipe_scaled = float(np.sum(state["pipeline"])) * 50 if isinstance(state["pipeline"], (np.ndarray, list)) else state.get("pipeline_sum", 0) * 50
            raw_action = agent.act(
                inv_scaled, pipe_scaled, state["signal"], explore=False,
            )

        if DARK_STORE_MODE:
            return RL_TO_RETAIL_QTY_HOURLY.get(raw_action, 10)
        return RL_TO_RETAIL_QTY.get(raw_action, 25)

    def _get_rl_confidence(self, sku: str, store_id: str | None = None) -> float:
        store = self._get_store(store_id)
        state = store.inventory_state[sku]
        agent = self._get_agent_for_sku(sku)
        
        age_mat = np.asarray(state.get("age_matrix", np.zeros(SHELF_LIFE_HORIZON)), dtype=np.float32) * 50
        fresh_ovr = state.get("fresh_overflow", 0.0) * 50
        pad_seq = lambda seq: np.array([[q * 50, eta] for q, eta in seq] + [[0.0, 0.0]] * max(0, MAX_PIPELINE_SEQUENCE - len(seq)), dtype=np.float32).flatten()

        if USE_PPO:
            ppo_agent = self._get_ppo_agent_for_sku(sku)
            pipeline_seq = pad_seq(state.get("pipeline_seq", []))
            from SignalCoreAI.dqn_engine import _build_state_array
            state_arr = _build_state_array(age_mat, fresh_ovr, state["signal"], pipeline_seq)
            state_t = torch.FloatTensor(state_arr).unsqueeze(0).to(ppo_agent.device)
            sku_t = torch.LongTensor([self._sku_to_idx.get(sku, 0)]).to(ppo_agent.device)
            cat = self._sku_cluster.get(sku, "Grocery")
            cat_t = torch.LongTensor([self._cat_to_idx.get(cat, 0)]).to(ppo_agent.device)
            metadata = self._sku_metadata.get(sku)
            meta_t = torch.FloatTensor([metadata if metadata is not None else np.zeros(DEFAULT_METADATA_DIM)]).to(ppo_agent.device)
            with torch.no_grad():
                mean, std, _ = ppo_agent.network(state_t, sku_t, cat_t, meta_t)
            confidence = 1.0 / (1.0 + float(std.item()) / max(float(mean.item()), 1.0))
            return round(min(0.99, max(0.1, confidence)), 2)

        if USE_DQN and isinstance(agent, DQNAgent):
            sku_idx = self._sku_to_idx.get(sku, 0)
            cat = self._sku_cluster.get(sku, "Grocery")
            cat_idx = self._cat_to_idx.get(cat, 0)
            metadata = self._sku_metadata.get(sku)
            pipeline_seq = pad_seq(state.get("pipeline_seq", []))
            
            from SignalCoreAI.dqn_engine import _build_state_array
            state_arr = _build_state_array(age_mat, fresh_ovr, state["signal"], pipeline_seq)
            state_t = torch.FloatTensor(state_arr).unsqueeze(0).to(agent.device)
            sku_t = torch.LongTensor([sku_idx]).to(agent.device)
            cat_t = torch.LongTensor([cat_idx]).to(agent.device)
            meta_t = torch.FloatTensor([metadata if metadata is not None else np.zeros(DEFAULT_METADATA_DIM)]).to(agent.device)
            with torch.no_grad():
                q_vals = agent.policy_net(state_t, sku_t, cat_t, meta_t).squeeze()
            probs = torch.softmax(q_vals, dim=0)
            return round(float(probs.max().item()), 2)

        # Tabular Q-learning fallback
        s = agent.get_state(inv_scaled, pipe_scaled, state["signal"])
        if s in agent.q:
            q_vals = agent.q[s]
            total = np.sum(np.abs(q_vals))
            if total > 0:
                return round(float(np.max(q_vals) / (total + 1e-8)), 2)
        return 0.5

    def _assign_priority(self, sku: str, catalog: dict, store_id: str | None = None) -> AlertPriority:
        store = self._get_store(store_id)
        state = store.inventory_state[sku]
        base = catalog[sku]["base_stock"]
        ratio = state["on_hand"] / base

        # Expiry-based priority boost
        shelf_life = state.get("shelf_life_hours", _DEFAULT_SHELF_LIFE)
        batch_age = state.get("oldest_batch_hours", 0)
        remaining_pct = 1.0 - (batch_age / max(shelf_life, 1))

        if remaining_pct < 0.15:  # <15% shelf life left
            return AlertPriority.CRITICAL
        if remaining_pct < 0.30:  # <30%
            return AlertPriority.HIGH

        if ratio < 0.3 or state.get("signal", 0) == 1:
            return AlertPriority.CRITICAL
        if ratio < 0.5:
            return AlertPriority.HIGH
        if ratio < 0.7:
            return AlertPriority.MEDIUM
        return AlertPriority.LOW

    def _get_expiry_risk(self, sku: str, store_id: str | None = None) -> str:
        """Return expiry risk level: green/yellow/red."""
        store = self._get_store(store_id)
        state = store.inventory_state[sku]
        shelf_life = state.get("shelf_life_hours", _DEFAULT_SHELF_LIFE)
        batch_age = state.get("oldest_batch_hours", 0)
        remaining_pct = 1.0 - (batch_age / max(shelf_life, 1))
        if remaining_pct < 0.25:
            return "red"
        if remaining_pct < 0.50:
            return "yellow"
        return "green"

    def _pick_reason(self, sku: str, priority: AlertPriority) -> str:
        state = self.inventory_state[sku]
        now = datetime.now()

        if now.month in MONSOON_MONTHS:
            return "Monsoon Supply Chain Disruption Expected"
        if state["signal"] == 1:
            return random.choice(
                [
                    "Festival Demand Surge — Ugadi Season",
                    "Dasara/Dussehra Week — Mysuru Corridor Spike",
                    "IPL Season — RCB Match-Day Snack Surge",
                    "Sankranti Harvest Festival — Bulk Staples Demand",
                ]
            )
        if priority in (AlertPriority.CRITICAL, AlertPriority.HIGH):
            return random.choice(
                ["Reorder Point Breached", "Pipeline Stockout Imminent"]
            )
        return random.choice(
            [
                "Competitor Promo Detected - Price Match Window",
                "Spoilage Risk - High Humidity Alert",
            ]
        )


    @staticmethod
    def _infer_fulfillment_channel(category: str, priority: str) -> str:
        """Auto-tag the BigBasket fulfillment channel for a directive.

        - bb_now:     Urgent/critical items or perishables needing 10-20 min delivery
        - bb_daily:   Subscription staples (milk, eggs, bread) for early-morning delivery
        - bb_slotted: Bulk staples/household for same-day/next-day scheduled delivery
        """
        cat_lower = category.lower()
        # Daily subscription items
        if any(k in cat_lower for k in ("dairy", "egg", "milk", "bread", "bakery")):
            return "bb_daily"
        # Urgent perishables and critical alerts → BB Now
        if priority in ("critical", "high") or any(k in cat_lower for k in ("meat", "seafood", "fruit", "veg")):
            return "bb_now"
        # Everything else → scheduled slotted delivery
        if any(k in cat_lower for k in ("staple", "grain", "household", "personal", "spice")):
            return "bb_slotted"
        return "bb_now"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_directives(self, category_filter: str | None = None,
                            limit: int = 25, store_id: str | None = None) -> list:
                            
        # Check cache (invalidate after 5 minutes)
        import time
        now = time.time()
        sid = store_id or "DS-BLR-INDIRANAGAR"
        cache_key = f"{sid}_{category_filter or 'ALL'}"
        if cache_key in self._directive_cache:
            entry = self._directive_cache[cache_key]
            if now - entry["timestamp"] < 300:  # 5 minute TTL
                return entry["directives"][:limit], entry.get("truck_utilization", 1.0)

        # Refresh dynamic catalog from DB
        self.load_dynamic_catalog()
        catalog = self.get_full_catalog()
        store = self._get_store(store_id)

        # --- Vectorized Matrix Computations (BigBasket Bootstrapping) ---
        import numpy as np
        
        skus = list(catalog.keys())
        # Allocate tensors
        on_hand_arr = np.array([store.inventory_state.get(s, {}).get("on_hand", 0) for s in skus])
        forward_arr = np.array([store.inventory_state.get(s, {}).get("forward_booked", 0) for s in skus])
        base_arr = np.array([max(catalog[s]["base_stock"], 1) for s in skus])
        signal_arr = np.array([store.inventory_state.get(s, {}).get("signal", 0) for s in skus])

        # Execute C-Optimized Vector Math
        effective_arr = on_hand_arr - forward_arr
        ratio_arr = effective_arr / base_arr
        needs_action_mask = (ratio_arr < 0.7) | (signal_arr == 1)
        
        actionable_set = set(skus[i] for i, mask in enumerate(needs_action_mask) if mask)
        # ----------------------------------------------------------------

        # ── Batched RL Inference ──
        actionable_list = []
        for sku in catalog:
            if category_filter and catalog[sku]["category"] != category_filter:
                continue
            if sku not in store.inventory_state:
                continue
            if sku in actionable_set or self._get_expiry_risk(sku, store.store_id) in ("yellow", "red"):
                actionable_list.append(sku)

        rec_qty_map = {}
        conf_map = {}
        agent_to_skus = {}
        
        for sku in actionable_list:
            if USE_PPO:
                cat = self._sku_cluster.get(sku) or catalog[sku].get("category", "Grocery")
                self._sku_cluster[sku] = cat
                agent_to_skus.setdefault(cat, []).append(sku)
            else:
                agent = self._get_agent_for_sku(sku)
                agent_to_skus.setdefault(agent, []).append(sku)

        if USE_PPO:
            for cat, batch_skus in agent_to_skus.items():
                ppo_agent = self._get_ppo_agent_for_sku(batch_skus[0])
                pad_seq = lambda seq: np.array([[q * 50, eta] for q, eta in seq] + [[0.0, 0.0]] * max(0, MAX_PIPELINE_SEQUENCE - len(seq)), dtype=np.float32).flatten()
                
                age_mats = [np.asarray(store.inventory_state[s].get("age_matrix", np.zeros(SHELF_LIFE_HORIZON))) * 50 for s in batch_skus]
                fresh_ovrs = [store.inventory_state[s].get("fresh_overflow", 0.0) * 50 for s in batch_skus]
                seqs = [pad_seq(store.inventory_state[s].get("pipeline_seq", [])) for s in batch_skus]
                sigs = [store.inventory_state[s]["signal"] for s in batch_skus]
                sku_ids = [self._sku_to_idx.get(s, 0) for s in batch_skus]
                cat_ids = [self._cat_to_idx.get(self._sku_cluster.get(s, "Grocery"), 0) for s in batch_skus]
                metas = [self._sku_metadata.get(s, np.zeros(DEFAULT_METADATA_DIM)) for s in batch_skus]
                
                actions, confs = ppo_agent.act_batched(age_mats, fresh_ovrs, seqs, sigs, sku_ids, cat_ids, metas, explore=False)
                for s, a, c in zip(batch_skus, actions, confs):
                    rec_qty_map[s] = max(0, round(a))
                    conf_map[s] = round(c, 2)
        else:
            for agent, batch_skus in agent_to_skus.items():
                if USE_DQN and isinstance(agent, DQNAgent):
                    pad_seq = lambda seq: np.array([[q * 50, eta] for q, eta in seq] + [[0.0, 0.0]] * max(0, MAX_PIPELINE_SEQUENCE - len(seq)), dtype=np.float32).flatten()
                    
                    age_mats = [np.asarray(store.inventory_state[s].get("age_matrix", np.zeros(SHELF_LIFE_HORIZON))) * 50 for s in batch_skus]
                    fresh_ovrs = [store.inventory_state[s].get("fresh_overflow", 0.0) * 50 for s in batch_skus]
                    seqs = [pad_seq(store.inventory_state[s].get("pipeline_seq", [])) for s in batch_skus]
                    sigs = [store.inventory_state[s]["signal"] for s in batch_skus]
                    sku_ids = [self._sku_to_idx.get(s, 0) for s in batch_skus]
                    cat_ids = [self._cat_to_idx.get(self._sku_cluster.get(s, "Grocery"), 0) for s in batch_skus]
                    metas = [self._sku_metadata.get(s, np.zeros(DEFAULT_METADATA_DIM)) for s in batch_skus]
                    
                    raw_actions, confs = agent.act_batched(age_mats, fresh_ovrs, seqs, sigs, sku_ids, cat_ids, metas, explore=False)
                    for s, ra, c in zip(batch_skus, raw_actions, confs):
                        rec_qty_map[s] = RL_TO_RETAIL_QTY_HOURLY.get(ra, 10) if DARK_STORE_MODE else RL_TO_RETAIL_QTY.get(ra, 25)
                        conf_map[s] = round(c, 2)
                else:
                    for s in batch_skus:
                        rec_qty_map[s] = self._get_rl_action(s, store.store_id)
                        conf_map[s] = self._get_rl_confidence(s, store.store_id)
        # ──────────────────────────

        directives = []

        for sku in actionable_list:
            info = catalog[sku]
            state = store.inventory_state[sku]
            expiry_risk = self._get_expiry_risk(sku, store.store_id)
            
            rec_qty = rec_qty_map[sku]
            
            # Hub vs CDC routing logic
            store_model = next((s for s in self.dark_stores if s.store_id == store.store_id), None)
            is_cdc = store_model and store_model.facility_type == "cdc"
            
            dir_type = "purchase" if is_cdc else "replenishment"
            transfer_source = store_model.parent_cdc if (store_model and not is_cdc) else None

            # FEFO Flash Sale Intercept
            if expiry_risk in ("yellow", "red") and state["on_hand"] > 0:
                dir_type = "discount"
                rec_qty = state["on_hand"]
            elif rec_qty == 0:
                continue

            # Check Fleet Rebalancing only if it's a standard restock
            if dir_type in ("purchase", "replenishment"):
                for other_sid, other_store in self.stores.items():
                    if other_sid == store.store_id:
                        continue
                    if sku in other_store.inventory_state:
                        other_state = other_store.inventory_state[sku]
                        other_base = info["base_stock"]
                        if other_state["on_hand"] > (1.5 * other_base) + rec_qty:
                            dir_type = "transfer"
                            transfer_source = other_sid
                            break

            priority = self._assign_priority(sku, catalog, store.store_id)

            # Compute lead time
            sku_lead_days = self.get_effective_lead_time(sku)
            lead_time_hours = sku_lead_days * 8 if DARK_STORE_MODE else None

            # Shelf life info
            shelf_life_h = state.get("shelf_life_hours", _DEFAULT_SHELF_LIFE)
            batch_age_h = state.get("oldest_batch_hours", 0)

            # Reason — add expiry warning for perishables
            if expiry_risk == "red":
                reason = f"Approaching Expiry — {shelf_life_h - batch_age_h}h remaining"
            elif expiry_risk == "yellow":
                reason = f"Shelf Life Warning — {shelf_life_h - batch_age_h}h remaining"
            else:
                reason = self._pick_reason(sku, priority)

            directives.append(
                Directive(
                    id=f"DIR-{uuid.uuid4().hex[:8].upper()}",
                    sku=sku,
                    product_name=info["name"],
                    current_stock=state["on_hand"],
                    pipeline_stock=int(state.get("pipeline_sum", 0)),
                    reason=reason,
                    priority=priority,
                    recommended_qty=rec_qty,
                    status=DirectiveStatus.PENDING,
                    estimated_arrival=date.today() + timedelta(days=sku_lead_days),
                    rl_state={
                        "inventory": state["on_hand"],
                        "pipeline": int(state.get("pipeline_sum", 0)),
                        "signal": state["signal"],
                    },
                    rl_confidence=conf_map[sku],
                    store_id=store.store_id,
                    lead_time_hours=lead_time_hours,
                    shelf_life_hours=shelf_life_h,
                    expiry_risk=expiry_risk,
                    oldest_batch_hours=batch_age_h,
                    directive_type=dir_type,
                    transfer_source=transfer_source,
                    fulfillment_channel=self._infer_fulfillment_channel(info.get("category", "General"), priority),
                )
            )

        priority_order = {
            AlertPriority.CRITICAL: 0,
            AlertPriority.HIGH: 1,
            AlertPriority.MEDIUM: 2,
            AlertPriority.LOW: 3,
        }
        directives.sort(key=lambda d: priority_order[d.priority])
        
        utilization = 1.0

        self._directive_cache[cache_key] = {
            "timestamp": now, 
            "directives": directives,
            "truck_utilization": utilization
        }
        return directives[:limit], utilization

    def apply_budget_constraint(
        self, directives: list, daily_budget: float | None = None
    ) -> tuple[list, BudgetSummary]:
        """Fast greedy knapsack: O(n log n) budget allocation.

        Scores each directive by urgency/cost ratio, greedily funds
        the highest-value directives until the budget is exhausted.
        Remaining directives are marked 'deferred'.
        """
        budget = daily_budget if daily_budget is not None else self.daily_budget
        catalog = self.get_full_catalog()

        # Compute estimated cost & urgency score
        scored: list[tuple[float, int, Directive]] = []
        for i, d in enumerate(directives):
            info = catalog.get(d.sku, {})
            unit_cost = info.get("unit_cost", 100.0)
            d.estimated_cost = round(unit_cost * d.recommended_qty, 2)

            base_stock = info.get("base_stock", 50)
            stock_ratio = d.current_stock / max(base_stock, 1)
            urgency = (
                _PRIORITY_WEIGHTS.get(d.priority, 1.0)
                * (1.0 - min(stock_ratio, 1.0))
                * d.rl_confidence
            )
            efficiency = urgency / max(d.estimated_cost, 0.01)
            scored.append((efficiency, i, d))

        # Sort descending by efficiency
        scored.sort(key=lambda x: x[0], reverse=True)

        total_allocated = 0.0
        funded_count = 0
        deferred_count = 0

        for _, _, d in scored:
            if total_allocated + d.estimated_cost <= budget:
                d.budget_status = "funded"
                total_allocated += d.estimated_cost
                funded_count += 1
            else:
                d.budget_status = "deferred"
                deferred_count += 1

        summary = BudgetSummary(
            daily_budget=budget,
            total_allocated=round(total_allocated, 2),
            remaining=round(budget - total_allocated, 2),
            funded_count=funded_count,
            deferred_count=deferred_count,
        )
        return directives, summary

    def confirm_order(self, sku: str, quantity: int):
        self.inventory_state[sku]["pipeline"] += quantity
        self.confirmed_orders.append(
            {
                "sku": sku,
                "quantity": quantity,
                "confirmed_at": datetime.now().isoformat(),
            }
        )

    def log_rlhf_feedback(self, adjustment) -> str:
        feedback_id = f"FB-{uuid.uuid4().hex[:8].upper()}"
        self.feedback_log.append(
            {
                "feedback_id": feedback_id,
                "directive_id": adjustment.directive_id,
                "sku": adjustment.sku,
                "original_qty": adjustment.original_qty,
                "adjusted_qty": adjustment.adjusted_qty,
                "reason": adjustment.reason,
                "timestamp": datetime.now().isoformat(),
                "delta": adjustment.adjusted_qty - adjustment.original_qty,
            }
        )
        if adjustment.adjusted_qty > 0:
            self.inventory_state[adjustment.sku]["pipeline"] += adjustment.adjusted_qty
        return feedback_id

    def update_inventory(self, sku: str, new_qty: int) -> InventoryAuditResponse:
        prev = self.inventory_state[sku]["on_hand"]
        self.inventory_state[sku]["on_hand"] = new_qty
        return InventoryAuditResponse(
            sku=sku,
            previous_qty=prev,
            new_qty=new_qty,
            synced=True,
            state_updated=True,
        )

    def get_effective_lead_time(self, sku: str | None = None) -> int:
        """Return effective lead time, optionally per-SKU.

        Uses the SKU's cataloged lead_time when available, otherwise
        falls back to the cluster sim's lead_time.  Monsoon adds +3 days.
        """
        if sku:
            catalog = self.get_full_catalog()
            base = catalog.get(sku, {}).get("lead_time", 3)
        else:
            base = next(iter(self.sims.values())).lead_time if self.sims else 3
        if datetime.now().month in MONSOON_MONTHS:
            return base + 3
        return base

    def get_monsoon_status(self) -> MonsoonStatus:
        now = datetime.now()
        if now.month in MONSOON_MONTHS:
            severity = "severe" if now.month in (7, 8) else "moderate"
            delay = 4 if severity == "severe" else 2
            return MonsoonStatus(
                active=True,
                severity=severity,
                additional_delay_days=delay,
                message=f"Monsoon active — expect +{delay} day delays on Goa logistics routes",
            )
        return MonsoonStatus(
            active=False,
            severity="none",
            additional_delay_days=0,
            message="No monsoon disruption — standard lead times apply",
        )

    # ------------------------------------------------------------------
    # Store Management
    # ------------------------------------------------------------------

    @property
    def dark_store_mode(self) -> bool:
        return DARK_STORE_MODE

    def get_all_stores(self) -> list[DarkStore]:
        return list(self.dark_stores)

    def add_store(self, store_id: str, name: str, location: str, zone: str) -> DarkStore:
        """Add a new dark store and initialize its inventory."""
        if store_id in self.stores:
            raise ValueError(f"Store {store_id} already exists")
        ds = DarkStore(store_id=store_id, name=name, location=location, zone=zone)
        self.dark_stores.append(ds)
        self.stores[store_id] = StoreState(store_id)

        # Copy inventory from central with slight variations
        for sku, info in PRODUCT_CATALOG.items():
            stock = info["base_stock"]
            variance = random.randint(-int(stock * 0.3), int(stock * 0.1))
            shelf_life = _SHELF_LIFE_HOURS.get(info["category"], _DEFAULT_SHELF_LIFE)
            batch_age = random.randint(1, max(1, int(shelf_life * 0.5)))
            self.stores[store_id].inventory_state[sku] = {
                "on_hand": max(5, stock + variance),
                "pipeline": 0,
                "signal": random.choice([0, 0, 0, 0, 0, 0, 0, 0, 0, 1]), # 10% chance of high demand signal
                "oldest_batch_hours": batch_age,
                "shelf_life_hours": shelf_life,
            }
        return ds

    def get_shelf_life_status(self, store_id: str | None = None,
                              category_filter: str | None = None) -> list[ShelfLifeStatus]:
        """Return shelf life status for all SKUs in a store."""
        store = self._get_store(store_id)
        catalog = self.get_full_catalog()
        results = []
        for sku, state in store.inventory_state.items():
            info = catalog.get(sku, {})
            if not info:
                continue
            if category_filter and info.get("category") != category_filter:
                continue
            shelf_life = state.get("shelf_life_hours", _DEFAULT_SHELF_LIFE)
            batch_age = state.get("oldest_batch_hours", 0)
            remaining = max(0, shelf_life - batch_age)
            results.append(ShelfLifeStatus(
                sku=sku,
                product_name=info.get("name", sku),
                category=info.get("category", "General"),
                shelf_life_hours=shelf_life,
                oldest_batch_hours=batch_age,
                remaining_hours=remaining,
                expiry_risk=self._get_expiry_risk(sku, store_id),
            ))
        # Sort by remaining hours ascending (most urgent first)
        results.sort(key=lambda s: s.remaining_hours)
        return results
