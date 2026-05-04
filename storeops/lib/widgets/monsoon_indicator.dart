import 'package:flutter/material.dart';
import '../models/directive.dart';
import '../theme/app_theme.dart';

class MonsoonIndicator extends StatelessWidget {
  final MonsoonStatus? status;

  const MonsoonIndicator({super.key, this.status});

  @override
  Widget build(BuildContext context) {
    if (status == null || !status!.active) {
      return const SizedBox.shrink();
    }

    final monsoonColor = StoreOpsColors.of(context).monsoon;

    return Container(
      margin: const EdgeInsets.only(right: 4),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: monsoonColor.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: monsoonColor.withValues(alpha: 0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.water_drop, size: 14, color: monsoonColor),
          const SizedBox(width: 4),
          Text(
            'Monsoon +${status!.additionalDelayDays}d',
            style: TextStyle(
              color: monsoonColor,
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
