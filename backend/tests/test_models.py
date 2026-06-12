import pytest
from datetime import datetime
from backend.models import Directive, PurchaseOrder, InventoryAuditResponse

def test_directive_model():
    d = Directive(
        id="DIR-123",
        sku="TEST-123",
        product_name="Test Product",
        current_stock=10,
        pipeline_stock=0,
        reason="Stockout risk",
        priority="high",
        recommended_qty=50,
        action="order",
        quantity=50,
        estimated_cost=100.5,
        rl_confidence=0.95,
        budget_status="pending",
        lead_time_hours=48
    )
    assert d.sku == "TEST-123"
    assert d.recommended_qty == 50
    assert d.estimated_cost == 100.5
    
    # Test dictionary export
    d_dict = d.model_dump()
    assert d_dict["rl_confidence"] == 0.95
    assert d_dict["budget_status"] == "pending"

def test_purchase_order_model():
    po = PurchaseOrder(
        id="PO-999",
        supplier_name="Supplier 1",
        items=[{
            "sku": "SKU-1", 
            "product_name": "Prod 1", 
            "quantity": 10, 
            "base_cost": 5.0, 
            "total_cost": 50.0
        }],
        total_quantity=10,
        total_value=50.0,
        eta_days=2
    )
    assert po.id == "PO-999"
    assert po.total_value == 50.0
