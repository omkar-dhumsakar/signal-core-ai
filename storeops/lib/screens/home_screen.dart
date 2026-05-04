import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/directive.dart';
import '../services/api_service.dart';
import '../providers/directives_provider.dart';
import '../widgets/directive_card.dart';
import '../widgets/adjust_bottom_sheet.dart';
import '../widgets/monsoon_indicator.dart';
import '../theme/app_theme.dart';
import 'inventory_audit_screen.dart';
import 'settings_screen.dart';
import 'po_summary_screen.dart';
import 'dashboard_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _tabController.addListener(() {
      setState(() {});
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<DirectivesProvider>().loadDirectives();
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Text(
              'BB StoreOps',
              style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: cs.onPrimary),
            ),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: cs.onPrimary.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                'v2.0.0-bb',
                style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w500,
                    color: cs.onPrimary.withValues(alpha: 0.8)),
              ),
            ),
          ],
        ),
        actions: [
          // ── Store Selector Dropdown ──
          Consumer<DirectivesProvider>(
            builder: (context, provider, _) {
              if (provider.stores.isEmpty) return const SizedBox.shrink();
              return PopupMenuButton<Store>(
                onSelected: (store) => provider.selectStore(store),
                offset: const Offset(0, 48),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                itemBuilder: (_) => provider.stores.map((store) {
                  final isSelected =
                      store.storeId == provider.selectedStore?.storeId;
                  return PopupMenuItem<Store>(
                    value: store,
                    child: Row(
                      children: [
                        Container(
                          width: 32,
                          height: 32,
                          decoration: BoxDecoration(
                            color: isSelected
                                ? cs.primary.withValues(alpha: 0.15)
                                : cs.surfaceContainerHighest,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Icon(
                            Icons.store_rounded,
                            size: 18,
                            color: isSelected
                                ? cs.primary
                                : cs.onSurfaceVariant,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(
                                store.name,
                                style: TextStyle(
                                  fontSize: 13,
                                  fontWeight: isSelected
                                      ? FontWeight.w700
                                      : FontWeight.w500,
                                  color: isSelected
                                      ? cs.primary
                                      : cs.onSurface,
                                ),
                              ),
                              Text(
                                store.location,
                                style: TextStyle(
                                  fontSize: 11,
                                  color: cs.onSurfaceVariant,
                                ),
                              ),
                            ],
                          ),
                        ),
                        if (isSelected)
                          Icon(Icons.check_circle, size: 18, color: cs.primary),
                      ],
                    ),
                  );
                }).toList(),
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: cs.onPrimary.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: cs.onPrimary.withValues(alpha: 0.2),
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.store_rounded,
                          size: 16, color: cs.onPrimary.withValues(alpha: 0.9)),
                      const SizedBox(width: 6),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            provider.selectedStore?.name ?? 'Select Store',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: cs.onPrimary,
                              height: 1.2,
                            ),
                          ),
                          if (provider.selectedStore != null)
                            Text(
                              provider.selectedStore!.location,
                              style: TextStyle(
                                fontSize: 9,
                                color: cs.onPrimary.withValues(alpha: 0.7),
                                height: 1.2,
                              ),
                            ),
                        ],
                      ),
                      const SizedBox(width: 4),
                      Icon(Icons.arrow_drop_down,
                          size: 18, color: cs.onPrimary.withValues(alpha: 0.8)),
                    ],
                  ),
                ),
              );
            },
          ),
          const SizedBox(width: 4),
          Consumer<DirectivesProvider>(
            builder: (_, p, __) =>
                MonsoonIndicator(status: p.monsoonStatus),
          ),
          Consumer<DirectivesProvider>(
            builder: (_, p, __) {
              if (p.isOffline) {
                final ext = StoreOpsColors.of(context);
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: Chip(
                    label: const Text('OFFLINE',
                        style:
                            TextStyle(fontSize: 10, color: Colors.white)),
                    backgroundColor: ext.warning,
                    padding: EdgeInsets.zero,
                    materialTapTargetSize:
                        MaterialTapTargetSize.shrinkWrap,
                  ),
                );
              }
              return const SizedBox.shrink();
            },
          ),
          IconButton(
            icon: Icon(Icons.tv_rounded, color: cs.onPrimary),
            tooltip: 'TV Control Tower',
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const DashboardScreen()),
            ),
          ),
          IconButton(
            icon: Icon(Icons.settings_rounded, color: cs.onPrimary),
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(
                  builder: (_) => const SettingsScreen()),
            ),
          ),
          const SizedBox(width: 4),
        ],
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: cs.onPrimary,
          labelColor: cs.onPrimary,
          unselectedLabelColor: cs.onPrimary.withValues(alpha: 0.6),
          tabs: const [
            Tab(
                icon: Icon(Icons.notifications_active, size: 20),
                text: 'Directives'),
            Tab(
                icon: Icon(Icons.inventory, size: 20),
                text: 'Audit'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: const [
          _DirectivesFeed(),
          InventoryAuditScreen(),
        ],
      ),
      floatingActionButton: _tabController.index == 0 
          ? Consumer<DirectivesProvider>(
              builder: (context, provider, _) {
                final cs = Theme.of(context).colorScheme;
                return FloatingActionButton.extended(
                  onPressed: () async {
                    if (provider.selectedStore == null) return;
                    
                    // Show a simple loading indicator
                    showDialog(
                      context: context, 
                      barrierDismissible: false,
                      builder: (c) => const Center(child: CircularProgressIndicator())
                    );
                    
                    try {
                      final api = ApiService();
                      final pos = await api.generatePurchaseOrders(provider.selectedStore!.storeId);
                      
                      // Dismiss loader
                      if (context.mounted) Navigator.pop(context);
                      
                      if (context.mounted) {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (context) => POSummaryScreen(purchaseOrders: pos),
                          )
                        );
                      }
                      
                      // Refresh directives to clear confirmed ones
                      provider.loadDirectives();
                    } catch (e) {
                      if (context.mounted) Navigator.pop(context);
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text('Failed to generate POs: $e'))
                        );
                      }
                    }
                  },
                  icon: const Icon(Icons.receipt_long),
                  label: const Text('Generate Daily POs'),
                  backgroundColor: cs.primaryContainer,
                  foregroundColor: cs.onPrimaryContainer,
                );
              }
            ) 
          : null,
    );
  }
}

class _DirectivesFeed extends StatelessWidget {
  const _DirectivesFeed();

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final ext = StoreOpsColors.of(context);

    return Consumer<DirectivesProvider>(
      builder: (context, provider, _) {
        if (provider.isLoading) {
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                CircularProgressIndicator(color: cs.primary),
                const SizedBox(height: 16),
                Text('Loading directives from RL Agent...',
                    style: TextStyle(color: cs.onSurfaceVariant)),
              ],
            ),
          );
        }

        if (provider.error != null && provider.directives.isEmpty) {
          return Center(
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.cloud_off, size: 64, color: cs.outline),
                  const SizedBox(height: 16),
                  Text(
                    'Could not reach the RL Agent',
                    style: TextStyle(
                        fontSize: 16, color: cs.onSurfaceVariant),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    provider.error!,
                    style: TextStyle(fontSize: 12, color: cs.outline),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 24),
                  FilledButton.icon(
                    onPressed: () => provider.loadDirectives(),
                    icon: const Icon(Icons.refresh),
                    label: const Text('Retry'),
                  ),
                ],
              ),
            ),
          );
        }

        final pending = provider.pendingDirectives;
        final completed = provider.completedDirectives;

        return RefreshIndicator(
          onRefresh: () => provider.loadDirectives(),
          color: cs.primary,
          child: ListView(
            padding: const EdgeInsets.only(top: 8, bottom: 100),
            children: [
              if (provider.isOffline)
                Container(
                  margin: const EdgeInsets.fromLTRB(16, 4, 16, 8),
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: ext.warning.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                        color: ext.warning.withValues(alpha: 0.3)),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.wifi_off, size: 18, color: ext.warning),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Showing cached directives. Actions will sync when online.',
                          style:
                              TextStyle(fontSize: 12, color: ext.warning),
                        ),
                      ),
                    ],
                  ),
                ),
              if (provider.monsoonStatus?.active == true)
                Container(
                  margin: const EdgeInsets.fromLTRB(16, 4, 16, 8),
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFF38BDF8), Color(0xFF6366F1)],
                      begin: Alignment.centerLeft,
                      end: Alignment.centerRight,
                    ),
                    borderRadius: BorderRadius.circular(12),
                    boxShadow: [
                      BoxShadow(
                        color: const Color(0xFF6366F1).withValues(alpha: 0.25),
                        blurRadius: 8,
                        offset: const Offset(0, 3),
                      ),
                    ],
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: 40,
                        height: 40,
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.2),
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(Icons.umbrella,
                            color: Colors.white, size: 22),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Monsoon Active',
                              style: TextStyle(
                                fontSize: 14,
                                fontWeight: FontWeight.w700,
                                color: Colors.white,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              'Lead time adjusted from 3 to ${3 + (provider.monsoonStatus?.additionalDelayDays ?? 3)} days due to regional weather disruptions.',
                              style: TextStyle(
                                fontSize: 12,
                                color: Colors.white.withValues(alpha: 0.9),
                                height: 1.3,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              // ── Stat Cards Row ──
              _StatCardsRow(
                criticalCount: provider.directives
                    .where((d) => d.priority == 'critical')
                    .length,
                pendingCount: pending.length,
                completedCount: completed.length,
                budgetSummary: provider.budgetSummary,
              ),
              // ── Category Filter Chips ──
              if (provider.categories.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 2, 16, 8),
                  child: SizedBox(
                    height: 38,
                    child: ListView(
                      scrollDirection: Axis.horizontal,
                      children: [
                        Padding(
                          padding: const EdgeInsets.only(right: 8),
                          child: FilterChip(
                            label: const Text('All'),
                            selected: provider.selectedCategory == null,
                            onSelected: (_) =>
                                provider.filterByCategory(null),
                            selectedColor:
                                cs.primary.withValues(alpha: 0.15),
                            checkmarkColor: cs.primary,
                            labelStyle: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: provider.selectedCategory == null
                                  ? cs.primary
                                  : cs.onSurfaceVariant,
                            ),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(20),
                              side: BorderSide(
                                color: provider.selectedCategory == null
                                    ? cs.primary
                                    : cs.outlineVariant,
                              ),
                            ),
                          ),
                        ),
                        ...provider.categories.map((cat) => Padding(
                              padding: const EdgeInsets.only(right: 8),
                              child: FilterChip(
                                label: Text(cat),
                                selected:
                                    provider.selectedCategory == cat,
                                onSelected: (_) =>
                                    provider.filterByCategory(
                                        provider.selectedCategory == cat
                                            ? null
                                            : cat),
                                selectedColor:
                                    cs.primary.withValues(alpha: 0.15),
                                checkmarkColor: cs.primary,
                                labelStyle: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w600,
                                  color:
                                      provider.selectedCategory == cat
                                          ? cs.primary
                                          : cs.onSurfaceVariant,
                                ),
                                shape: RoundedRectangleBorder(
                                  borderRadius:
                                      BorderRadius.circular(20),
                                  side: BorderSide(
                                    color:
                                        provider.selectedCategory == cat
                                            ? cs.primary
                                            : cs.outlineVariant,
                                  ),
                                ),
                              ),
                            )),
                      ],
                    ),
                  ),
                ),
              if (pending.isNotEmpty) ...[
                _SectionHeader(
                  title: 'Pending Actions',
                  count: pending.length,
                  color: ext.critical,
                ),
                ...pending.map((d) => DirectiveCard(
                      directive: d,
                      onApprove: () =>
                          _handleApprove(context, d),
                      onAdjust: () =>
                          _handleAdjust(context, d),
                    )),
              ],
              if (completed.isNotEmpty) ...[
                _SectionHeader(
                  title: 'Completed',
                  count: completed.length,
                  color: ext.success,
                ),
                ...completed.map((d) => DirectiveCard(
                      directive: d,
                      onApprove: () {},
                      onAdjust: () {},
                    )),
              ],
              if (pending.isEmpty && completed.isEmpty)
                Center(
                  child: Padding(
                    padding: const EdgeInsets.all(64),
                    child: Column(
                      children: [
                        Icon(Icons.check_circle_outline,
                            size: 64, color: cs.outlineVariant),
                        const SizedBox(height: 16),
                        Text(
                          'All clear! No directives right now.',
                          style: TextStyle(color: cs.outline),
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        );
      },
    );
  }

  void _handleApprove(
      BuildContext context, Directive directive) async {
    final ext = StoreOpsColors.of(context);
    final provider = context.read<DirectivesProvider>();
    final online = await provider.approveDirective(directive);
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(online
            ? 'Order confirmed: ${directive.recommendedQty} units of ${directive.productName}'
            : 'Queued offline — will sync when connected'),
        backgroundColor: online ? ext.success : ext.warning,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10)),
      ));
    }
  }

  void _handleAdjust(
      BuildContext context, Directive directive) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => AdjustBottomSheet(
        directive: directive,
        onSubmit: (qty, reason) async {
          final ext = StoreOpsColors.of(context);
          final provider = context.read<DirectivesProvider>();
          final online = await provider.adjustDirective(
              directive, qty, reason);
          if (context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(SnackBar(
              content: Text(online
                  ? 'Adjustment logged for RLHF: $qty units'
                  : 'Adjustment queued offline'),
              backgroundColor: online ? ext.medium : ext.warning,
              behavior: SnackBarBehavior.floating,
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10)),
            ));
          }
        },
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  final int count;
  final Color color;

  const _SectionHeader({
    required this.title,
    required this.count,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 4),
      child: Row(
        children: [
          Text(
            title,
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: cs.onSurfaceVariant,
              letterSpacing: 0.5,
            ),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(
                horizontal: 8, vertical: 2),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              '$count',
              style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  color: color),
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Stat Cards Row — horizontal overview cards above the directive feed
// ---------------------------------------------------------------------------

class _StatCardsRow extends StatelessWidget {
  final int criticalCount;
  final int pendingCount;
  final int completedCount;
  final BudgetSummary? budgetSummary;

  const _StatCardsRow({
    required this.criticalCount,
    required this.pendingCount,
    required this.completedCount,
    this.budgetSummary,
  });

  @override
  Widget build(BuildContext context) {
    final ext = StoreOpsColors.of(context);
    return SizedBox(
      height: 110,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        children: [
          _StatCard(
            count: criticalCount,
            label: 'Critical Items',
            icon: Icons.warning_amber_rounded,
            gradientColors: [
              ext.critical,
              ext.critical.withValues(alpha: 0.7),
            ],
          ),
          const SizedBox(width: 12),
          _StatCard(
            count: pendingCount,
            label: 'Pending Actions',
            icon: Icons.pending_actions_rounded,
            gradientColors: const [
              Color(0xFF6366F1),
              Color(0xFF818CF8),
            ],
          ),
          const SizedBox(width: 12),
          _StatCard(
            count: completedCount,
            label: 'Completed',
            icon: Icons.check_circle_outline_rounded,
            gradientColors: [
              ext.success,
              ext.success.withValues(alpha: 0.7),
            ],
          ),
          if (budgetSummary != null) ...[
            const SizedBox(width: 12),
            _BudgetStatCard(summary: budgetSummary!),
          ],
        ],
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  final int count;
  final String label;
  final IconData icon;
  final List<Color> gradientColors;

  const _StatCard({
    required this.count,
    required this.label,
    required this.icon,
    required this.gradientColors,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 150,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: gradientColors,
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: gradientColors.first.withValues(alpha: 0.3),
            blurRadius: 8,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '$count',
                style: const TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.w800,
                  color: Colors.white,
                  height: 1,
                ),
              ),
              Icon(icon, color: Colors.white.withValues(alpha: 0.8), size: 22),
            ],
          ),
          Text(
            label,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w500,
              color: Colors.white.withValues(alpha: 0.9),
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Budget Stat Card — shows allocated vs total budget
// ---------------------------------------------------------------------------

class _BudgetStatCard extends StatelessWidget {
  final BudgetSummary summary;

  const _BudgetStatCard({required this.summary});

  String _formatK(double v) {
    if (v >= 1000) return '₹${(v / 1000).toStringAsFixed(1)}K';
    return '₹${v.toStringAsFixed(0)}';
  }

  @override
  Widget build(BuildContext context) {
    final pct = summary.dailyBudget > 0
        ? (summary.totalAllocated / summary.dailyBudget).clamp(0.0, 1.0)
        : 0.0;

    return Container(
      width: 170,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF0EA5E9), Color(0xFF38BDF8)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF0EA5E9).withValues(alpha: 0.3),
            blurRadius: 8,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Flexible(
                child: Text(
                  '${_formatK(summary.totalAllocated)} / ${_formatK(summary.dailyBudget)}',
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                    height: 1,
                  ),
                ),
              ),
              Icon(Icons.account_balance_wallet_rounded,
                  color: Colors.white.withValues(alpha: 0.8), size: 20),
            ],
          ),
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(3),
            child: LinearProgressIndicator(
              value: pct,
              minHeight: 5,
              backgroundColor: Colors.white.withValues(alpha: 0.25),
              valueColor: const AlwaysStoppedAnimation<Color>(Colors.white),
            ),
          ),
          const SizedBox(height: 4),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Daily Budget',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w500,
                  color: Colors.white.withValues(alpha: 0.9),
                ),
              ),
              if (summary.deferredCount > 0)
                Text(
                  '${summary.deferredCount} deferred',
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                    color: Colors.white.withValues(alpha: 0.8),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}
