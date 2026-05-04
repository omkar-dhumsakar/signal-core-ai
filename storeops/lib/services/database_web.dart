import '../models/directive.dart';

/// In-memory fallback for web platform where sqflite is unavailable.
class PlatformDatabase {
  final List<Directive> _cache = [];
  final List<Map<String, dynamic>> _pendingActions = [];
  int _actionIdCounter = 0;

  Future<void> cacheDirectives(List<Directive> directives) async {
    _cache
      ..clear()
      ..addAll(directives);
  }

  Future<List<Directive>> getCachedDirectives() async {
    return List.from(_cache);
  }

  Future<void> updateDirectiveStatus(
    String id,
    String status, {
    int? confirmedQty,
    String? orderId,
    int? leadTimeDays,
  }) async {
    final idx = _cache.indexWhere((d) => d.id == id);
    if (idx >= 0) {
      _cache[idx].status = status;
      if (confirmedQty != null) _cache[idx].confirmedQty = confirmedQty;
      if (orderId != null) _cache[idx].orderId = orderId;
      if (leadTimeDays != null) _cache[idx].leadTimeDays = leadTimeDays;
    }
  }

  Future<void> queueOfflineAction(
      String actionType, String payload) async {
    _pendingActions.add({
      'id': ++_actionIdCounter,
      'action_type': actionType,
      'payload': payload,
      'created_at': DateTime.now().toIso8601String(),
    });
  }

  Future<List<Map<String, dynamic>>> getPendingActions() async {
    return List.from(_pendingActions);
  }

  Future<void> clearPendingAction(int id) async {
    _pendingActions.removeWhere((a) => a['id'] == id);
  }
}
