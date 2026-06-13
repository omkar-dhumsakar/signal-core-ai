"""Signal Core AI — StoreOps Backend

FastAPI bridge between the RL Supply Chain Agent and the StoreOps mobile app.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Query, BackgroundTasks, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from datetime import date, timedelta
from typing import List, Optional
import uuid
import threading
import structlog
import hmac
import hashlib
import base64
import os

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logger = structlog.get_logger()

from models import (
    OrderConfirmRequest,
    OrderConfirmResponse,
    AdjustmentRequest,
    AdjustmentResponse,
    InventoryAuditRequest,
    InventoryAuditResponse,
    MonsoonStatus,
    Product,
    SupplierUploadResponse,
    LoginRequest,
    LoginResponse,
    GoogleLoginRequest,
    ManagerInfo,
    BudgetConfig,
    DirectivesResponse,
    DarkStore,
    BannedCheckResponse,
    ShelfLifeStatus,
    PurchaseOrder,
    POSSaleBatch,
    InboundQCPayload,
    ForwardDemandPayload,
)
from rl_bridge import RLBridge, PRODUCT_CATALOG
from data_utils import (
    init_db,
    parse_supplier_dataframe,
    upsert_suppliers,
    get_all_supplier_links,
    authenticate_manager,
    get_manager_by_id,
    generate_pos_from_confirmed,
)
from kafka_gateway import KafkaConsumerWrapper

app = FastAPI(
    title="Signal Core AI — BigBasket Q-Commerce Engine",
    version="2.0.0",
    description="Agentic RL Supply Chain Engine powering BigBasket's dark store network in Bengaluru. "
                "Supports BB Now (10-min), BB Daily (subscription), and BB Slotted (same-day) fulfillment.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

bridge = RLBridge()
kafka_consumer = KafkaConsumerWrapper(bridge)
init_db()

@app.on_event("startup")
def startup_event():
    # Load agents from cache or train them in the background
    t = threading.Thread(target=bridge.load_or_train_agents, daemon=True)
    t.start()
    
    # Start Kafka Consumer
    kafka_consumer.start()

@app.on_event("shutdown")
def shutdown_event():
    kafka_consumer.stop()

# In-memory token store: token → manager_id
_active_sessions: dict[str, int] = {}


# ── Authentication Endpoints ──────────────────────────────────────


@app.post("/api/v1/auth/login", response_model=LoginResponse)
def login(req: LoginRequest):
    """Authenticate a store manager and return a session token."""
    manager = authenticate_manager(req.username, req.password)
    if manager is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = uuid.uuid4().hex
    _active_sessions[token] = manager["manager_id"]

    return LoginResponse(
        success=True,
        token=token,
        manager_id=manager["manager_id"],
        full_name=manager["full_name"],
        store_name=manager["store_name"],
        message="Login successful",
    )



@app.post("/api/v1/auth/google", response_model=LoginResponse)
def google_login(req: GoogleLoginRequest):
    """Authenticate a store manager via Google Sign-In."""
    from data_utils import authenticate_google_user
    manager = authenticate_google_user(req.email, req.name)
    if manager is None:
        raise HTTPException(status_code=401, detail="Google authentication failed")

    token = uuid.uuid4().hex
    _active_sessions[token] = manager["manager_id"]

    return LoginResponse(
        success=True,
        manager_id=manager["manager_id"],
        full_name=manager["full_name"],
        store_name=manager["store_name"],
        token=token,
        message="Google Login successful",
    )


@app.get("/api/v1/auth/me", response_model=ManagerInfo)
def get_current_user(authorization: str = Query(..., alias="token")):
    """Validate a session token and return the current manager's info."""
    manager_id = _active_sessions.get(authorization)
    if manager_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    manager = get_manager_by_id(manager_id)
    if manager is None:
        raise HTTPException(status_code=401, detail="Manager not found")

    return ManagerInfo(**manager)


@app.post("/api/v1/auth/logout")
def logout(authorization: str = Query(..., alias="token")):
    """Invalidate a session token."""
    removed = _active_sessions.pop(authorization, None)
    return {"success": removed is not None, "message": "Logged out"}

@app.get("/api/v1/directives", response_model=DirectivesResponse)
async def get_directives(
    category: str | None = Query(None, description="Filter by product category"),
    store_id: str | None = Query(None, description="Dark store ID")
):
    """Fetch RL-generated inventory directives."""
    raw, utilization = bridge.generate_directives(category_filter=category, store_id=store_id)
    directives, summary = bridge.apply_budget_constraint(raw)
    
    return DirectivesResponse(
        directives=directives,
        budget_summary=summary,
        store_id=store_id or "DS-BLR-INDIRANAGAR",
    )

@app.post("/api/v1/admin/retrain")
def retrain_agents(background_tasks: BackgroundTasks):
    """Force Retrain the RL models in the background."""
    if bridge.is_training:
        return {"status": "currently_training"}
    background_tasks.add_task(bridge.load_or_train_agents, force=True)
    return {"status": "training_started_background"}


@app.post("/api/v1/orders/generate-pos", response_model=List[PurchaseOrder])
def generate_purchase_orders(
    store_id: Optional[str] = Query(None, description="Dark store ID"),
):
    """Aggregate confirmed directives into Purchase Orders grouped by Supplier."""
    sid = store_id or "DS-BLR-INDIRANAGAR"
    store = bridge.stores.get(sid)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    confirmed = store.confirmed_orders
    if not confirmed:
        return []

    # Get the catalog for pricing and names
    catalog = bridge.get_full_catalog()

    pos_data = generate_pos_from_confirmed(confirmed, catalog)
    
    # Clear the confirmed orders queue
    store.confirmed_orders = []

    return [PurchaseOrder(**po) for po in pos_data]


def _process_pos_batch(batch: POSSaleBatch):
    total_items = 0
    updated_stores = set()
    for item in batch.items:
        store = bridge.stores.get(item.store_id)
        if not store:
            continue
            
        if item.sku in store.inventory_state:
            store.inventory_state[item.sku]["on_hand"] -= item.quantity
            total_items += item.quantity
            updated_stores.add(item.store_id)
        else:
            store.inventory_state[item.sku] = {
                "on_hand": -item.quantity,
                "pipeline": 0,
                "shelf_life_hours": 72,
                "oldest_batch_age_hours": 0
            }
            total_items += item.quantity
            updated_stores.add(item.store_id)

    if updated_stores:
        bridge._directive_cache.clear()

@app.post("/api/v1/webhooks/pos-sale")
def handle_pos_sale(batch: POSSaleBatch, background_tasks: BackgroundTasks):
    """
    EDA Mock: Instantly drop the checkout payload into the async queue 
    and return 200 OK without blocking BigBasket's POS systems.
    """
    background_tasks.add_task(_process_pos_batch, batch)
    return {"status": "queued", "event": "pos-sale"}

def _process_inbound_qc(payload: InboundQCPayload):
    store = bridge.stores.get(payload.store_id)
    if not store or payload.sku not in store.inventory_state:
        return
    state = store.inventory_state[payload.sku]
    
    state["on_hand"] += payload.accepted_qty
    state["pipeline"] = max(0, state["pipeline"] - payload.received_qty)

    if payload.rejected_qty > 0:
        bridge._directive_cache.clear()

@app.post("/api/v1/inventory/inbound-qc")
def handle_inbound_qc(payload: InboundQCPayload, background_tasks: BackgroundTasks):
    """
    EDA Mock: Accept QC payload to background queue instantly.
    """
    background_tasks.add_task(_process_inbound_qc, payload)
    return {"status": "queued", "event": "inbound-qc"}

def _process_forward_demand(payload: ForwardDemandPayload):
    store = bridge.stores.get(payload.store_id)
    if not store or payload.sku not in store.inventory_state:
        return
    state = store.inventory_state[payload.sku]
    state["forward_booked"] = state.get("forward_booked", 0) + payload.reserved_qty
    bridge._directive_cache.clear()

@app.post("/api/v1/webhooks/forward-demand")
def handle_forward_demand(payload: ForwardDemandPayload, background_tasks: BackgroundTasks):
    """
    EDA Mock: Process forecasted demand slots asynchronously to avoid blocking.
    """
    background_tasks.add_task(_process_forward_demand, payload)
    return {"status": "queued", "event": "forward-demand"}

# ── E-Commerce Webhooks (Shopify / WooCommerce) ───────────────────────

SHOPIFY_SECRET = os.getenv("SHOPIFY_WEBHOOK_SECRET", "your_shopify_secret_here")
WOOCOMMERCE_SECRET = os.getenv("WOOCOMMERCE_WEBHOOK_SECRET", "your_woocommerce_secret_here")

async def verify_shopify_webhook(request: Request, x_shopify_hmac_sha256: str = Header(None)):
    if not x_shopify_hmac_sha256:
        raise HTTPException(status_code=401, detail="Missing HMAC signature")
    body = await request.body()
    digest = hmac.new(SHOPIFY_SECRET.encode('utf-8'), body, hashlib.sha256).digest()
    computed_hmac = base64.b64encode(digest).decode('utf-8')
    if not hmac.compare_digest(computed_hmac, x_shopify_hmac_sha256):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")
    return True

@app.post("/api/v1/webhooks/shopify/orders-create")
async def shopify_orders_create(request: Request, background_tasks: BackgroundTasks, x_shopify_hmac_sha256: str = Header(None)):
    """Ingest a Shopify orders/create webhook."""
    await verify_shopify_webhook(request, x_shopify_hmac_sha256)
    payload = await request.json()
    
    # Extract line items
    items = []
    store_id = "DS-BLR-INDIRANAGAR" # Default store, can be mapped from Shopify location
    
    for line_item in payload.get("line_items", []):
        sku = line_item.get("sku")
        qty = line_item.get("quantity", 0)
        if sku and qty > 0:
            # Option A: Silently ignore unknown SKUs (handled naturally by _process_pos_batch skipping them)
            items.append({"sku": sku, "quantity": qty, "store_id": store_id})
            
    if items:
        batch = POSSaleBatch(items=items)
        background_tasks.add_task(_process_pos_batch, batch)
        
    return {"status": "success"}

async def verify_woocommerce_webhook(request: Request, x_wc_webhook_signature: str = Header(None)):
    if not x_wc_webhook_signature:
        raise HTTPException(status_code=401, detail="Missing WC Signature")
    body = await request.body()
    digest = hmac.new(WOOCOMMERCE_SECRET.encode('utf-8'), body, hashlib.sha256).digest()
    computed_signature = base64.b64encode(digest).decode('utf-8')
    if not hmac.compare_digest(computed_signature, x_wc_webhook_signature):
        raise HTTPException(status_code=401, detail="Invalid WC Signature")
    return True

@app.post("/api/v1/webhooks/woocommerce/order-created")
async def woocommerce_order_created(request: Request, background_tasks: BackgroundTasks, x_wc_webhook_signature: str = Header(None)):
    """Ingest a WooCommerce order created webhook."""
    await verify_woocommerce_webhook(request, x_wc_webhook_signature)
    payload = await request.json()
    
    items = []
    store_id = "DS-BLR-INDIRANAGAR"
    
    for line_item in payload.get("line_items", []):
        sku = line_item.get("sku")
        qty = line_item.get("quantity", 0)
        if sku and qty > 0:
            items.append({"sku": sku, "quantity": qty, "store_id": store_id})
            
    if items:
        batch = POSSaleBatch(items=items)
        background_tasks.add_task(_process_pos_batch, batch)
        
    return {"status": "success"}

@app.get("/api/v1/categories")
def get_categories():
    """Return all available product categories for filter chips."""
    return bridge.get_all_categories()


@app.post("/api/v1/orders/confirm", response_model=OrderConfirmResponse)
def confirm_order(req: OrderConfirmRequest):
    """Confirm an RL-recommended order. Adds to pipeline and returns ETA."""
    if req.sku not in bridge.get_full_catalog():
        raise HTTPException(status_code=404, detail=f"SKU {req.sku} not found")

    lead_time = bridge.get_effective_lead_time()
    arrival = date.today() + timedelta(days=lead_time)
    bridge.confirm_order(req.sku, req.quantity)

    return OrderConfirmResponse(
        order_id=f"ORD-{uuid.uuid4().hex[:8].upper()}",
        sku=req.sku,
        quantity=req.quantity,
        estimated_arrival=arrival,
        status="confirmed",
        lead_time_days=lead_time,
    )


@app.post("/api/v1/orders/adjust", response_model=AdjustmentResponse)
def adjust_order(req: AdjustmentRequest):
    """Log a human adjustment for RLHF training feedback."""
    if req.sku not in bridge.get_full_catalog():
        raise HTTPException(status_code=404, detail=f"SKU {req.sku} not found")

    feedback_id = bridge.log_rlhf_feedback(req)
    return AdjustmentResponse(
        directive_id=req.directive_id,
        logged=True,
        feedback_id=feedback_id,
        message="Adjustment logged for RLHF training",
    )


@app.post("/api/v1/inventory/audit", response_model=InventoryAuditResponse)
def audit_inventory(req: InventoryAuditRequest):
    """Manual inventory audit — syncs the RL agent's state with real on-hand counts."""
    if req.sku not in bridge.get_full_catalog():
        raise HTTPException(status_code=404, detail=f"SKU {req.sku} not found")

    return bridge.update_inventory(req.sku, req.on_hand_qty)


@app.get("/api/v1/monsoon/status", response_model=MonsoonStatus)
def get_monsoon_status():
    """Check current monsoon status and logistics impact."""
    return bridge.get_monsoon_status()


@app.post("/api/v1/suppliers/upload", response_model=SupplierUploadResponse)
async def upload_suppliers(file: UploadFile = File(...)):
    """Upload a CSV or XLSX file of supplier data to link SKUs to suppliers.

    Uses pandas to detect format by file extension:
      - .csv  → pd.read_csv()
      - .xlsx → pd.read_excel()
    Expected columns: sku, supplier_name, lead_time.
    """
    filename = (file.filename or "").lower()
    if not filename.endswith((".csv", ".xlsx")):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Expected .csv or .xlsx, got '{filename}'.",
        )

    raw = await file.read()
    try:
        rows = parse_supplier_dataframe(raw, filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    result = upsert_suppliers(rows)
    return SupplierUploadResponse(**result)


@app.get("/api/v1/products", response_model=list[Product])
def list_products():
    """List all products with metadata, enriched with supplier links."""
    supplier_map = get_all_supplier_links()
    products = []
    for sku, info in PRODUCT_CATALOG.items():
        supplier = supplier_map.get(sku)
        products.append(
            Product(
                sku=sku,
                name=info["name"],
                category=info["category"],
                base_stock=info["base_stock"],
                supplier_id=supplier["supplier_id"] if supplier else None,
            )
        )
    return products


@app.get("/health")
def health():
    from rl_bridge import USE_DQN, DARK_STORE_MODE
    return {
        "status": "healthy",
        "dark_store_mode": DARK_STORE_MODE,
        "agent_type": "DQN" if USE_DQN else "Q-Learning",
        "stores": len(bridge.stores),
        "cluster_agents": {
            cluster: "DQNAgent" if USE_DQN else len(agent.q)
            for cluster, agent in bridge.agents.items()
        },
        "clusters_count": len(bridge.agents),
        "total_parameters": sum(
            sum(p.numel() for p in a.policy_net.parameters())
            for a in bridge.agents.values()
            if hasattr(a, "policy_net")
        ) if USE_DQN else sum(len(a.q) for a in bridge.agents.values()),
        "products_tracked": len(bridge.get_full_catalog()),
        "pending_feedback": len(bridge.feedback_log),
        "daily_budget": bridge.daily_budget,
    }


@app.get("/api/v1/budget", response_model=BudgetConfig)
def get_budget():
    """Return the current daily ordering budget."""
    return BudgetConfig(daily_budget=bridge.daily_budget)


@app.put("/api/v1/budget", response_model=BudgetConfig)
def update_budget(config: BudgetConfig):
    """Update the daily ordering budget."""
    bridge.daily_budget = config.daily_budget
    return config


# ── Dark Store Endpoints ──────────────────────────────────────────────

@app.get("/api/v1/stores", response_model=list[DarkStore])
def list_stores():
    """List all dark stores."""
    return bridge.get_all_stores()


@app.post("/api/v1/stores", response_model=DarkStore)
def create_store(store: DarkStore):
    """Create a new dark store."""
    try:
        return bridge.add_store(
            store_id=store.store_id, name=store.name,
            location=store.location, zone=store.zone
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


# ── Shelf Life Endpoints ──────────────────────────────────────────────

@app.get("/api/v1/shelf-life", response_model=list[ShelfLifeStatus])
def get_shelf_life(
    store_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(50, description="Max items to return"),
):
    """Return shelf life status for SKUs, sorted by urgency (most expiring first)."""
    return bridge.get_shelf_life_status(
        store_id=store_id, category_filter=category
    )[:limit]


# ── Banned Ingredients Endpoints ──────────────────────────────────────

@app.post("/api/v1/ingredients/check", response_model=BannedCheckResponse)
def check_product_ingredients(product_name: str, ingredients: list[str]):
    """Check if a product's ingredients pass First Club's clean policy."""
    from ingredients import check_ingredients as _check
    banned = _check(ingredients)
    return BannedCheckResponse(
        product_name=product_name,
        is_clean=len(banned) == 0,
        banned_found=banned,
    )


@app.get("/api/v1/ingredients/banned")
def get_banned_list():
    """Return the full list of banned ingredients."""
    from ingredients import get_banned_list as _get
    return {"banned_ingredients": _get(), "count": len(_get())}


if __name__ == "__main__":
    import uvicorn

    import sys
    port = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == "--port" else 8002
    uvicorn.run(app, host="0.0.0.0", port=port)
