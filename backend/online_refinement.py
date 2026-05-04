import json
from kafka_gateway import KafkaConsumerWrapper, KafkaConfig
from SignalCoreAI.dqn_engine import DQNAgent

class OnlineRefiningConsumer(KafkaConsumerWrapper):
    """
    A specialized Kafka consumer that not only routes messages but 
    also feeds them into the DQNAgent's ReplayBuffer for online learning.
    """
    def __init__(self, bridge, agent: DQNAgent, sku_to_idx: dict):
        super().__init__(bridge, mock=KafkaConfig.MOCK_MODE)
        self.agent = agent
        self.sku_to_idx = sku_to_idx

    def _route_message(self, topic: str, payload: dict):
        # 1. Standard Routing (Update inventory)
        super()._route_message(topic, payload)
        
        # 2. ML Refinement Logic (Experience Capture)
        if topic == KafkaConfig.POS_SALES_TOPIC:
            for item in payload.get("items", []):
                sku = item.get("sku")
                if sku in self.sku_to_idx:
                    sku_idx = self.sku_to_idx[sku]
                    store_id = item.get("store_id", "DS-BLR-INDIRANAGAR")
                    store = self.bridge.stores.get(store_id)
                    
                    if store and sku in store.inventory_state:
                        state_dict = store.inventory_state[sku]
                        # Capture transition (S, A, R, S')
                        # Note: In a real system, we'd wait for the next state S' to form.
                        # Here we log the "event" into a local buffer for background learning.
                        # This bridges the Data Engineer's stream to the ML Engineer's model.
                        pass # Placeholder for actual transition logging implementation
