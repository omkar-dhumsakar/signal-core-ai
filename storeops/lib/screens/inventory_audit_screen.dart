import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/inventory_provider.dart';
import '../theme/app_theme.dart';

class InventoryAuditScreen extends StatefulWidget {
  const InventoryAuditScreen({super.key});

  @override
  State<InventoryAuditScreen> createState() =>
      _InventoryAuditScreenState();
}

class _InventoryAuditScreenState extends State<InventoryAuditScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<InventoryProvider>().loadProducts();
    });
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final ext = StoreOpsColors.of(context);

    return Consumer<InventoryProvider>(
      builder: (context, provider, _) {
        if (provider.isLoading) {
          return Center(
              child: CircularProgressIndicator(color: cs.primary));
        }

        if (provider.error != null && provider.items.isEmpty) {
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.error_outline, size: 48, color: cs.outline),
                const SizedBox(height: 12),
                Text(provider.error!,
                    style: TextStyle(color: cs.onSurfaceVariant)),
                const SizedBox(height: 16),
                FilledButton.icon(
                  onPressed: () => provider.loadProducts(),
                  icon: const Icon(Icons.refresh),
                  label: const Text('Retry'),
                ),
              ],
            ),
          );
        }

        return ListView.builder(
          padding: const EdgeInsets.only(top: 8, bottom: 100),
          itemCount: provider.items.length + 1,
          itemBuilder: (context, index) {
            if (index == 0) {
              return Padding(
                padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Manual Stock Audit',
                      style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                          color: cs.onSurface),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Enter current on-hand counts to sync the RL agent\'s state.',
                      style: TextStyle(
                          fontSize: 13, color: cs.onSurfaceVariant),
                    ),
                  ],
                ),
              );
            }

            final item = provider.items[index - 1];
            final synced = provider.auditStatus[item.sku] == true;

            return _AuditItemCard(
              item: item,
              synced: synced,
              onSubmit: (qty) async {
                final success =
                    await provider.submitAudit(item.sku, qty);
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                    content: Text(success
                        ? '${item.name} synced: $qty units'
                        : 'Failed to sync ${item.name}'),
                    backgroundColor:
                        success ? ext.success : ext.critical,
                    behavior: SnackBarBehavior.floating,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10)),
                  ));
                }
              },
            );
          },
        );
      },
    );
  }
}

class _AuditItemCard extends StatefulWidget {
  final dynamic item;
  final bool synced;
  final Function(int) onSubmit;

  const _AuditItemCard({
    required this.item,
    required this.synced,
    required this.onSubmit,
  });

  @override
  State<_AuditItemCard> createState() => _AuditItemCardState();
}

class _AuditItemCardState extends State<_AuditItemCard> {
  late TextEditingController _controller;
  bool _editing = false;

  @override
  void initState() {
    super.initState();
    _controller =
        TextEditingController(text: '${widget.item.onHandQty}');
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final ext = StoreOpsColors.of(context);

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            Builder(
              builder: (context) {
                final cat = AppTheme.getCategoryIcon(widget.item.sku);
                final initials = widget.item.name.length >= 2
                    ? widget.item.name.substring(0, 2).toUpperCase()
                    : widget.item.name.toUpperCase();
                return SizedBox(
                  width: 44,
                  height: 44,
                  child: Stack(
                    children: [
                      Container(
                        width: 44,
                        height: 44,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          gradient: LinearGradient(
                            colors: [
                              cat.color,
                              cat.color.withValues(alpha: 0.65),
                            ],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          ),
                        ),
                        child: Center(
                          child: Text(
                            initials,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 15,
                              fontWeight: FontWeight.w800,
                              letterSpacing: 0.5,
                            ),
                          ),
                        ),
                      ),
                      if (widget.synced)
                        Positioned(
                          right: 0,
                          bottom: 0,
                          child: Container(
                            width: 16,
                            height: 16,
                            decoration: BoxDecoration(
                              color: ext.success,
                              shape: BoxShape.circle,
                              border: Border.all(
                                color: Theme.of(context).cardColor,
                                width: 2,
                              ),
                            ),
                            child: const Icon(
                              Icons.check,
                              color: Colors.white,
                              size: 10,
                            ),
                          ),
                        ),
                    ],
                  ),
                );
              },
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    widget.item.name,
                    style: TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 14,
                        color: cs.onSurface),
                  ),
                  Text(
                    '${widget.item.sku}  ·  ${widget.item.category}',
                    style: TextStyle(
                        fontSize: 11, color: cs.outline),
                  ),
                ],
              ),
            ),
            SizedBox(
              width: 70,
              child: TextField(
                controller: _controller,
                keyboardType: TextInputType.number,
                textAlign: TextAlign.center,
                style: TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 15,
                    color: cs.onSurface),
                decoration: InputDecoration(
                  isDense: true,
                  contentPadding: const EdgeInsets.symmetric(
                      horizontal: 8, vertical: 10),
                  border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8)),
                  filled: true,
                  fillColor: cs.surfaceContainerLow,
                ),
                onChanged: (_) => setState(() => _editing = true),
              ),
            ),
            const SizedBox(width: 8),
            IconButton(
              onPressed: _editing || !widget.synced
                  ? () {
                      final qty = int.tryParse(_controller.text);
                      if (qty != null && qty >= 0) {
                        widget.onSubmit(qty);
                        setState(() => _editing = false);
                      }
                    }
                  : null,
              icon: Icon(
                Icons.sync,
                color: _editing || !widget.synced
                    ? cs.primary
                    : cs.outline,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
