import time
import random
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from kafka_gateway import KafkaProducerWrapper, KafkaConfig

def simulate_bb_traffic():
    print("--- BigBasket SAP/Oracle Simulator ---")
    producer = KafkaProducerWrapper(mock=True) # Using Mock for local demo
    
    skus = ["PROD-G001", "PROD-F002", "PROD-E003", "PROD-D004"] # Example SKUs
    stores = ["DS-NORTH", "DS-SOUTH", "DS-CENTRAL"]
    
    print(f"Starting simulation. Producing to {KafkaConfig.POS_SALES_TOPIC}...")
    
    try:
        while True:
            # 1. Simulate a POS Sale Batch
            batch_id = f"BATCH-{int(time.time())}"
            sales_batch = {
                "batch_id": batch_id,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "items": [
                    {
                        "sku": random.choice(skus),
                        "quantity": random.randint(1, 5),
                        "store_id": random.choice(stores)
                    } for _ in range(random.randint(1, 3))
                ]
            }
            producer.send_event(KafkaConfig.POS_SALES_TOPIC, key=batch_id, payload=sales_batch)
            
            # 2. Occasionally simulate an ERP Sync (Manual adjustment)
            if random.random() > 0.8:
                sync_sku = random.choice(skus)
                sync_payload = {
                    "sku": sync_sku,
                    "on_hand": random.randint(100, 200),
                    "store_id": "DS-CENTRAL",
                    "sync_reason": "Cycle Count Correction"
                }
                producer.send_event(KafkaConfig.ERP_SYNC_TOPIC, key=sync_sku, payload=sync_payload)
            
            time.sleep(2) # Wait 2 seconds between batches
            
    except KeyboardInterrupt:
        print("\nSimulation stopped.")

if __name__ == "__main__":
    simulate_bb_traffic()
