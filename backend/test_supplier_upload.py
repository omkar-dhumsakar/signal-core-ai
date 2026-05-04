"""Quick test for the supplier upload endpoint."""
import urllib.request
import json

BASE = "http://localhost:8000"

# ── 1. Upload CSV ──
print("=== Testing POST /api/v1/suppliers/upload ===")
csv_data = open("test_suppliers.csv", "rb").read()

boundary = "----TestBoundary123"
body = (
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="file"; filename="test_suppliers.csv"\r\n'
    f"Content-Type: text/csv\r\n"
    f"\r\n"
).encode() + csv_data + f"\r\n--{boundary}--\r\n".encode()

req = urllib.request.Request(
    f"{BASE}/api/v1/suppliers/upload",
    data=body,
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    method="POST",
)
resp = urllib.request.urlopen(req)
result = json.loads(resp.read())
print(f"  Result: {json.dumps(result, indent=2)}")
assert result["inserted"] == 8, f"Expected 8 inserted, got {result['inserted']}"
assert result["updated"] == 0
assert result["errors"] == []
print("  [OK] Upload successful!\n")

# ── 2. Check products now have supplier_id ──
print("=== Testing GET /api/v1/products (with supplier_id) ===")
resp = urllib.request.urlopen(f"{BASE}/api/v1/products")
products = json.loads(resp.read())
linked = [p for p in products if p.get("supplier_id") is not None]
print(f"  Total products: {len(products)}")
print(f"  Products with supplier_id: {len(linked)}")
for p in products:
    print(f"    {p['sku']:20s} supplier_id={p.get('supplier_id')}")
assert len(linked) == 8, f"Expected 8 linked, got {len(linked)}"
print("  [OK] All products enriched with supplier_id!\n")

# ── 3. Re-upload (should update, not insert) ──
print("=== Testing re-upload (idempotency) ===")
req2 = urllib.request.Request(
    f"{BASE}/api/v1/suppliers/upload",
    data=body,
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    method="POST",
)
resp2 = urllib.request.urlopen(req2)
result2 = json.loads(resp2.read())
print(f"  Result: {json.dumps(result2, indent=2)}")
assert result2["inserted"] == 0, f"Expected 0 inserted on re-upload, got {result2['inserted']}"
assert result2["updated"] == 8, f"Expected 8 updated on re-upload, got {result2['updated']}"
print("  [OK] Re-upload correctly updates existing links!\n")

# ── 4. Existing endpoints still work ──
print("=== Verifying existing endpoints ===")
resp = urllib.request.urlopen(f"{BASE}/health")
health = json.loads(resp.read())
print(f"  Health: {health['status']}")
assert health["status"] == "healthy"

resp = urllib.request.urlopen(f"{BASE}/api/v1/directives")
directives = json.loads(resp.read())
print(f"  Directives: {len(directives)} active")

resp = urllib.request.urlopen(f"{BASE}/api/v1/monsoon/status")
monsoon = json.loads(resp.read())
print(f"  Monsoon: active={monsoon['active']}")
print("  [OK] All existing endpoints working!\n")

print("=" * 50)
print("All tests passed!")
print("=" * 50)
