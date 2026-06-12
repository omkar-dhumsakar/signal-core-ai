import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_end_to_end_workflow():
    # 1. Login
    login_resp = client.post("/api/v1/auth/login", json={"username": "manager1", "password": "storeops123"})
    assert login_resp.status_code == 200
    token = login_resp.json()["token"]
    
    # 2. Get Directives
    dir_resp = client.get("/api/v1/directives")
    assert dir_resp.status_code == 200
    data = dir_resp.json()
    assert "directives" in data
    
    if len(data["directives"]) == 0:
        pytest.skip("No directives generated to test with.")
        
    directive = data["directives"][0]
    sku = directive["sku"]
    directive_id = directive["id"]
    
    # 3. Confirm the order
    confirm_resp = client.post("/api/v1/orders/confirm", json={
        "sku": sku,
        "quantity": 10,
        "directive_id": directive_id
    })
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["status"] == "confirmed"
    
    # 4. Generate Purchase Orders
    po_resp = client.post("/api/v1/orders/generate-pos")
    assert po_resp.status_code == 200
    
    # 5. Log Human Feedback (RLHF)
    adjust_resp = client.post("/api/v1/orders/adjust", json={
        "directive_id": directive_id,
        "sku": sku,
        "original_qty": 10,
        "adjusted_qty": 20,
        "reason": "Expected weekend spike"
    })
    assert adjust_resp.status_code == 200
    assert adjust_resp.json()["logged"] is True
