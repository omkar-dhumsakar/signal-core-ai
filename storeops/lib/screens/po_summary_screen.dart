import 'package:flutter/material.dart';
import '../models/purchase_order.dart';
import 'package:flutter/services.dart';

class POSummaryScreen extends StatelessWidget {
  final List<PurchaseOrder> purchaseOrders;

  const POSummaryScreen({super.key, required this.purchaseOrders});

  void _copyToClipboard(BuildContext context) {
    if (purchaseOrders.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No Purchase Orders to copy.')),
      );
      return;
    }

    final StringBuffer sb = StringBuffer();
    sb.writeln('=== DAILY PURCHASE ORDERS ===\n');

    for (var po in purchaseOrders) {
      sb.writeln('PO ID: ${po.id}');
      sb.writeln('Supplier: ${po.supplierName}');
      sb.writeln('ETA (Days): ${po.etaDays}');
      sb.writeln('Total Items: ${po.totalQuantity}');
      sb.writeln('Total Value: ₹${po.totalValue.toStringAsFixed(2)}\n');
      
      sb.writeln('Items:');
      for (var item in po.items) {
        sb.writeln(' - ${item.quantity}x ${item.productName} (₹${item.baseCost.toStringAsFixed(2)}/ea) = ₹${item.totalCost.toStringAsFixed(2)}');
      }
      sb.writeln('\n---------------------------\n');
    }

    Clipboard.setData(ClipboardData(text: sb.toString()));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Purchase Orders copied to clipboard!')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Generated POs'),
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.copy),
            tooltip: 'Copy Text Summary',
            onPressed: () => _copyToClipboard(context),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: purchaseOrders.isEmpty
          ? Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.inventory_2_outlined, size: 64, color: cs.onSurface.withValues(alpha: 0.3)),
                  const SizedBox(height: 16),
                  Text(
                    'No orders to generate.',
                    style: TextStyle(fontSize: 16, color: cs.onSurface.withValues(alpha: 0.7)),
                  ),
                ],
              ),
            )
          : ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: purchaseOrders.length,
              itemBuilder: (context, index) {
                final po = purchaseOrders[index];
                return Card(
                  margin: const EdgeInsets.only(bottom: 16),
                  elevation: 2,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Expanded(
                              child: Text(
                                po.supplierName,
                                style: const TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                              decoration: BoxDecoration(
                                color: cs.primaryContainer,
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Text(
                                po.id,
                                style: TextStyle(
                                  fontSize: 12,
                                  color: cs.onPrimaryContainer,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            _buildStatBadge(context, Icons.inventory_2, '${po.totalQuantity} items'),
                            _buildStatBadge(context, Icons.currency_rupee, po.totalValue.toStringAsFixed(2)),
                            _buildStatBadge(context, Icons.local_shipping, 'ETA: ${po.etaDays}d'),
                          ],
                        ),
                        const Divider(height: 32),
                        const Text(
                          'Order Items',
                          style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
                        ),
                        const SizedBox(height: 8),
                        ...po.items.map((item) => Padding(
                          padding: const EdgeInsets.symmetric(vertical: 4),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Container(
                                width: 24,
                                height: 24,
                                alignment: Alignment.center,
                                decoration: BoxDecoration(
                                  color: cs.secondaryContainer,
                                  shape: BoxShape.circle,
                                ),
                                child: Text(
                                  '${item.quantity}',
                                  style: TextStyle(
                                    fontSize: 11,
                                    fontWeight: FontWeight.bold,
                                    color: cs.onSecondaryContainer,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      item.productName,
                                      style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
                                    ),
                                    Text(
                                      '${item.sku} • ₹${item.baseCost.toStringAsFixed(2)}/unit',
                                      style: TextStyle(fontSize: 12, color: cs.onSurface.withValues(alpha: 0.6)),
                                    ),
                                  ],
                                ),
                              ),
                              Text(
                                '₹${item.totalCost.toStringAsFixed(2)}',
                                style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                              ),
                            ],
                          ),
                        )),
                      ],
                    ),
                  ),
                );
              },
            ),
    );
  }

  Widget _buildStatBadge(BuildContext context, IconData icon, String text) {
    final cs = Theme.of(context).colorScheme;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: cs.onSurfaceVariant),
        const SizedBox(width: 4),
        Text(
          text,
          style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant, fontWeight: FontWeight.w500),
        ),
      ],
    );
  }
}
