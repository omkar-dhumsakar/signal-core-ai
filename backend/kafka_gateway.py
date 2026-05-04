import json
import threading
import time
import logging
from typing import Dict, Any, List, Callable
from confluent_kafka import Producer, Consumer, KafkaError, KafkaException

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("KafkaGateway")

# ── Kafka Configuration ───────────────────────────────────────────────

class KafkaConfig:
    BOOTSTRAP_SERVERS = "localhost:9092"
    POS_SALES_TOPIC = "bb.pos.sales"
    ERP_SYNC_TOPIC = "bb.erp.inventory"
    CONSUMER_GROUP = "signal-core-ai-engine"
    MOCK_MODE = True # Set to True to simulate Kafka locally without a broker

# ── Kafka Producer Wrapper ───────────────────────────────────────────

class KafkaProducerWrapper:
    def __init__(self, mock=KafkaConfig.MOCK_MODE):
        self.mock = mock
        if not self.mock:
            self.producer = Producer({'bootstrap.servers': KafkaConfig.BOOTSTRAP_SERVERS})
        else:
            logger.info("[Mock] Initializing Mock Kafka Producer")

    def send_event(self, topic: str, key: str, payload: Dict[str, Any]):
        if self.mock:
            logger.info(f"[Mock] Producing to {topic} | Key: {key} | Payload: {payload}")
            return

        try:
            self.producer.produce(
                topic, 
                key=key, 
                value=json.dumps(payload).encode('utf-8'),
                callback=self._delivery_report
            )
            self.producer.flush()
        except KafkaException as e:
            logger.error(f"Failed to produce message: {e}")

    def _delivery_report(self, err, msg):
        if err is not None:
            logger.error(f'Message delivery failed: {err}')
        else:
            logger.info(f'Message delivered to {msg.topic()} [{msg.partition()}]')

# ── Kafka Consumer Wrapper ───────────────────────────────────────────

class KafkaConsumerWrapper:
    def __init__(self, bridge, mock=KafkaConfig.MOCK_MODE):
        self.bridge = bridge # RLBridge instance
        self.mock = mock
        self.running = False
        self.thread = None
        
        if not self.mock:
            self.consumer = Consumer({
                'bootstrap.servers': KafkaConfig.BOOTSTRAP_SERVERS,
                'group.id': KafkaConfig.CONSUMER_GROUP,
                'auto.offset.reset': 'earliest'
            })
            self.topic = KafkaConfig.POS_SALES_TOPIC
        else:
            logger.info("[Mock] Initializing Mock Kafka Consumer")

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._consume_loop, daemon=True)
        self.thread.start()
        logger.info(f"Kafka Consumer started (Mock: {self.mock})")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        if not self.mock:
            self.consumer.close()
        logger.info("Kafka Consumer stopped.")

    def _consume_loop(self):
        if not self.mock:
            self.consumer.subscribe([KafkaConfig.POS_SALES_TOPIC, KafkaConfig.ERP_SYNC_TOPIC])
            
            while self.running:
                msg = self.consumer.poll(1.0)
                if msg is None: continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        logger.error(f"Consumer error: {msg.error()}")
                        break
                
                # Process message
                try:
                    payload = json.loads(msg.value().decode('utf-8'))
                    self._route_message(msg.topic(), payload)
                except Exception as e:
                    logger.error(f"Failed to process message: {e}")
        else:
            # Mock loop: just wait for shutdown
            while self.running:
                time.sleep(1)

    def _route_message(self, topic: str, payload: Dict[str, Any]):
        """Data Engineer Logic: Mapping BigBasket SAP events to Signal Core State."""
        logger.info(f"Routing event from {topic}")
        
        if topic == KafkaConfig.POS_SALES_TOPIC:
            # Scenario: Multiple items in a checkout batch
            items = payload.get("items", [])
            for item in items:
                sku = item.get("sku")
                qty = item.get("quantity", 0)
                store_id = item.get("store_id", "DS-BLR-INDIRANAGAR")
                
                # Update inventory in the bridge
                store = self.bridge.stores.get(store_id)
                if store and sku in store.inventory_state:
                    store.inventory_state[sku]["on_hand"] -= qty
                    logger.info(f"[DataEngine] Ingested Sale: {sku} x{qty} at {store_id}")
            
            # Invalidate directives cache
            self.bridge._directive_cache.clear()

        elif topic == KafkaConfig.ERP_SYNC_TOPIC:
            # Scenario: Manual stock update from SAP/Oracle
            sku = payload.get("sku")
            on_hand = payload.get("on_hand")
            store_id = payload.get("store_id", "DS-BLR-INDIRANAGAR")
            
            self.bridge.update_inventory(sku, on_hand)
            logger.info(f"[DataEngine] ERP Sync: {sku} set to {on_hand} at {store_id}")

    def inject_mock_message(self, topic: str, payload: Dict[str, Any]):
        """For testing without a real broker."""
        if self.mock:
            self._route_message(topic, payload)
