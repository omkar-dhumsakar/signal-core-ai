import '../models/directive.dart';

// Conditional sqflite import — only used on mobile
import 'database_native.dart' if (dart.library.html) 'database_web.dart'
    as platform_db;

class DatabaseService {
  final platform_db.PlatformDatabase _db = platform_db.PlatformDatabase();

  Future<void> cacheDirectives(List<Directive> directives) =>
      _db.cacheDirectives(directives);

  Future<List<Directive>> getCachedDirectives() =>
      _db.getCachedDirectives();

  Future<void> updateDirectiveStatus(
    String id,
    String status, {
    int? confirmedQty,
    String? orderId,
    int? leadTimeDays,
  }) =>
      _db.updateDirectiveStatus(id, status,
          confirmedQty: confirmedQty,
          orderId: orderId,
          leadTimeDays: leadTimeDays);

  Future<void> queueOfflineAction(String actionType, String payload) =>
      _db.queueOfflineAction(actionType, payload);

  Future<List<Map<String, dynamic>>> getPendingActions() =>
      _db.getPendingActions();

  Future<void> clearPendingAction(int id) =>
      _db.clearPendingAction(id);
}
