import 'package:flutter/material.dart';
import '../models/directive.dart';

class AdjustBottomSheet extends StatefulWidget {
  final Directive directive;
  final Function(int adjustedQty, String? reason) onSubmit;

  const AdjustBottomSheet({
    super.key,
    required this.directive,
    required this.onSubmit,
  });

  @override
  State<AdjustBottomSheet> createState() => _AdjustBottomSheetState();
}

class _AdjustBottomSheetState extends State<AdjustBottomSheet> {
  late int _quantity;
  final _reasonController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _quantity = widget.directive.recommendedQty;
  }

  @override
  void dispose() {
    _reasonController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Container(
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(context).viewInsets.bottom,
      ),
      decoration: BoxDecoration(
        color: cs.surfaceContainerLowest,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(24, 12, 24, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: cs.outlineVariant,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 20),
            Text(
              'Adjust Order',
              style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: cs.onSurface),
            ),
            const SizedBox(height: 4),
            Text(
              widget.directive.productName,
              style: TextStyle(fontSize: 14, color: cs.onSurfaceVariant),
            ),
            const SizedBox(height: 6),
            Text(
              'AI recommended ${widget.directive.recommendedQty} units',
              style: TextStyle(fontSize: 13, color: cs.primary),
            ),
            const SizedBox(height: 24),
            Center(
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: cs.surfaceContainerLow,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: cs.outlineVariant),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    _StepButton(
                      icon: Icons.remove,
                      onPressed: _quantity > 0
                          ? () => setState(
                              () => _quantity = (_quantity - 5).clamp(0, 999))
                          : null,
                    ),
                    SizedBox(
                      width: 80,
                      child: Text(
                        '$_quantity',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontSize: 28,
                          fontWeight: FontWeight.w700,
                          color: cs.onSurface,
                        ),
                      ),
                    ),
                    _StepButton(
                      icon: Icons.add,
                      onPressed: () => setState(
                          () => _quantity = (_quantity + 5).clamp(0, 999)),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 8),
            Center(
              child: Text(
                'units',
                style: TextStyle(fontSize: 13, color: cs.outline),
              ),
            ),
            const SizedBox(height: 20),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                _QuickChip(
                  label: '−25%',
                  onTap: () => setState(() {
                    _quantity =
                        (widget.directive.recommendedQty * 0.75).round();
                  }),
                ),
                const SizedBox(width: 8),
                _QuickChip(
                  label: 'Reset',
                  onTap: () => setState(
                      () => _quantity = widget.directive.recommendedQty),
                ),
                const SizedBox(width: 8),
                _QuickChip(
                  label: '+25%',
                  onTap: () => setState(() {
                    _quantity =
                        (widget.directive.recommendedQty * 1.25).round();
                  }),
                ),
                const SizedBox(width: 8),
                _QuickChip(
                  label: '×2',
                  onTap: () => setState(
                      () => _quantity = widget.directive.recommendedQty * 2),
                ),
              ],
            ),
            const SizedBox(height: 20),
            TextField(
              controller: _reasonController,
              decoration: InputDecoration(
                labelText: 'Reason for Adjustment (optional)',
                hintText: 'e.g., Local event this weekend...',
                border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12)),
                filled: true,
                fillColor: cs.surfaceContainerLow,
              ),
              maxLines: 2,
            ),
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: () {
                  widget.onSubmit(
                    _quantity,
                    _reasonController.text.isEmpty
                        ? null
                        : _reasonController.text,
                  );
                  Navigator.pop(context);
                },
                style: FilledButton.styleFrom(
                  backgroundColor: cs.primary,
                  foregroundColor: cs.onPrimary,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12)),
                ),
                child: Text(
                  'Submit Adjustment  ·  $_quantity units',
                  style: const TextStyle(
                      fontSize: 15, fontWeight: FontWeight.w600),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _StepButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback? onPressed;

  const _StepButton({required this.icon, this.onPressed});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Material(
      color: onPressed != null
          ? cs.primary.withValues(alpha: 0.1)
          : cs.surfaceContainerHighest,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onPressed,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Icon(
            icon,
            color: onPressed != null ? cs.primary : cs.outline,
          ),
        ),
      ),
    );
  }
}

class _QuickChip extends StatelessWidget {
  final String label;
  final VoidCallback onTap;

  const _QuickChip({required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return ActionChip(
      label: Text(label, style: const TextStyle(fontSize: 12)),
      onPressed: onTap,
      backgroundColor: cs.surfaceContainerHighest,
      shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20)),
    );
  }
}
