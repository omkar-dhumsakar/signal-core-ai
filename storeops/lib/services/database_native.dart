import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';
import '../models/directive.dart';

class PlatformDatabase {
  static Database? _database;

  Future<Database> get database async {
    _database ??= await _initDatabase();
    return _database!;
  }

  Future<Database> _initDatabase() async {
    String path = join(await getDatabasesPath(), 'storeops.db');
    return await openDatabase(
      path,
      version: 1,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE directives (
            id TEXT PRIMARY KEY,
            sku TEXT NOT NULL,
            product_name TEXT NOT NULL,
            current_stock INTEGER NOT NULL,
            pipeline_stock INTEGER NOT NULL,
            reason TEXT NOT NULL,
            priority TEXT NOT NULL,
            recommended_qty INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            estimated_arrival TEXT,
            created_at TEXT NOT NULL,
            rl_confidence REAL DEFAULT 0.5,
            confirmed_qty INTEGER,
            order_id TEXT,
            lead_time_days INTEGER
          )
        ''');
        await db.execute('''
          CREATE TABLE pending_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
          )
        ''');
      },
    );
  }

  Future<void> cacheDirectives(List<Directive> directives) async {
    final db = await database;
    final batch = db.batch();
    batch.delete('directives');
    for (final d in directives) {
      batch.insert('directives', d.toDbMap(),
          conflictAlgorithm: ConflictAlgorithm.replace);
    }
    await batch.commit(noResult: true);
  }

  Future<List<Directive>> getCachedDirectives() async {
    final db = await database;
    final maps = await db.query(
      'directives',
      orderBy:
          "CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END",
    );
    return maps.map((m) => Directive.fromDbMap(m)).toList();
  }

  Future<void> updateDirectiveStatus(
    String id,
    String status, {
    int? confirmedQty,
    String? orderId,
    int? leadTimeDays,
  }) async {
    final db = await database;
    final updates = <String, dynamic>{'status': status};
    if (confirmedQty != null) updates['confirmed_qty'] = confirmedQty;
    if (orderId != null) updates['order_id'] = orderId;
    if (leadTimeDays != null) updates['lead_time_days'] = leadTimeDays;
    await db.update('directives', updates,
        where: 'id = ?', whereArgs: [id]);
  }

  Future<void> queueOfflineAction(
      String actionType, String payload) async {
    final db = await database;
    await db.insert('pending_actions', {
      'action_type': actionType,
      'payload': payload,
      'created_at': DateTime.now().toIso8601String(),
    });
  }

  Future<List<Map<String, dynamic>>> getPendingActions() async {
    final db = await database;
    return db.query('pending_actions', orderBy: 'created_at ASC');
  }

  Future<void> clearPendingAction(int id) async {
    final db = await database;
    await db.delete('pending_actions', where: 'id = ?', whereArgs: [id]);
  }
}
