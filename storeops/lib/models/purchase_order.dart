class PurchaseOrderItem {
  final String sku;
  final String productName;
  final int quantity;
  final double baseCost;
  final double totalCost;

  PurchaseOrderItem({
    required this.sku,
    required this.productName,
    required this.quantity,
    required this.baseCost,
    required this.totalCost,
  });

  factory PurchaseOrderItem.fromJson(Map<String, dynamic> json) {
    return PurchaseOrderItem(
      sku: json['sku'] ?? '',
      productName: json['product_name'] ?? 'Unknown Item',
      quantity: json['quantity'] ?? 0,
      baseCost: (json['base_cost'] ?? 0.0).toDouble(),
      totalCost: (json['total_cost'] ?? 0.0).toDouble(),
    );
  }
}

class PurchaseOrder {
  final String id;
  final String supplierName;
  final List<PurchaseOrderItem> items;
  final int totalQuantity;
  final double totalValue;
  final int etaDays;

  PurchaseOrder({
    required this.id,
    required this.supplierName,
    required this.items,
    required this.totalQuantity,
    required this.totalValue,
    required this.etaDays,
  });

  factory PurchaseOrder.fromJson(Map<String, dynamic> json) {
    return PurchaseOrder(
      id: json['id'] ?? '',
      supplierName: json['supplier_name'] ?? 'Unknown Supplier',
      items: (json['items'] as List<dynamic>?)
              ?.map((e) => PurchaseOrderItem.fromJson(e))
              .toList() ??
          [],
      totalQuantity: json['total_quantity'] ?? 0,
      totalValue: (json['total_value'] ?? 0.0).toDouble(),
      etaDays: json['eta_days'] ?? 0,
    );
  }
}
