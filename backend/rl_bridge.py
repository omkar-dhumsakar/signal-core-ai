"""Bridge between FastAPI and the SignalCoreAI RL Agent.

Translates RL state/action representations into retail-friendly
directives for the StoreOps mobile app.
"""

import sys
import os
import random
import uuid
import numpy as np
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from SignalCoreAI.scm_engine import (
    QLearningAgent,
    StochasticSCMSimulator,
    train_agent_stochastic,
    train_agent_from_demand_series,
    get_category_sim_params,
    HOURLY_TARGETS,
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

# ── Dark Store Mode ───────────────────────────────────────────────────
DARK_STORE_MODE = True  # Set False for traditional retail mode

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
        self.agents: dict[str, QLearningAgent] = {}   # keyed by cluster
        self.sims: dict[str, StochasticSCMSimulator] = {}
        self._dynamic_catalog: dict = {}
        self.daily_budget: float = _DEFAULT_DAILY_BUDGET
        self._sku_cluster: dict[str, str] = {}        # sku → cluster key

        # Multi-store support
        self.stores: dict[str, StoreState] = {}
        self.dark_stores: list[DarkStore] = list(_DEFAULT_STORES)

        # Initialize stores with inventory
        for ds in self.dark_stores:
            self.stores[ds.store_id] = StoreState(ds.store_id)
        self._init_all_stores()
        
        self.is_training: bool = False
        self._directive_cache: dict[str, dict] = {} # store_id -> {timestamp, directives}

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
                # Each store gets slightly different stock levels
                seed_offset = hash(ds.store_id + sku) % 20 - 10
                variance = random.randint(-int(stock * 0.3), int(stock * 0.1)) + seed_offset
                shelf_life = _SHELF_LIFE_HOURS.get(info["category"], _DEFAULT_SHELF_LIFE)
                # Simulate oldest batch age (random fraction of shelf life)
                batch_age_hours = random.randint(1, max(1, int(shelf_life * 0.6)))
                store.inventory_state[sku] = {
                    "on_hand": max(5, stock + variance),
                    "pipeline": random.choice([0, 0, 0, 10, 20, 30]),
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
                self.inventory_state[sku] = {
                    "on_hand": max(5, base_stock + variance),
                    "pipeline": random.choice([0, 0, 0, 5, 10]),
                    "signal": random.choice([0, 0, 0, 1]),
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

    _CACHE_PATH = os.path.join(os.path.dirname(__file__), ".rl_cache.pkl")

    def load_or_train_agents(self, force=False):
        """Train one Q-table per demand cluster, or load from cache."""
        import pickle, time
        
        self.is_training = True

        # Try loading from cache first (if not forcing retrain)
        if not force and os.path.exists(self._CACHE_PATH):
            try:
                with open(self._CACHE_PATH, "rb") as f:
                    cached = pickle.load(f)
                self.agents = cached["agents"]
                self.sims = cached["sims"]
                self._sku_cluster = cached["sku_cluster"]
                print(f"[rl_bridge] Loaded {len(self.agents)} agents from cache (instant)")
                self.is_training = False
                return
            except Exception as e:
                print(f"[rl_bridge] Cache load failed ({e}), retraining...")

        t0 = time.time()
        catalog = self.get_full_catalog()
        clusters = self._build_clusters(catalog)

        # Load real demand profiles from CSV
        try:
            profiles = load_sku_demand_profiles(_CSV_PATH)
            use_real_data = True
            print(f"[rl_bridge] Loaded real demand profiles for {len(profiles)} SKUs")
        except Exception as e:
            profiles = {}
            use_real_data = False
            print(f"[rl_bridge] WARNING: Could not load demand profiles ({e}), using synthetic data")

        for cluster_key, sku_list in clusters.items():
            cat = cluster_key.rsplit("_", 1)[0]
            h, s, sp, wc = get_category_sim_params(cat)

            lead_times = [catalog[sk].get("lead_time", 3) for sk in sku_list]
            avg_lead = max(1, int(round(sum(lead_times) / len(lead_times))))

            if DARK_STORE_MODE:
                avg_lead_final = avg_lead * 8
            else:
                avg_lead_final = avg_lead

            sim = StochasticSCMSimulator(
                lead_time=avg_lead_final, holding_cost=h, stockout_cost=s,
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
        print(f"[rl_bridge] Trained {len(self.agents)} cluster agents in {elapsed:.1f}s")

        # Save to cache for instant next startup
        try:
            with open(self._CACHE_PATH, "wb") as f:
                pickle.dump({
                    "agents": self.agents,
                    "sims": self.sims,
                    "sku_cluster": self._sku_cluster,
                }, f)
            print(f"[rl_bridge] Saved cache to {self._CACHE_PATH}")
        except Exception as e:
            print(f"[rl_bridge] Cache save failed: {e}")
            
        self.is_training = False

    def _get_agent_for_sku(self, sku: str) -> QLearningAgent:
        """Return the cluster-specific agent for a SKU."""
        cluster = self._sku_cluster.get(sku)
        if cluster and cluster in self.agents:
            return self.agents[cluster]

        # Fallback: find by category
        catalog = self.get_full_catalog()
        cat = catalog.get(sku, {}).get("category", "Grocery")
        # Try any cluster matching that category
        for key, agent in self.agents.items():
            if key.startswith(cat):
                return agent

        # Last resort: lazy-init a new agent
        h, s, sp, wc = get_category_sim_params(cat)
        lead_time = catalog.get(sku, {}).get("lead_time", 3)
        self.sims[cat] = StochasticSCMSimulator(
            lead_time=lead_time, holding_cost=h, stockout_cost=s,
            spoilage_rate=sp, waste_unit_cost=wc,
        )
        agent = QLearningAgent()
        df_synth = generate_demand_signals(days=90)
        train_agent_stochastic(self.sims[cat], agent, df_synth, epochs=30)
        agent.epsilon = 0.05
        self.agents[cat] = agent
        self._sku_cluster[sku] = cat
        return agent

    def _get_rl_action(self, sku: str, store_id: str | None = None) -> int:
        store = self._get_store(store_id)
        state = store.inventory_state[sku]
        inv_scaled = state["on_hand"] * 50
        pipe_scaled = state["pipeline"] * 50
        agent = self._get_agent_for_sku(sku)
        raw_action = agent.act(
            inv_scaled, pipe_scaled, state["signal"], explore=False
        )
        if DARK_STORE_MODE:
            return RL_TO_RETAIL_QTY_HOURLY.get(raw_action, 10)
        return RL_TO_RETAIL_QTY.get(raw_action, 25)

    def _get_rl_confidence(self, sku: str, store_id: str | None = None) -> float:
        store = self._get_store(store_id)
        state = store.inventory_state[sku]
        inv_scaled = state["on_hand"] * 50
        pipe_scaled = state["pipeline"] * 50
        agent = self._get_agent_for_sku(sku)
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

        directives = []

        for sku, info in catalog.items():
            # Apply category filter if provided
            if category_filter and info["category"] != category_filter:
                continue

            if sku not in store.inventory_state:
                continue
                
            state = store.inventory_state[sku]
            expiry_risk = self._get_expiry_risk(sku, store.store_id)
            
            # Combine Tensor bool with Python string check
            if sku not in actionable_set and expiry_risk not in ("yellow", "red"):
                continue

            rec_qty = self._get_rl_action(sku, store.store_id)
            
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
                    pipeline_stock=state["pipeline"],
                    reason=reason,
                    priority=priority,
                    recommended_qty=rec_qty,
                    status=DirectiveStatus.PENDING,
                    estimated_arrival=date.today() + timedelta(days=sku_lead_days),
                    rl_state={
                        "inventory": state["on_hand"],
                        "pipeline": state["pipeline"],
                        "signal": state["signal"],
                    },
                    rl_confidence=self._get_rl_confidence(sku, store.store_id),
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
