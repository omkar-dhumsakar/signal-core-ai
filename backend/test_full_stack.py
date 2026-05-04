"""Full-stack test suite for StoreOps backend.

Tests all API endpoints including the upgraded supplier upload with pandas.
"""

import requests
import os
import sys

BASE = "http://localhost:8000"
PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [OK] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} -- {detail}")


def test_health():
    print("\n=== 1. Health Check ===")
    r = requests.get(f"{BASE}/health")
    check("Status 200", r.status_code == 200)
    data = r.json()
    check("Status healthy", data.get("status") == "healthy")
    check("Products tracked", data.get("products_tracked", 0) == 8)


def test_directives():
    print("\n=== 2. Directives ===")
    r = requests.get(f"{BASE}/api/v1/directives")
    check("Status 200", r.status_code == 200)
    data = r.json()
    check("Returns list", isinstance(data, list))
    check("Has directives", len(data) > 0)
    if data:
        d = data[0]
        check("Has sku", "sku" in d)
        check("Has priority", "priority" in d)
        check("Has rl_confidence", "rl_confidence" in d)


def test_monsoon():
    print("\n=== 3. Monsoon Status ===")
    r = requests.get(f"{BASE}/api/v1/monsoon/status")
    check("Status 200", r.status_code == 200)
    data = r.json()
    check("Has active field", "active" in data)
    check("Has severity", "severity" in data)
    check("Has message", "message" in data)


def test_products():
    print("\n=== 4. Products ===")
    r = requests.get(f"{BASE}/api/v1/products")
    check("Status 200", r.status_code == 200)
    data = r.json()
    check("Returns 8 products", len(data) == 8)
    if data:
        check("Product has sku", "sku" in data[0])
        check("Product has category", "category" in data[0])


def test_supplier_csv_upload():
    print("\n=== 5. Supplier Upload (CSV via pandas) ===")
    csv_path = os.path.join(os.path.dirname(__file__), "test_suppliers.csv")
    with open(csv_path, "rb") as f:
        r = requests.post(
            f"{BASE}/api/v1/suppliers/upload",
            files={"file": ("suppliers.csv", f, "text/csv")},
        )
    check("Status 200", r.status_code == 200, f"Got {r.status_code}: {r.text}")
    data = r.json()
    total = data.get("inserted", 0) + data.get("updated", 0)
    check("Processed 8 rows", total == 8, f"Got {total}")
    check("No errors", len(data.get("errors", [])) == 0)
    print(f"    inserted={data.get('inserted')}, updated={data.get('updated')}")


def test_supplier_reupload_idempotent():
    print("\n=== 6. Supplier Re-upload (Idempotent) ===")
    csv_path = os.path.join(os.path.dirname(__file__), "test_suppliers.csv")
    with open(csv_path, "rb") as f:
        r = requests.post(
            f"{BASE}/api/v1/suppliers/upload",
            files={"file": ("suppliers.csv", f, "text/csv")},
        )
    check("Status 200", r.status_code == 200)
    data = r.json()
    check("0 inserted (idempotent)", data.get("inserted") == 0)
    check("8 updated", data.get("updated") == 8)


def test_product_enrichment():
    print("\n=== 7. Product Enrichment ===")
    r = requests.get(f"{BASE}/api/v1/products")
    data = r.json()
    with_supplier = [p for p in data if p.get("supplier_id") is not None]
    check("All 8 products have supplier_id", len(with_supplier) == 8,
          f"Only {len(with_supplier)} have supplier_id")


def test_invalid_file_type():
    print("\n=== 8. Invalid File Type Rejection ===")
    r = requests.post(
        f"{BASE}/api/v1/suppliers/upload",
        files={"file": ("data.txt", b"bad data", "text/plain")},
    )
    check("Status 400 for .txt", r.status_code == 400)


def test_order_confirm():
    print("\n=== 9. Order Confirm ===")
    r = requests.post(
        f"{BASE}/api/v1/orders/confirm",
        json={"sku": "GOA-FENI-750", "quantity": 10, "directive_id": "test-d1"},
    )
    check("Status 200", r.status_code == 200)
    data = r.json()
    check("Has order_id", "order_id" in data)
    check("Has lead_time_days", "lead_time_days" in data)


def test_inventory_audit():
    print("\n=== 10. Inventory Audit ===")
    r = requests.post(
        f"{BASE}/api/v1/inventory/audit",
        json={"sku": "GOA-FENI-750", "on_hand_qty": 42},
    )
    check("Status 200", r.status_code == 200)
    data = r.json()
    check("Has synced field", "synced" in data)


if __name__ == "__main__":
    print("=" * 60)
    print("  StoreOps Full-Stack Test Suite")
    print("=" * 60)

    test_health()
    test_directives()
    test_monsoon()
    test_products()
    test_supplier_csv_upload()
    test_supplier_reupload_idempotent()
    test_product_enrichment()
    test_invalid_file_type()
    test_order_confirm()
    test_inventory_audit()

    print("\n" + "=" * 60)
    print(f"  Results: {PASS} passed, {FAIL} failed")
    print("=" * 60)

    sys.exit(0 if FAIL == 0 else 1)
