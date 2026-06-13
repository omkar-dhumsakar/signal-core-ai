import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/directives_provider.dart';
import '../widgets/directive_card.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<DirectivesProvider>();

    // Calculate metrics
    int criticalCount = 0;
    int transferCount = 0;
    int discountCount = 0;
    int orderCount = 0;

    for (var d in provider.directives) {
      if (d.status != 'pending') continue;
      if (d.priority == 'critical') criticalCount++;
      if (d.directiveType == 'transfer') transferCount++;
      if (d.directiveType == 'discount') discountCount++;
      if (d.directiveType == 'purchase') orderCount++;
    }

    return Scaffold(
      backgroundColor: const Color(0xFF0F111A), // Dark TV background
      appBar: AppBar(
        title: const Text('CONTROL TOWER', style: TextStyle(fontWeight: FontWeight.w900, letterSpacing: 2)),
        centerTitle: true,
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        actions: [
          Center(
            child: Padding(
              padding: const EdgeInsets.only(right: 16.0),
              child: Text(
                provider.selectedStore?.name ?? 'ALL STORES',
                style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.blueAccent),
              ),
            ),
          )
        ],
      ),
      body: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // LEFT PANEL: Kpis
          Container(
            width: 300,
            padding: const EdgeInsets.all(16),
            color: const Color(0xFF161925),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text('LIVE METRICS', style: TextStyle(color: Colors.white54, fontSize: 12, fontWeight: FontWeight.bold)),
                const SizedBox(height: 16),
                _KpiCard(title: 'CRITICAL', value: '$criticalCount', color: Colors.redAccent, icon: Icons.warning_amber_rounded),
                const SizedBox(height: 12),
                _KpiCard(title: 'TRANSFERS', value: '$transferCount', color: Colors.purpleAccent, icon: Icons.local_shipping),
                const SizedBox(height: 12),
                _KpiCard(title: 'FLASH SALES', value: '$discountCount', color: Colors.orangeAccent, icon: Icons.local_offer),
                const SizedBox(height: 12),
                _KpiCard(title: 'PURCHASE PO', value: '$orderCount', color: Colors.blueAccent, icon: Icons.receipt_long),
                const Spacer(),
                if (provider.isOffline)
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(color: Colors.red.withValues(alpha: 0.2), borderRadius: BorderRadius.circular(8)),
                    child: const Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.wifi_off, color: Colors.red),
                        SizedBox(width: 8),
                        Text('SYSTEM OFFLINE', style: TextStyle(color: Colors.red, fontWeight: FontWeight.bold)),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          // RIGHT PANEL: Directive Grid
          Expanded(
            child: provider.isLoading
                ? const Center(child: CircularProgressIndicator())
                : GridView.builder(
                    padding: const EdgeInsets.all(16),
                    gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
                      maxCrossAxisExtent: 400,
                      mainAxisExtent: 250,
                      crossAxisSpacing: 16,
                      mainAxisSpacing: 16,
                    ),
                    itemCount: provider.directives.length,
                    itemBuilder: (context, index) {
                      final dir = provider.directives[index];
                      return DirectiveCard(
                        directive: dir,
                        onApprove: () {},
                        onAdjust: () {},
                      );
                    },
                  ),
          )
        ],
      ),
    );
  }
}

class _KpiCard extends StatelessWidget {
  final String title;
  final String value;
  final Color color;
  final IconData icon;

  const _KpiCard({required this.title, required this.value, required this.color, required this.icon});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        border: Border.all(color: color.withValues(alpha: 0.3)),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w700, letterSpacing: 1)),
              const SizedBox(height: 4),
              Text(value, style: const TextStyle(color: Colors.white, fontSize: 32, fontWeight: FontWeight.w900)),
            ],
          ),
          Icon(icon, color: color.withValues(alpha: 0.8), size: 40),
        ],
      ),
    );
  }
}
