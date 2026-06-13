from fastapi.testclient import TestClient
from backend.main import app
from backend.models import LoginRequest

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_login_success():
    req = LoginRequest(username="manager1", password="storeops123")
    response = client.post("/api/v1/auth/login", json=req.model_dump())
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert "manager_id" in data

def test_login_invalid():
    req = LoginRequest(username="manager1", password="wrongpassword")
    response = client.post("/api/v1/auth/login", json=req.model_dump())
    assert response.status_code == 401

def test_get_directives():
    response = client.get("/api/v1/directives")
    assert response.status_code == 200
    data = response.json()
    assert "directives" in data
    if len(data["directives"]) > 0:
        assert "id" in data["directives"][0]
        assert "sku" in data["directives"][0]
        
def test_get_products():
    response = client.get("/api/v1/products")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    
def test_get_stores():
    response = client.get("/api/v1/stores")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_shopify_webhook_invalid_hmac():
    response = client.post(
        "/api/v1/webhooks/shopify/orders-create",
        json={"line_items": [{"sku": "BB-FRESH-101", "quantity": 2}]},
        headers={"X-Shopify-Hmac-Sha256": "invalid_hmac"}
    )
    assert response.status_code == 401

def test_shopify_webhook_valid_hmac():
    import hmac, hashlib, base64, json
    payload = {"line_items": [{"sku": "BB-FRESH-101", "quantity": 2}]}
    body = json.dumps(payload).encode('utf-8')
    digest = hmac.new(b"your_shopify_secret_here", body, hashlib.sha256).digest()
    valid_hmac = base64.b64encode(digest).decode('utf-8')
    
    response = client.post(
        "/api/v1/webhooks/shopify/orders-create",
        content=body,
        headers={"X-Shopify-Hmac-Sha256": valid_hmac, "Content-Type": "application/json"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_woocommerce_webhook_invalid_signature():
    response = client.post(
        "/api/v1/webhooks/woocommerce/order-created",
        json={"line_items": [{"sku": "BB-FRESH-102", "quantity": 1}]},
        headers={"X-WC-Webhook-Signature": "invalid_signature"}
    )
    assert response.status_code == 401

def test_woocommerce_webhook_valid_signature():
    import hmac, hashlib, base64, json
    payload = {"line_items": [{"sku": "BB-FRESH-102", "quantity": 1}]}
    body = json.dumps(payload).encode('utf-8')
    digest = hmac.new(b"your_woocommerce_secret_here", body, hashlib.sha256).digest()
    valid_sig = base64.b64encode(digest).decode('utf-8')
    
    response = client.post(
        "/api/v1/webhooks/woocommerce/order-created",
        content=body,
        headers={"X-WC-Webhook-Signature": valid_sig, "Content-Type": "application/json"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
