import 'package:flutter/material.dart';

// ---------------------------------------------------------------------------
// BigBasket Green — enterprise palette for BB StoreOps
// ---------------------------------------------------------------------------

@immutable
class StoreOpsColors extends ThemeExtension<StoreOpsColors> {
  const StoreOpsColors({
    required this.critical,
    required this.high,
    required this.medium,
    required this.low,
    required this.success,
    required this.adjust,
    required this.monsoon,
    required this.warning,
  });

  final Color critical;
  final Color high;
  final Color medium;
  final Color low;
  final Color success;
  final Color adjust;
  final Color monsoon;
  final Color warning;

  static const light = StoreOpsColors(
    critical: Color(0xFFEF4444),
    high: Color(0xFFF59E0B),
    medium: Color(0xFF6366F1),
    low: Color(0xFF94A3B8),
    success: Color(0xFF10B981),
    adjust: Color(0xFF64748B),
    monsoon: Color(0xFF0EA5E9),
    warning: Color(0xFFF97316),
  );

  static StoreOpsColors of(BuildContext context) =>
      Theme.of(context).extension<StoreOpsColors>()!;

  Color priorityColor(String priority) {
    switch (priority) {
      case 'critical':
        return critical;
      case 'high':
        return high;
      case 'medium':
        return medium;
      default:
        return low;
    }
  }

  @override
  StoreOpsColors copyWith({
    Color? critical,
    Color? high,
    Color? medium,
    Color? low,
    Color? success,
    Color? adjust,
    Color? monsoon,
    Color? warning,
  }) =>
      StoreOpsColors(
        critical: critical ?? this.critical,
        high: high ?? this.high,
        medium: medium ?? this.medium,
        low: low ?? this.low,
        success: success ?? this.success,
        adjust: adjust ?? this.adjust,
        monsoon: monsoon ?? this.monsoon,
        warning: warning ?? this.warning,
      );

  @override
  StoreOpsColors lerp(covariant StoreOpsColors? other, double t) {
    if (other == null) return this;
    return StoreOpsColors(
      critical: Color.lerp(critical, other.critical, t)!,
      high: Color.lerp(high, other.high, t)!,
      medium: Color.lerp(medium, other.medium, t)!,
      low: Color.lerp(low, other.low, t)!,
      success: Color.lerp(success, other.success, t)!,
      adjust: Color.lerp(adjust, other.adjust, t)!,
      monsoon: Color.lerp(monsoon, other.monsoon, t)!,
      warning: Color.lerp(warning, other.warning, t)!,
    );
  }
}

class AppTheme {
  AppTheme._();

  // BigBasket brand green
  static const _bbGreen = Color(0xFF84C225);
  static const _bbDarkGreen = Color(0xFF2D7A2D);

  static ThemeData get theme {
    final scheme = ColorScheme.fromSeed(
      seedColor: _bbGreen,
      primary: _bbDarkGreen,
      secondary: _bbGreen,
      surface: const Color(0xFFF8FAF5),
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: scheme.surface,
      appBarTheme: AppBarTheme(
        backgroundColor: _bbDarkGreen,
        foregroundColor: Colors.white,
        elevation: 0,
        centerTitle: false,
      ),
      cardTheme: CardThemeData(
        elevation: 2,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        color: scheme.surfaceContainerLowest,
      ),
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: _bbGreen,
        foregroundColor: Colors.white,
      ),
      dividerTheme: DividerThemeData(color: scheme.outlineVariant),
      extensions: const [StoreOpsColors.light],
    );
  }

  static IconData priorityIcon(String priority) {
    switch (priority) {
      case 'critical':
        return Icons.error;
      case 'high':
        return Icons.warning_amber_rounded;
      case 'medium':
        return Icons.info_outline;
      default:
        return Icons.low_priority;
    }
  }

  /// Returns a unique [IconData] and [Color] for each BigBasket product
  /// category, derived from SKU keyword matching.
  static ({IconData icon, Color color}) getCategoryIcon(String sku) {
    final s = sku.toUpperCase();

    // Fruits & Vegetables
    if (s.contains('FRUIT') || s.contains('VEG') || s.contains('TOMATO') ||
        s.contains('ONION') || s.contains('POTATO') || s.contains('MANGO')) {
      return (icon: Icons.eco_rounded, color: const Color(0xFF10B981));
    }
    // Dairy & Eggs
    if (s.contains('MILK') || s.contains('CURD') || s.contains('PANEER') ||
        s.contains('CHEESE') || s.contains('EGG') || s.contains('BUTTER') ||
        s.contains('YOGURT')) {
      return (icon: Icons.water_drop_rounded, color: const Color(0xFF0EA5E9));
    }
    // Meat & Seafood
    if (s.contains('CHICKEN') || s.contains('MUTTON') || s.contains('FISH') ||
        s.contains('PRAWN') || s.contains('MEAT') || s.contains('SEAFOOD')) {
      return (icon: Icons.restaurant_rounded, color: const Color(0xFFEF4444));
    }
    // Bakery & Snacks
    if (s.contains('BREAD') || s.contains('CAKE') || s.contains('BISCUIT') ||
        s.contains('CHIPS') || s.contains('SNACK') || s.contains('BAKERY')) {
      return (icon: Icons.bakery_dining_rounded, color: const Color(0xFFD97706));
    }
    // Beverages
    if (s.contains('JUICE') || s.contains('COFFEE') || s.contains('TEA') ||
        s.contains('WATER') || s.contains('SODA') || s.contains('DRINK')) {
      return (icon: Icons.local_cafe_rounded, color: const Color(0xFF8B5CF6));
    }
    // Staples & Grains
    if (s.contains('RICE') || s.contains('WHEAT') || s.contains('ATTA') ||
        s.contains('DAL') || s.contains('FLOUR') || s.contains('GRAIN') ||
        s.contains('OIL') || s.contains('SUGAR') || s.contains('SALT')) {
      return (icon: Icons.grass_rounded, color: const Color(0xFFF59E0B));
    }
    // Personal Care
    if (s.contains('SOAP') || s.contains('SHAMPOO') || s.contains('CREAM') ||
        s.contains('LOTION') || s.contains('CARE')) {
      return (icon: Icons.spa_rounded, color: const Color(0xFFEC4899));
    }
    // Spices
    if (s.contains('SPICE') || s.contains('PEPPER') || s.contains('MASALA') ||
        s.contains('TURMERIC') || s.contains('CHILLI')) {
      return (icon: Icons.local_fire_department_rounded, color: const Color(0xFFDC2626));
    }
    // Household
    if (s.contains('DETERGENT') || s.contains('CLEANER') || s.contains('HOUSE')) {
      return (icon: Icons.cleaning_services_rounded, color: const Color(0xFF14B8A6));
    }
    // Default — general grocery
    return (icon: Icons.shopping_basket_rounded, color: const Color(0xFF64748B));
  }
}
