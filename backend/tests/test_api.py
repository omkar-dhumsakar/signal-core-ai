import pytest
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
