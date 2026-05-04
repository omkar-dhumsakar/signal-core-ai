from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime, date
from enum import Enum


class DirectiveStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    ADJUSTED = "adjusted"
    DISMISSED = "dismissed"


class AlertPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Directive(BaseModel):
    id: str
    sku: str
    product_name: str
    current_stock: int
    pipeline_stock: int
    reason: str
    priority: AlertPriority
    recommended_qty: int
    status: DirectiveStatus = DirectiveStatus.PENDING
    estimated_arrival: Optional[date] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    rl_state: Dict[str, int] = {}
    rl_confidence: float = 0.5
    estimated_cost: float = 0.0
    budget_status: str = "funded"  # "funded" or "deferred"
    # Dark store / shelf life fields
    store_id: str = "DS-BLR-INDIRANAGAR"
    lead_time_hours: Optional[int] = None
    shelf_life_hours: Optional[int] = None
    expiry_risk: Optional[str] = None  # "green", "yellow", "red"
    oldest_batch_hours: Optional[int] = None
    directive_type: str = "purchase"  # "purchase" or "transfer"
    transfer_source: Optional[str] = None  # Store ID if transfer
    fulfillment_channel: str = "bb_now"  # "bb_now", "bb_daily", "bb_slotted"

class POSSaleItem(BaseModel):
    sku: str
    quantity: int
    store_id: str
    
class POSSaleBatch(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    items: List[POSSaleItem]
class OrderConfirmRequest(BaseModel):
    sku: str
    quantity: int
    directive_id: str


class OrderConfirmResponse(BaseModel):
    order_id: str
    sku: str
    quantity: int
    estimated_arrival: date
    status: str = "confirmed"
    lead_time_days: int


class AdjustmentRequest(BaseModel):
    directive_id: str
    sku: str
    original_qty: int
    adjusted_qty: int
    reason: Optional[str] = None


class AdjustmentResponse(BaseModel):
    directive_id: str
    logged: bool
    feedback_id: str
    message: str


class InventoryAuditRequest(BaseModel):
    sku: str
    on_hand_qty: int
    audited_by: Optional[str] = None


class InventoryAuditResponse(BaseModel):
    sku: str
    previous_qty: int
    new_qty: int
    synced: bool
    state_updated: bool


class MonsoonStatus(BaseModel):
    active: bool
    severity: str
    additional_delay_days: int
    message: str


class Product(BaseModel):
    sku: str
    name: str
    category: str
    base_stock: int
    supplier_id: Optional[int] = None
    ingredients: Optional[List[str]] = None
    is_clean: bool = True
    shelf_life_hours: Optional[int] = None


class SupplierUploadResponse(BaseModel):
    inserted: int
    updated: int
    errors: List[str] = []


# ── Authentication Models ──────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class GoogleLoginRequest(BaseModel):
    email: str
    name: str


class LoginResponse(BaseModel):
    success: bool
    manager_id: Optional[int] = None
    full_name: Optional[str] = None
    store_name: Optional[str] = None
    token: Optional[str] = None
    message: str


class ManagerInfo(BaseModel):
    manager_id: int
    username: str
    full_name: str
    store_name: str
    role: str


class BudgetSummary(BaseModel):
    daily_budget: float
    total_allocated: float
    remaining: float
    funded_count: int
    deferred_count: int


class BudgetConfig(BaseModel):
    daily_budget: float


class DirectivesResponse(BaseModel):
    directives: List[Directive] = []
    budget_summary: BudgetSummary
    store_id: str = "DS-BLR-INDIRANAGAR"


class DarkStore(BaseModel):
    store_id: str
    name: str
    location: str
    zone: str
    facility_type: str = "hub"  # "cdc" or "hub"
    parent_cdc: Optional[str] = None

class InboundQCPayload(BaseModel):
    sku: str
    store_id: str
    received_qty: int
    accepted_qty: int
    rejected_qty: int

class ForwardDemandPayload(BaseModel):
    sku: str
    store_id: str
    reserved_qty: int
    delivery_date: date


class BannedCheckResponse(BaseModel):
    product_name: str
    is_clean: bool
    banned_found: List[str] = []


class ShelfLifeStatus(BaseModel):
    sku: str
    product_name: str
    category: str = "General"
    on_hand: int = 0
    shelf_life_hours: int
    oldest_batch_hours: int
    remaining_hours: int = 0
    expiry_risk: str
    spoilage_rate_hourly: float = 0.0
    estimated_waste_cost: float = 0.0


class PurchaseOrderItem(BaseModel):
    sku: str
    product_name: str
    quantity: int
    base_cost: float
    total_cost: float


class PurchaseOrder(BaseModel):
    id: str
    supplier_name: str
    items: List[PurchaseOrderItem]
    total_quantity: int
    total_value: float
    eta_days: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
