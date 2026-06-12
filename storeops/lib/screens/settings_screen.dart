import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../providers/directives_provider.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final ApiService _api = ApiService();
  bool _uploading = false;
  Map<String, dynamic>? _lastResult;
  String? _error;

  Future<void> _pickAndUpload() async {
    try {
      FilePickerResult? result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['csv', 'xlsx'],
        withData: true,
      );

      if (result != null && result.files.isNotEmpty) {
        final file = result.files.first;
        if (file.bytes == null) return;

        setState(() {
          _uploading = true;
          _error = null;
          _lastResult = null;
        });

        final response = await _api.uploadSupplierFile(file.bytes!, file.name);
        if (!mounted) return;
        setState(() {
          _lastResult = response;
          _uploading = false;
        });
        final ins = response['inserted'] ?? 0;
        final upd = response['updated'] ?? 0;
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('Upload successful: $ins added, $upd updated'),
          backgroundColor: StoreOpsColors.of(context).success,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        ));
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _uploading = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('Upload failed: $e'),
        backgroundColor: StoreOpsColors.of(context).critical,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ));
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final ext = StoreOpsColors.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          // ── Signed-in Profile Card ──────────────────────────────
          Consumer<AuthProvider>(
            builder: (_, auth, __) {
              return Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFF4338CA), Color(0xFF6366F1)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: [
                    BoxShadow(
                      color: const Color(0xFF4338CA).withValues(alpha: 0.3),
                      blurRadius: 12,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: Row(
                  children: [
                    Container(
                      width: 48,
                      height: 48,
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.2),
                        shape: BoxShape.circle,
                      ),
                      child: Center(
                        child: Text(
                          (auth.managerName ?? 'M')[0].toUpperCase(),
                          style: const TextStyle(
                            fontSize: 22,
                            fontWeight: FontWeight.w700,
                            color: Colors.white,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            auth.managerName ?? 'Store Manager',
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w700,
                              color: Colors.white,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            auth.storeName ?? '',
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.white.withValues(alpha: 0.8),
                            ),
                          ),
                        ],
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text(
                        (auth.role ?? 'manager').toUpperCase(),
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: Colors.white.withValues(alpha: 0.9),
                          letterSpacing: 0.5,
                        ),
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
          const SizedBox(height: 24),

          // ── Supplier Management Section ────────────────────
          Text(
            'Supplier Management',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w700,
              color: cs.onSurface,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'Upload a CSV or XLSX file containing SKU, supplier name, and lead time '
            'to link each product to its supplier.',
            style: TextStyle(fontSize: 13, color: cs.onSurfaceVariant),
          ),
          const SizedBox(height: 20),

          // ── Upload Card ────────────────────────────────────
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: cs.surfaceContainerLowest,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: cs.outlineVariant.withValues(alpha: 0.5)),
              boxShadow: [
                BoxShadow(
                  color: cs.shadow.withValues(alpha: 0.05),
                  blurRadius: 10,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [Color(0xFF6366F1), Color(0xFF818CF8)],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Icon(Icons.cloud_upload_rounded,
                          color: Colors.white, size: 22),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Supplier Data',
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w700,
                              color: cs.onSurface,
                            ),
                          ),
                          Text(
                            'Accepts .csv and .xlsx files',
                            style: TextStyle(
                              fontSize: 11,
                              color: cs.outline,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),

                // Progress indicator
                if (_uploading)
                  Column(
                    children: [
                      LinearProgressIndicator(
                        borderRadius: BorderRadius.circular(4),
                        color: const Color(0xFF6366F1),
                        backgroundColor:
                            const Color(0xFF6366F1).withValues(alpha: 0.15),
                      ),
                      const SizedBox(height: 10),
                      Text(
                        'Uploading and processing...',
                        style: TextStyle(
                          fontSize: 12,
                          color: cs.onSurfaceVariant,
                        ),
                      ),
                      const SizedBox(height: 12),
                    ],
                  ),

                // Upload button
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: _uploading ? null : _pickAndUpload,
                    icon: const Icon(Icons.upload_file, size: 20),
                    label: Text(_uploading
                        ? 'Uploading...'
                        : 'Upload Suppliers'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF6366F1),
                      foregroundColor: Colors.white,
                      disabledBackgroundColor:
                          const Color(0xFF6366F1).withValues(alpha: 0.5),
                      disabledForegroundColor:
                          Colors.white.withValues(alpha: 0.7),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      elevation: 0,
                    ),
                  ),
                ),
              ],
            ),
          ),

          // ── Success Result ─────────────────────────────────
          if (_lastResult != null) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: ext.success.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                    color: ext.success.withValues(alpha: 0.25)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.check_circle, color: ext.success, size: 20),
                      const SizedBox(width: 8),
                      Text(
                        'Upload Successful',
                        style: TextStyle(
                          fontWeight: FontWeight.w700,
                          color: ext.success,
                          fontSize: 14,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  _ResultRow(
                      label: 'New suppliers linked',
                      value: '${_lastResult!['inserted']}'),
                  _ResultRow(
                      label: 'Existing records updated',
                      value: '${_lastResult!['updated']}'),
                  if ((_lastResult!['errors'] as List).isNotEmpty)
                    _ResultRow(
                      label: 'Errors',
                      value: '${(_lastResult!['errors'] as List).length}',
                      isError: true,
                    ),
                ],
              ),
            ),
          ],

          // ── Error Message ──────────────────────────────────
          if (_error != null) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: ext.critical.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                    color: ext.critical.withValues(alpha: 0.25)),
              ),
              child: Row(
                children: [
                  Icon(Icons.error_outline, color: ext.critical, size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      _error!,
                      style: TextStyle(
                        fontSize: 13,
                        color: ext.critical,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],

          const SizedBox(height: 32),

          // ── Daily Budget Section ────────────────────────────
          Text(
            'Daily Budget',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w700,
              color: cs.onSurface,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'Set the maximum daily ordering budget. Directives exceeding this '
            'limit will be marked as deferred.',
            style: TextStyle(fontSize: 13, color: cs.onSurfaceVariant),
          ),
          const SizedBox(height: 20),
          Consumer<DirectivesProvider>(
            builder: (_, provider, __) {
              return _BudgetEditor(
                currentBudget: provider.budgetSummary?.dailyBudget ?? 50000,
                onSave: (amount) async {
                  await provider.updateBudget(amount);
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                      content: Text('Budget updated to ₹${amount.toStringAsFixed(0)}'),
                      backgroundColor: ext.success,
                      behavior: SnackBarBehavior.floating,
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10)),
                    ));
                  }
                },
              );
            },
          ),

          const SizedBox(height: 32),

          // ── Sign Out Button ────────────────────────────────
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: () async {
                final confirmed = await showDialog<bool>(
                  context: context,
                  builder: (ctx) => AlertDialog(
                    title: const Text('Sign Out'),
                    content: const Text(
                        'Are you sure you want to sign out?'),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(ctx, false),
                        child: const Text('Cancel'),
                      ),
                      FilledButton(
                        onPressed: () => Navigator.pop(ctx, true),
                        child: const Text('Sign Out'),
                      ),
                    ],
                  ),
                );
                if (confirmed == true && context.mounted) {
                  await context.read<AuthProvider>().logout();
                  if (context.mounted) {
                    Navigator.of(context).popUntil((r) => r.isFirst);
                  }
                }
              },
              icon: Icon(Icons.logout_rounded, color: ext.critical),
              label: Text(
                'Sign Out',
                style: TextStyle(
                  fontWeight: FontWeight.w600,
                  color: ext.critical,
                ),
              ),
              style: OutlinedButton.styleFrom(
                side: BorderSide(color: ext.critical.withValues(alpha: 0.4)),
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
          ),

          const SizedBox(height: 24),

          // ── App Info ───────────────────────────────────────
          Center(
            child: Column(
              children: [
                Text(
                  'BB StoreOps v2.0.0-bb',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: cs.outline,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Signal Core AI',
                  style: TextStyle(
                    fontSize: 11,
                    color: cs.outlineVariant,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ResultRow extends StatelessWidget {
  final String label;
  final String value;
  final bool isError;

  const _ResultRow({
    required this.label,
    required this.value,
    this.isError = false,
  });

  @override
  Widget build(BuildContext context) {
    final ext = StoreOpsColors.of(context);
    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: TextStyle(
                fontSize: 12,
                color: Theme.of(context).colorScheme.onSurfaceVariant),
          ),
          Text(
            value,
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: isError ? ext.critical : ext.success,
            ),
          ),
        ],
      ),
    );
  }
}

class _BudgetEditor extends StatefulWidget {
  final double currentBudget;
  final Future<void> Function(double) onSave;

  const _BudgetEditor({required this.currentBudget, required this.onSave});

  @override
  State<_BudgetEditor> createState() => _BudgetEditorState();
}

class _BudgetEditorState extends State<_BudgetEditor> {
  late TextEditingController _controller;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(
        text: widget.currentBudget.toStringAsFixed(0));
  }

  @override
  void didUpdateWidget(covariant _BudgetEditor old) {
    super.didUpdateWidget(old);
    if (old.currentBudget != widget.currentBudget && !_saving) {
      _controller.text = widget.currentBudget.toStringAsFixed(0);
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: cs.surfaceContainerLowest,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: cs.outlineVariant.withValues(alpha: 0.5)),
        boxShadow: [
          BoxShadow(
            color: cs.shadow.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFF0EA5E9), Color(0xFF38BDF8)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.account_balance_wallet_rounded,
                    color: Colors.white, size: 22),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Order Budget',
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: cs.onSurface,
                      ),
                    ),
                    Text(
                      'Maximum spend per day (₹)',
                      style: TextStyle(
                        fontSize: 11,
                        color: cs.outline,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _controller,
            keyboardType: TextInputType.number,
            decoration: InputDecoration(
              prefixText: '₹ ',
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _saving
                  ? null
                  : () async {
                      final val = double.tryParse(_controller.text);
                      if (val == null || val <= 0) return;
                      setState(() => _saving = true);
                      await widget.onSave(val);
                      if (mounted) setState(() => _saving = false);
                    },
              icon: const Icon(Icons.save_rounded, size: 20),
              label: Text(_saving ? 'Saving...' : 'Save Budget'),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF0EA5E9),
                foregroundColor: Colors.white,
                disabledBackgroundColor:
                    const Color(0xFF0EA5E9).withValues(alpha: 0.5),
                disabledForegroundColor:
                    Colors.white.withValues(alpha: 0.7),
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                elevation: 0,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
