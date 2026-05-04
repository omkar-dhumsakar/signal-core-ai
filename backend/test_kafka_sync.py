import sys
import os
import unittest
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from kafka_gateway import KafkaConsumerWrapper, KafkaConfig

class TestKafkaIngestion(unittest.TestCase):
    def setUp(self):
        self.bridge = MagicMock()
        # Mock stores
        self.store = MagicMock()
        self.store.inventory_state = {"PROD-001": {"on_hand": 100}}
        self.bridge.stores = {"DS-CENTRAL": self.store}
        self.bridge.update_inventory = MagicMock()
        
        self.consumer = KafkaConsumerWrapper(self.bridge, mock=True)

    def test_pos_sale_routing(self):
        payload = {
            "items": [{"sku": "PROD-001", "quantity": 10, "store_id": "DS-CENTRAL"}]
        }
        self.consumer._route_message(KafkaConfig.POS_SALES_TOPIC, payload)
        
        # Verify inventory was decremented
        self.assertEqual(self.store.inventory_state["PROD-001"]["on_hand"], 90)
        # Verify cache was cleared
        self.bridge._directive_cache.clear.assert_called_once()

    def test_erp_sync_routing(self):
        payload = {"sku": "PROD-001", "on_hand": 150, "store_id": "DS-CENTRAL"}
        self.consumer._route_message(KafkaConfig.ERP_SYNC_TOPIC, payload)
        
        # Verify bridge.update_inventory was called
        self.bridge.update_inventory.assert_called_with("PROD-001", 150)

if __name__ == "__main__":
    unittest.main()
