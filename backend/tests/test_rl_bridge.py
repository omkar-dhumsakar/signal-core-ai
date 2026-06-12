import pytest
from backend.rl_bridge import RLBridge
from backend.models import AdjustmentRequest

def test_rl_bridge_initialization():
    bridge = RLBridge()
    assert isinstance(bridge.agents, dict)
    assert len(bridge.inventory_state) >= 0

def test_confirm_order():
    bridge = RLBridge()
    sku = "TEST-123"
    bridge.inventory_state[sku] = {
        "on_hand": 100,
        "pipeline_sum": 0,
        "pipeline_seq": []
    }
    
    initial_sum = bridge.inventory_state[sku].get("pipeline_sum", 0)
    initial_seq_len = len(bridge.inventory_state[sku].get("pipeline_seq", []))
    
    bridge.confirm_order(sku, 50)
    
    assert bridge.inventory_state[sku]["pipeline_sum"] == initial_sum + 50
    assert len(bridge.inventory_state[sku]["pipeline_seq"]) == initial_seq_len + 1
    assert bridge.inventory_state[sku]["pipeline_seq"][-1][0] == 50

def test_log_rlhf_feedback():
    bridge = RLBridge()
    sku = "TEST-123"
    bridge.inventory_state[sku] = {
        "on_hand": 100,
        "pipeline_sum": 0,
        "pipeline_seq": []
    }
    
    initial_sum = bridge.inventory_state[sku].get("pipeline_sum", 0)
    
    adjustment = AdjustmentRequest(
        directive_id="DIR-123",
        sku=sku,
        original_qty=20,
        adjusted_qty=40,
        reason="stockout_risk"
    )
    
    feedback_id = bridge.log_rlhf_feedback(adjustment)
    
    assert feedback_id.startswith("FB-")
    assert bridge.inventory_state[sku]["pipeline_sum"] == initial_sum + 40
    assert len(bridge.feedback_log) > 0
    assert bridge.feedback_log[-1]["delta"] == 20
