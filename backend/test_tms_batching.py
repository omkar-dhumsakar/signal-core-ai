import sys
import os
import uuid

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from rl_bridge import RLBridge
from models import AlertPriority, TMSStatus

def test_tms_batching():
    print("--- TMS Truck Batching Test ---")
    bridge = RLBridge()
    
    sid = "DS-CENTRAL"
    store = bridge.stores[sid]
    
    # 0. Precise state setup to avoid CRITICAL but ensure REPLENISHMENT
    for sku in store.inventory_state:
        store.inventory_state[sku]["signal"] = 0
        store.inventory_state[sku]["on_hand"] = 1000 # Abundant
        store.inventory_state[sku]["oldest_batch_hours"] = 0 # Fresh
        
    print("Setup: Cleared all signals, boosted inventory, and reset shelf life.")
    
    # 1. Generate many directives for a store
    catalog = bridge.get_full_catalog()
    skus = list(catalog.keys())
    test_cluster = skus[:20] 
    for sku in test_cluster:
        # Set inventory to 50% of base (High priority but NOT Critical)
        # _assign_priority: ratio < 0.3 is Critical, ratio < 0.5 is High, ratio < 0.7 is Medium.
        base = catalog[sku]["base_stock"]
        store.inventory_state[sku]["on_hand"] = int(base * 0.4) + 1 # Ratio approx 0.45 -> HIGH
    
    # Clear cache
    bridge._directive_cache.clear()
    
    directives, utilization = bridge.generate_directives(store_id=sid, limit=50)
    
    print(f"Total Directives: {len(directives)}")
    print(f"Initial Truck Utilization: {utilization*100:.2f}%")
    
    # Count statuses
    batching_count = sum(1 for d in directives if d.tms_status == TMSStatus.BATCHING)
    ready_count = sum(1 for d in directives if d.tms_status == TMSStatus.READY)
    
    print(f"Directives BATCHING: {batching_count}")
    print(f"Directives READY: {ready_count}")
    
    if batching_count > 0:
        print("SUCCESS: Low utilization truck is BATCHING.")
    
        # 2. Test Critical Override
        sku_to_override = None
        for d in directives:
            if d.tms_status == TMSStatus.BATCHING:
                sku_to_override = d.sku
                break
        
        if sku_to_override:
            print(f"\nElevating {sku_to_override} to CRITICAL to test override...")
            store.inventory_state[sku_to_override]["signal"] = 1 # Forces CRITICAL via signal
            # Clear cache
            bridge._directive_cache.clear()
            
            new_directives, new_util = bridge.generate_directives(store_id=sid, limit=50)
            new_status = next(nd.tms_status for nd in new_directives if nd.sku == sku_to_override)
            
            print(f"New Status for {sku_to_override}: {new_status}")
            transport_directives = [nd for nd in new_directives if nd.directive_type in ('replenishment', 'purchase')]
            fleet_ready = all(nd.tms_status == TMSStatus.READY for nd in transport_directives)
            print(f"New Fleet Ready Status: {fleet_ready}")
            
            if new_status == TMSStatus.READY and fleet_ready:
                print("SUCCESS: Critical override triggered Ready state for whole fleet.")
            else:
                print(f"FAILURE: Counter-check -> Ready Count: {sum(1 for nd in transport_directives if nd.tms_status == TMSStatus.READY)}")
        else:
            print("Could not find a BATCHING directive to test override.")
    else:
        print("FAILURE: Still no BATCHING state. Check HasCrit in Debug logs.")

if __name__ == "__main__":
    test_tms_batching()
