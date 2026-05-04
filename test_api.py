"""Full test of all StoreOps API endpoints."""
import urllib.request
import json

BASE = "http://localhost:8000"

def get(path):
    r = urllib.request.urlopen(f"{BASE}{path}")
    return json.loads(r.read())

def post(path, body):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    r = urllib.request.urlopen(req)
    return json.loads(r.read())

SEP = "=" * 70
LINE = "-" * 50

print(SEP)
print("  SIGNAL CORE AI — StoreOps Backend | Full API Test")
print("  Goa Bagayatdaar Inventory Management System")
print(SEP)

# ── 1. Health ─────────────────────────────────────────────
print(f"\n[1] HEALTH CHECK  (GET /health)")
print(LINE)
health = get("/health")
for k, v in health.items():
    print(f"    {k}: {v}")

# ── 2. Monsoon ────────────────────────────────────────────
print(f"\n[2] MONSOON STATUS  (GET /api/v1/monsoon/status)")
print(LINE)
monsoon = get("/api/v1/monsoon/status")
for k, v in monsoon.items():
    print(f"    {k}: {v}")

# ── 3. Product Catalog ────────────────────────────────────
print(f"\n[3] PRODUCT CATALOG  (GET /api/v1/products)")
print(LINE)
products = get("/api/v1/products")
print(f"    Total products: {len(products)}\n")
header = f"    {'SKU':<20} {'Product':<30} {'Category':<15} {'Stock'}"
print(header)
print(f"    {'-'*20} {'-'*30} {'-'*15} {'-'*6}")
for p in products:
    print(f"    {p['sku']:<20} {p['name']:<30} {p['category']:<15} {p['base_stock']}")

# ── 4. Directives Feed ────────────────────────────────────
print(f"\n[4] RL DIRECTIVES FEED  (GET /api/v1/directives)")
print(LINE)
directives = get("/api/v1/directives")
print(f"    Active directives: {len(directives)}\n")

for i, d in enumerate(directives, 1):
    priority_marker = {
        "critical": "!!!",
        "high": "!! ",
        "medium": "!  ",
        "low": "   ",
    }.get(d["priority"], "   ")
    print(f"    [{priority_marker}] Directive #{i}: {d['product_name']}")
    print(f"         ID:             {d['id']}")
    print(f"         SKU:            {d['sku']}")
    print(f"         Priority:       {d['priority'].upper()}")
    print(f"         Reason:         {d['reason']}")
    print(f"         On-Hand Stock:  {d['current_stock']} units")
    print(f"         In Pipeline:    {d['pipeline_stock']} units")
    print(f"         RL State:       inv={d['rl_state']['inventory']}, pipe={d['rl_state']['pipeline']}, signal={d['rl_state']['signal']}")
    print(f"         RL Confidence:  {d['rl_confidence']}")
    print(f"         Recommendation: ORDER {d['recommended_qty']} UNITS")
    print(f"         Est. Arrival:   {d['estimated_arrival']} (3-day lead time)")
    print(f"         Status:         {d['status']}")
    print()

# ── 5. Approve first directive ────────────────────────────
if directives:
    d = directives[0]
    print(f"[5] APPROVE ORDER  (POST /api/v1/orders/confirm)")
    print(LINE)
    print(f"    Approving: {d['product_name']} — {d['recommended_qty']} units")
    result = post("/api/v1/orders/confirm", {
        "sku": d["sku"],
        "quantity": d["recommended_qty"],
        "directive_id": d["id"],
    })
    print(f"\n    RESULT:")
    for k, v in result.items():
        print(f"      {k}: {v}")

# ── 6. Adjust second directive (RLHF) ────────────────────
if len(directives) > 1:
    d = directives[1]
    adjusted_qty = int(d["recommended_qty"] * 1.5)
    print(f"\n[6] ADJUST ORDER + RLHF FEEDBACK  (POST /api/v1/orders/adjust)")
    print(LINE)
    print(f"    Product:      {d['product_name']}")
    print(f"    AI suggested: {d['recommended_qty']} units")
    print(f"    Manager sets: {adjusted_qty} units (+50%)")
    print(f"    Reason:       'Expecting tourist surge this weekend'")
    result = post("/api/v1/orders/adjust", {
        "directive_id": d["id"],
        "sku": d["sku"],
        "original_qty": d["recommended_qty"],
        "adjusted_qty": adjusted_qty,
        "reason": "Expecting tourist surge this weekend",
    })
    print(f"\n    RESULT:")
    for k, v in result.items():
        print(f"      {k}: {v}")

# ── 7. Inventory Audit ────────────────────────────────────
print(f"\n[7] INVENTORY AUDIT  (POST /api/v1/inventory/audit)")
print(LINE)
print(f"    Auditing: GOA-FENI-750 — actual count is 85 units")
result = post("/api/v1/inventory/audit", {
    "sku": "GOA-FENI-750",
    "on_hand_qty": 85,
})
print(f"\n    RESULT:")
for k, v in result.items():
    print(f"      {k}: {v}")

# ── 8. Post-action health ────────────────────────────────
print(f"\n[8] POST-ACTION HEALTH CHECK")
print(LINE)
health = get("/health")
for k, v in health.items():
    print(f"    {k}: {v}")

print(f"\n{SEP}")
print("  All endpoints tested successfully!")
print(SEP)
