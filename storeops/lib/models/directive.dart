class Directive {
  final String id;
  final String sku;
  final String productName;
  final int currentStock;
  final int pipelineStock;
  final String reason;
  final String priority;
  final int recommendedQty;
  String status;
  final String? estimatedArrival;
  final String createdAt;
  final Map<String, dynamic> rlState;
  final double rlConfidence;

  int? confirmedQty;
  String? adjustmentReason;
  String? orderId;
  int? leadTimeDays;
  final double estimatedCost;
  final String budgetStatus;
  final String storeId;
  final String directiveType;
  final String? transferSource;
  final String? expiryRisk;
  final int? oldestBatchHours;
  final String fulfillmentChannel;

  Directive({
    required this.id,
    required this.sku,
    required this.productName,
    required this.currentStock,
    required this.pipelineStock,
    required this.reason,
    required this.priority,
    required this.recommendedQty,
    required this.status,
    this.estimatedArrival,
    required this.createdAt,
    required this.rlState,
    required this.rlConfidence,
    this.confirmedQty,
    this.adjustmentReason,
    this.orderId,
    this.leadTimeDays,
    this.estimatedCost = 0.0,
    this.budgetStatus = 'funded',
    this.storeId = 'DS-BLR-INDIRANAGAR',
    this.directiveType = 'purchase',
    this.transferSource,
    this.expiryRisk,
    this.oldestBatchHours,
    this.fulfillmentChannel = 'bb_now',
  });

  factory Directive.fromJson(Map<String, dynamic> json) {
    return Directive(
      id: json['id'] ?? '',
      sku: json['sku'] ?? '',
      productName: json['product_name'] ?? '',
      currentStock: json['current_stock'] ?? 0,
      pipelineStock: json['pipeline_stock'] ?? 0,
      reason: json['reason'] ?? '',
      priority: json['priority'] ?? 'low',
      recommendedQty: json['recommended_qty'] ?? 0,
      status: json['status'] ?? 'pending',
      estimatedArrival: json['estimated_arrival'],
      createdAt: json['created_at'] ?? DateTime.now().toIso8601String(),
      rlState: Map<String, dynamic>.from(json['rl_state'] ?? {}),
      rlConfidence: (json['rl_confidence'] ?? 0.5).toDouble(),
      estimatedCost: (json['estimated_cost'] ?? 0.0).toDouble(),
      budgetStatus: json['budget_status'] ?? 'funded',
      storeId: json['store_id'] ?? 'DS-BLR-INDIRANAGAR',
      directiveType: json['directive_type'] ?? 'purchase',
      transferSource: json['transfer_source'],
      expiryRisk: json['expiry_risk'],
      oldestBatchHours: json['oldest_batch_hours'],
      fulfillmentChannel: json['fulfillment_channel'] ?? 'bb_now',
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'sku': sku,
        'product_name': productName,
        'current_stock': currentStock,
        'pipeline_stock': pipelineStock,
        'reason': reason,
        'priority': priority,
        'recommended_qty': recommendedQty,
        'status': status,
        'estimated_arrival': estimatedArrival,
        'created_at': createdAt,
        'rl_state': rlState,
        'rl_confidence': rlConfidence,
        'estimated_cost': estimatedCost,
        'budget_status': budgetStatus,
        'directive_type': directiveType,
        'transfer_source': transferSource,
        'expiry_risk': expiryRisk,
        'oldest_batch_hours': oldestBatchHours,
        'fulfillment_channel': fulfillmentChannel,
      };

  Map<String, dynamic> toDbMap() => {
        'id': id,
        'sku': sku,
        'product_name': productName,
        'current_stock': currentStock,
        'pipeline_stock': pipelineStock,
        'reason': reason,
        'priority': priority,
        'recommended_qty': recommendedQty,
        'status': status,
        'estimated_arrival': estimatedArrival,
        'created_at': createdAt,
        'rl_confidence': rlConfidence,
        'confirmed_qty': confirmedQty,
        'order_id': orderId,
        'lead_time_days': leadTimeDays,
      };

  factory Directive.fromDbMap(Map<String, dynamic> map) {
    return Directive(
      id: map['id'],
      sku: map['sku'],
      productName: map['product_name'],
      currentStock: map['current_stock'],
      pipelineStock: map['pipeline_stock'],
      reason: map['reason'],
      priority: map['priority'],
      recommendedQty: map['recommended_qty'],
      status: map['status'],
      estimatedArrival: map['estimated_arrival'],
      createdAt: map['created_at'],
      rlState: {},
      rlConfidence: (map['rl_confidence'] ?? 0.5).toDouble(),
      confirmedQty: map['confirmed_qty'],
      orderId: map['order_id'],
      leadTimeDays: map['lead_time_days'],
      expiryRisk: map['expiry_risk'],
      oldestBatchHours: map['oldest_batch_hours'],
    );
  }
}

class MonsoonStatus {
  final bool active;
  final String severity;
  final int additionalDelayDays;
  final String message;

  MonsoonStatus({
    required this.active,
    required this.severity,
    required this.additionalDelayDays,
    required this.message,
  });

  factory MonsoonStatus.fromJson(Map<String, dynamic> json) {
    return MonsoonStatus(
      active: json['active'] ?? false,
      severity: json['severity'] ?? 'none',
      additionalDelayDays: json['additional_delay_days'] ?? 0,
      message: json['message'] ?? '',
    );
  }
}

class BudgetSummary {
  final double dailyBudget;
  final double totalAllocated;
  final double remaining;
  final int fundedCount;
  final int deferredCount;

  BudgetSummary({
    required this.dailyBudget,
    required this.totalAllocated,
    required this.remaining,
    required this.fundedCount,
    required this.deferredCount,
  });

  factory BudgetSummary.fromJson(Map<String, dynamic> json) {
    return BudgetSummary(
      dailyBudget: (json['daily_budget'] ?? 0).toDouble(),
      totalAllocated: (json['total_allocated'] ?? 0).toDouble(),
      remaining: (json['remaining'] ?? 0).toDouble(),
      fundedCount: json['funded_count'] ?? 0,
      deferredCount: json['deferred_count'] ?? 0,
    );
  }
}

class InventoryItem {
  final String sku;
  final String name;
  final String category;
  int onHandQty;
  final int baseStock;

  InventoryItem({
    required this.sku,
    required this.name,
    required this.category,
    required this.onHandQty,
    required this.baseStock,
  });

  factory InventoryItem.fromJson(Map<String, dynamic> json) {
    return InventoryItem(
      sku: json['sku'] ?? '',
      name: json['name'] ?? '',
      category: json['category'] ?? '',
      onHandQty: json['base_stock'] ?? 0,
      baseStock: json['base_stock'] ?? 0,
    );
  }
}


class Store {
  final String storeId;
  final String name;
  final String location;
  final String zone;

  Store({
    required this.storeId,
    required this.name,
    required this.location,
    required this.zone,
  });

  factory Store.fromJson(Map<String, dynamic> json) {
    return Store(
      storeId: json['store_id'] ?? '',
      name: json['name'] ?? '',
      location: json['location'] ?? '',
      zone: json['zone'] ?? '',
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Store && storeId == other.storeId;

  @override
  int get hashCode => storeId.hashCode;
}
