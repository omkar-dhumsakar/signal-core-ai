"""Multi-echelon network coordinator for supply chain constraints.

Fix #5: Individual per-SKU RL agents operate in isolation, ignoring
network-level constraints. This coordinator sits between the RL
agents and the PO generator, applying:

1. Warehouse capacity constraints — total inbound capped per store
2. Supplier capacity constraints — total outbound capped per supplier
3. Cross-store rebalancing — transfer surplus between sibling stores
   instead of ordering from suppliers

Usage:
    coordinator = NetworkCoordinator(store_caps, supplier_caps)
    adjusted = coordinator.coordinate(raw_actions, inventory_states)
"""

import numpy as np
from dataclasses import dataclass, field


@dataclass
class StoreCapacity:
    """Warehouse capacity limits for a single store."""
    store_id: str
    max_inbound_units: float = 10000.0   # Max units receivable per cycle
    max_storage_units: float = 50000.0   # Total warehouse capacity
    current_occupancy: float = 0.0       # Current stored units
    facility_type: str = "darkstore"     # cdc, darkstore, hub
    parent_cdc: str | None = None


@dataclass
class SupplierCapacity:
    """Supplier capacity limits."""
    supplier_id: str
    max_daily_units: float = 50000.0     # Max units supplier can ship per day
    current_committed: float = 0.0       # Already committed for today
    categories: list = field(default_factory=list)  # Categories this supplier serves


class NetworkCoordinator:
    """Applies multi-echelon constraints to per-SKU agent decisions.

    Transforms raw RL agent outputs into feasible orders that respect
    physical network constraints.

    Parameters
    ----------
    store_capacities : dict[str, StoreCapacity]
        Warehouse capacity per store.
    supplier_capacities : dict[str, SupplierCapacity]
        Supplier capacity limits.
    rebalance_threshold : float
        Ratio of (on_hand / base_stock) above which a store is
        considered to have surplus available for transfer.
    """

    def __init__(self, store_capacities: dict[str, StoreCapacity] | None = None,
                 supplier_capacities: dict[str, SupplierCapacity] | None = None,
                 rebalance_threshold: float = 1.5):
        self.store_caps = store_capacities or {}
        self.supplier_caps = supplier_capacities or {}
        self.rebalance_threshold = rebalance_threshold

    # ── Core Coordination ─────────────────────────────────────────

    def coordinate(self, raw_actions: dict[str, dict[str, float]],
                   inventory_states: dict[str, dict],
                   catalog: dict,
                   store_graph: dict[str, list[str]] | None = None
                   ) -> dict[str, dict[str, float]]:
        """Adjust individual SKU orders to satisfy network constraints.

        Parameters
        ----------
        raw_actions : dict[store_id, dict[sku_id, order_qty]]
            Raw order quantities from RL agents per store per SKU.
        inventory_states : dict[store_id, dict[sku_id, state_dict]]
            Current inventory state per store per SKU.
        catalog : dict[sku_id, product_info]
            Product catalog with base_stock, category, etc.
        store_graph : dict[store_id, list[store_id]] or None
            Adjacency list defining which stores can transfer to each other.
            If None, uses parent_cdc grouping for siblings.

        Returns
        -------
        dict[str, dict[str, float]]
            Adjusted order quantities per store per SKU.
        """
        adjusted = {}
        transfers = {}

        for store_id, sku_actions in raw_actions.items():
            adjusted[store_id] = dict(sku_actions)

        # Phase 1: Cross-store rebalancing (before ordering from suppliers)
        if store_graph is None:
            store_graph = self._build_sibling_graph()

        transfers = self._identify_transfers(
            adjusted, inventory_states, catalog, store_graph
        )

        # Apply transfers: reduce orders where transfers can satisfy demand
        for transfer in transfers:
            from_store = transfer["from"]
            to_store = transfer["to"]
            sku = transfer["sku"]
            qty = transfer["qty"]

            # Reduce the receiving store's supplier order
            if sku in adjusted.get(to_store, {}):
                adjusted[to_store][sku] = max(0, adjusted[to_store][sku] - qty)

        # Phase 2: Cap store inbound to warehouse capacity
        for store_id, sku_actions in adjusted.items():
            cap = self.store_caps.get(store_id)
            if cap is None:
                continue

            total_inbound = sum(sku_actions.values())
            remaining_capacity = cap.max_storage_units - cap.current_occupancy
            max_inbound = min(cap.max_inbound_units, remaining_capacity)

            if total_inbound > max_inbound and total_inbound > 0:
                # Scale down proportionally
                scale = max_inbound / total_inbound
                for sku in sku_actions:
                    sku_actions[sku] = round(sku_actions[sku] * scale)

        # Phase 3: Cap supplier outbound capacity
        adjusted = self._apply_supplier_constraints(adjusted, catalog)

        return adjusted, transfers

    # ── Transfer Logic ────────────────────────────────────────────

    def _build_sibling_graph(self) -> dict[str, list[str]]:
        """Build sibling graph from parent_cdc relationships.

        Stores with the same parent_cdc can transfer between each other.
        """
        cdc_children: dict[str, list[str]] = {}
        for store_id, cap in self.store_caps.items():
            parent = cap.parent_cdc or store_id  # CDCs are their own parent
            cdc_children.setdefault(parent, []).append(store_id)

        graph: dict[str, list[str]] = {}
        for siblings in cdc_children.values():
            for store in siblings:
                graph[store] = [s for s in siblings if s != store]

        return graph

    def _identify_transfers(self, actions, inventory_states, catalog,
                            store_graph) -> list[dict]:
        """Identify cross-store transfer opportunities.

        A transfer is generated when:
        1. Store A has surplus (on_hand / base_stock > threshold) for a SKU
        2. Store B needs that same SKU (has a pending order)
        3. Store A and Store B are siblings (connected in graph)

        Returns list of {from, to, sku, qty} transfer directives.
        """
        transfers = []

        # Build surplus and deficit maps
        surplus_map: dict[str, dict[str, float]] = {}   # store -> {sku: surplus_qty}
        deficit_map: dict[str, dict[str, float]] = {}   # store -> {sku: needed_qty}

        for store_id, inv_state in inventory_states.items():
            for sku, state in inv_state.items():
                if sku not in catalog:
                    continue
                base_stock = catalog[sku].get("base_stock", 50)
                on_hand = state.get("on_hand", 0)
                ratio = on_hand / max(base_stock, 1)

                if ratio > self.rebalance_threshold:
                    surplus_qty = on_hand - base_stock
                    surplus_map.setdefault(store_id, {})[sku] = surplus_qty

                # A store has a deficit if it placed an order for this SKU
                order_qty = actions.get(store_id, {}).get(sku, 0)
                if order_qty > 0:
                    deficit_map.setdefault(store_id, {})[sku] = order_qty

        # Match surpluses with deficits among siblings
        for deficit_store, deficit_skus in deficit_map.items():
            siblings = store_graph.get(deficit_store, [])

            for sku, needed_qty in deficit_skus.items():
                remaining_need = needed_qty

                for sibling in siblings:
                    if remaining_need <= 0:
                        break

                    available = surplus_map.get(sibling, {}).get(sku, 0)
                    if available <= 0:
                        continue

                    transfer_qty = min(available, remaining_need)
                    transfers.append({
                        "from": sibling,
                        "to": deficit_store,
                        "sku": sku,
                        "qty": transfer_qty,
                        "type": "rebalance",
                    })

                    surplus_map[sibling][sku] -= transfer_qty
                    remaining_need -= transfer_qty

        return transfers

    # ── Supplier Constraints ──────────────────────────────────────

    def _apply_supplier_constraints(self, actions, catalog) -> dict:
        """Cap total orders to supplier daily capacity.

        Groups SKUs by their supplier (inferred from category),
        sums total demand, and scales down if exceeding capacity.
        """
        if not self.supplier_caps:
            return actions

        # Aggregate demand per supplier across all stores
        supplier_demand: dict[str, float] = {}  # supplier_id -> total_qty
        supplier_sku_map: dict[str, list[tuple]] = {}  # supplier_id -> [(store, sku)]

        for store_id, sku_actions in actions.items():
            for sku, qty in sku_actions.items():
                if qty <= 0:
                    continue
                category = catalog.get(sku, {}).get("category", "General")

                # Find supplier for this category
                supplier_id = None
                for sid, sup in self.supplier_caps.items():
                    if category in sup.categories or not sup.categories:
                        supplier_id = sid
                        break

                if supplier_id is None:
                    continue

                supplier_demand[supplier_id] = (
                    supplier_demand.get(supplier_id, 0) + qty
                )
                supplier_sku_map.setdefault(supplier_id, []).append(
                    (store_id, sku)
                )

        # Scale down if over capacity
        for supplier_id, total_demand in supplier_demand.items():
            cap = self.supplier_caps.get(supplier_id)
            if cap is None:
                continue

            available = cap.max_daily_units - cap.current_committed
            if total_demand > available and total_demand > 0:
                scale = available / total_demand
                for store_id, sku in supplier_sku_map.get(supplier_id, []):
                    actions[store_id][sku] = round(
                        actions[store_id][sku] * scale
                    )

        return actions

    # ── Reporting ─────────────────────────────────────────────────

    def get_utilization_report(self, actions: dict) -> dict:
        """Generate a utilization report for monitoring.

        Returns per-store inbound utilization and per-supplier utilization.
        """
        report = {
            "store_utilization": {},
            "supplier_utilization": {},
        }

        for store_id, sku_actions in actions.items():
            total_inbound = sum(sku_actions.values())
            cap = self.store_caps.get(store_id)
            if cap:
                report["store_utilization"][store_id] = {
                    "inbound_units": total_inbound,
                    "max_inbound": cap.max_inbound_units,
                    "utilization_pct": round(
                        total_inbound / max(cap.max_inbound_units, 1) * 100, 1
                    ),
                    "remaining_storage": cap.max_storage_units - cap.current_occupancy,
                }

        return report
