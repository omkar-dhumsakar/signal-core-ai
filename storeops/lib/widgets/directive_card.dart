import 'package:flutter/material.dart';
import '../models/directive.dart';
import '../theme/app_theme.dart';

class DirectiveCard extends StatelessWidget {
  final Directive directive;
  final VoidCallback onApprove;
  final VoidCallback onAdjust;

  const DirectiveCard({
    super.key,
    required this.directive,
    required this.onApprove,
    required this.onAdjust,
  });

  @override
  Widget build(BuildContext context) {
    final ext = StoreOpsColors.of(context);
    final cs = Theme.of(context).colorScheme;
    final color = ext.priorityColor(directive.priority);
    final isActioned = directive.status != 'pending';
    final isDeferred = directive.budgetStatus == 'deferred';
    final isTransfer = directive.directiveType == 'transfer';
    final isDiscount = directive.directiveType == 'discount';
    final isReplenishment = directive.directiveType == 'replenishment';

    return Opacity(
      opacity: isDeferred ? 0.7 : 1.0,
      child: Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      clipBehavior: Clip.antiAlias,
      shape: isDiscount 
          ? RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: const BorderSide(color: Colors.redAccent, width: 2),
            )
          : null,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(height: 4, color: isDeferred ? Colors.grey : color),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: Row(
              children: [
                Builder(
                  builder: (context) {
                    if (isDiscount) {
                      return Container(
                        width: 38,
                        height: 38,
                        decoration: BoxDecoration(
                          color: Colors.red.withValues(alpha: 0.12),
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(Icons.percent_rounded, color: Colors.red, size: 20),
                      );
                    }
                    final cat = AppTheme.getCategoryIcon(directive.sku);
                    return Container(
                      width: 38,
                      height: 38,
                      decoration: BoxDecoration(
                        color: cat.color.withValues(alpha: 0.12),
                        shape: BoxShape.circle,
                      ),
                      child: Icon(cat.icon, color: cat.color, size: 20),
                    );
                  },
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        directive.productName,
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                          letterSpacing: -0.3,
                          color: cs.onSurface,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Row(
                        children: [
                          Icon(AppTheme.priorityIcon(directive.priority),
                              color: color, size: 14),
                          const SizedBox(width: 4),
                          Text(
                            directive.sku,
                            style: TextStyle(
                              fontSize: 11,
                              color: cs.outline,
                              letterSpacing: 0.3,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                _PriorityChip(priority: directive.priority, color: color),
                const SizedBox(width: 6),
                _FulfillmentChip(channel: directive.fulfillmentChannel),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 6, 16, 0),
            child: Text(
              directive.reason,
              style: TextStyle(
                fontSize: 13,
                color: cs.onSurfaceVariant,
                height: 1.3,
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
            child: _StockRow(directive: directive),
          ),
          const Divider(height: 20),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                Icon(Icons.smart_toy_outlined, size: 18, color: cs.primary),
                const SizedBox(width: 6),
                Text(
                  'RL Recommendation: ',
                  style: TextStyle(fontSize: 13, color: cs.onSurfaceVariant),
                ),
                Text(
                  isDiscount
                      ? 'Flash Sale ${directive.recommendedQty} Units'
                      : '${isTransfer ? 'Transfer' : (isReplenishment ? 'Pull' : 'Order')} ${directive.recommendedQty} Units',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: isDiscount ? Colors.red : cs.primary,
                  ),
                ),
                if (isDiscount) ...[
                  const Spacer(),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: Colors.red.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: Colors.red.withValues(alpha: 0.3)),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.timer_outlined, size: 12, color: Colors.redAccent),
                        const SizedBox(width: 4),
                        Text(
                          'FEFO ALERT',
                          style: const TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                            color: Colors.redAccent,
                            letterSpacing: 0.5,
                          ),
                        ),
                      ],
                    ),
                  ),
                ] else if (isTransfer) ...[
                  const Spacer(),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: Colors.purple.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: Colors.purple.withValues(alpha: 0.3)),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.compare_arrows, size: 12, color: Colors.purple),
                        const SizedBox(width: 4),
                        Text(
                          'SOURCE: ${directive.transferSource}',
                          style: const TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                            color: Colors.purple,
                            letterSpacing: 0.5,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),
          if (directive.estimatedArrival != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
              child: Row(
                children: [
                  Icon(Icons.local_shipping_outlined,
                      size: 16, color: cs.outline),
                  const SizedBox(width: 6),
                  Text(
                    'Est. Arrival: ${directive.estimatedArrival}',
                    style: TextStyle(fontSize: 12, color: cs.outline),
                  ),
                ],
              ),
            ),
          // Cost badge
          if (directive.estimatedCost > 0)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
              child: Row(
                children: [
                  Icon(Icons.currency_rupee, size: 16, color: cs.outline),
                  const SizedBox(width: 4),
                  Text(
                    'Est. Cost: ₹${directive.estimatedCost.toStringAsFixed(0)}',
                    style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant, fontWeight: FontWeight.w600),
                  ),
                  if (isDeferred) ...[
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: Colors.orange.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: const Text(
                        'DEFERRED',
                        style: TextStyle(fontSize: 9, fontWeight: FontWeight.w700, color: Colors.orange, letterSpacing: 0.5),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          const SizedBox(height: 12),
          if (isActioned)
            _ConfirmedBanner(directive: directive)
          else
            _ActionButtons(
              onApprove: onApprove, 
              onAdjust: onAdjust,
              isTransfer: isTransfer,
              isDiscount: isDiscount,
              isReplenishment: isReplenishment,
            ),
          const SizedBox(height: 12),
        ],
      ),
    ),
    );
  }
}

class _PriorityChip extends StatelessWidget {
  final String priority;
  final Color color;

  const _PriorityChip({required this.priority, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        priority.toUpperCase(),
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w700,
          color: color,
          letterSpacing: 0.5,
        ),
      ),
    );
  }
}

class _StockRow extends StatelessWidget {
  final Directive directive;

  const _StockRow({required this.directive});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        _StockPill(
          label: 'On Hand',
          value: '${directive.currentStock}',
          icon: Icons.inventory_2_outlined,
        ),
        const SizedBox(width: 12),
        _StockPill(
          label: 'In Pipeline',
          value: '${directive.pipelineStock}',
          icon: Icons.move_to_inbox_outlined,
        ),
        const SizedBox(width: 12),
        Expanded(
          child: RLConfidenceGauge(
              confidence: directive.rlConfidence),
        ),
      ],
    );
  }
}

class _StockPill extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;

  const _StockPill(
      {required this.label, required this.value, required this.icon});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
        decoration: BoxDecoration(
          color: cs.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: cs.onSurfaceVariant),
            const SizedBox(width: 4),
            Flexible(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label,
                      style: TextStyle(fontSize: 9, color: cs.outline)),
                  Text(value,
                      style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: cs.onSurface)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ActionButtons extends StatelessWidget {
  final VoidCallback onApprove;
  final VoidCallback onAdjust;
  final bool isTransfer;
  final bool isDiscount;
  final bool isReplenishment;

  const _ActionButtons({
    required this.onApprove, 
    required this.onAdjust,
    this.isTransfer = false,
    this.isDiscount = false,
    this.isReplenishment = false,
  });

  @override
  Widget build(BuildContext context) {
    final ext = StoreOpsColors.of(context);
    final cs = Theme.of(context).colorScheme;
    
    IconData approveIcon = Icons.check_circle_outline;
    String approveLabel = 'APPROVE';
    Color approveColor = ext.success;
    
    if (isDiscount) {
      approveIcon = Icons.local_offer;
      approveLabel = 'PUSH DISCOUNT';
      approveColor = Colors.redAccent;
    } else if (isTransfer) {
      approveIcon = Icons.local_shipping;
      approveLabel = 'TRANSFER';
    } else if (isReplenishment) {
      approveIcon = Icons.account_tree_outlined;
      approveLabel = 'REPLENISH';
      approveColor = Colors.blueAccent;
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          Expanded(
            child: FilledButton.icon(
              onPressed: onApprove,
              icon: Icon(approveIcon, size: 18),
              label: Text(approveLabel),
              style: FilledButton.styleFrom(
                backgroundColor: approveColor,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 12),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10)),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: OutlinedButton.icon(
              onPressed: onAdjust,
              icon: const Icon(Icons.tune, size: 18),
              label: const Text('ADJUST'),
              style: OutlinedButton.styleFrom(
                foregroundColor: ext.adjust,
                padding: const EdgeInsets.symmetric(vertical: 12),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10)),
                side: BorderSide(color: cs.outlineVariant),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ConfirmedBanner extends StatelessWidget {
  final Directive directive;

  const _ConfirmedBanner({required this.directive});

  @override
  Widget build(BuildContext context) {
    final ext = StoreOpsColors.of(context);
    final cs = Theme.of(context).colorScheme;
    final isApproved = directive.status == 'approved';
    final color = isApproved ? ext.success : ext.medium;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Row(
        children: [
          Icon(
            isApproved ? Icons.check_circle : Icons.edit_note,
            color: color,
            size: 20,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  isApproved 
                    ? (directive.directiveType == 'discount' 
                        ? 'Discount Pulled' 
                        : (directive.directiveType == 'transfer' ? 'Transfer Authorized' 
                            : (directive.directiveType == 'replenishment' ? 'Replenishment Queued' : 'Order Confirmed'))) 
                    : 'Adjusted & Logged',
                  style: TextStyle(
                      fontWeight: FontWeight.w600,
                      color: color,
                      fontSize: 13),
                ),
                if (directive.confirmedQty != null)
                  Text(
                    '${directive.confirmedQty} units'
                    '${directive.orderId != null ? ' • ${directive.orderId}' : ''}',
                    style: TextStyle(
                        fontSize: 12, color: cs.onSurfaceVariant),
                  ),
                if (directive.estimatedArrival != null && isApproved)
                  Text(
                    'Arriving: ${directive.estimatedArrival}',
                    style: TextStyle(fontSize: 12, color: cs.outline),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// RL Confidence Gauge — visual bar indicator for agent certainty
// ---------------------------------------------------------------------------

class RLConfidenceGauge extends StatelessWidget {
  final double confidence;

  const RLConfidenceGauge({super.key, required this.confidence});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final pct = (confidence * 100).round();
    final int activeBars;
    final Color barColor;

    if (pct >= 80) {
      activeBars = 3;
      barColor = const Color(0xFF10B981); // green
    } else if (pct >= 50) {
      activeBars = 2;
      barColor = const Color(0xFFF59E0B); // yellow/amber
    } else {
      activeBars = 1;
      barColor = const Color(0xFFEF4444); // red
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
      decoration: BoxDecoration(
        color: cs.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.psychology_outlined,
                  size: 14, color: cs.onSurfaceVariant),
              const SizedBox(width: 4),
              Text('Confidence',
                  style: TextStyle(fontSize: 9, color: cs.outline)),
            ],
          ),
          const SizedBox(height: 4),
          Row(
            children: [
              _buildBar(activeBars >= 1, barColor, cs),
              const SizedBox(width: 3),
              _buildBar(activeBars >= 2, barColor, cs),
              const SizedBox(width: 3),
              _buildBar(activeBars >= 3, barColor, cs),
              const SizedBox(width: 6),
              Text(
                '$pct%',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  color: barColor,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildBar(bool active, Color color, ColorScheme cs) {
    return Container(
      width: 14,
      height: 10,
      decoration: BoxDecoration(
        color: active ? color : cs.outlineVariant.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(2),
      ),
    );
  }
}

/// Colored chip showing BigBasket fulfillment channel (BB NOW / BB DAILY / BB SLOTTED)
class _FulfillmentChip extends StatelessWidget {
  final String channel;
  const _FulfillmentChip({required this.channel});

  @override
  Widget build(BuildContext context) {
    final (label, chipColor) = switch (channel) {
      'bb_daily' => ('BB DAILY', const Color(0xFF0EA5E9)),
      'bb_slotted' => ('BB SLOTTED', const Color(0xFF8B5CF6)),
      _ => ('BB NOW', const Color(0xFF10B981)),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: chipColor.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: chipColor.withValues(alpha: 0.4)),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 9,
          fontWeight: FontWeight.w700,
          color: chipColor,
          letterSpacing: 0.5,
        ),
      ),
    );
  }
}
