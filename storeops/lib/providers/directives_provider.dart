import 'dart:convert';
import 'package:flutter/material.dart';
import '../models/directive.dart';
import '../services/api_service.dart';
import '../services/database_service.dart';

class DirectivesProvider extends ChangeNotifier {
  final ApiService _api;
  final DatabaseService _db;

  List<Directive> _directives = [];
  List<String> _categories = [];
  String? _selectedCategory;
  MonsoonStatus? _monsoonStatus;
  BudgetSummary? _budgetSummary;
  bool _isLoading = false;
  String? _error;
  bool _isOffline = false;

  // Multi-store support
  List<Store> _stores = [];
  Store? _selectedStore;

  DirectivesProvider({ApiService? api, DatabaseService? db})
      : _api = api ?? ApiService(),
        _db = db ?? DatabaseService();

  List<Directive> get directives => _directives;
  List<String> get categories => _categories;
  String? get selectedCategory => _selectedCategory;
  List<Directive> get pendingDirectives =>
      _directives.where((d) => d.status == 'pending').toList();
  List<Directive> get completedDirectives =>
      _directives.where((d) => d.status != 'pending').toList();
  MonsoonStatus? get monsoonStatus => _monsoonStatus;
  BudgetSummary? get budgetSummary => _budgetSummary;
  bool get isLoading => _isLoading;
  String? get error => _error;
  bool get isOffline => _isOffline;
  List<Store> get stores => _stores;
  Store? get selectedStore => _selectedStore;

  Future<void> loadStores() async {
    _stores = await _api.fetchStores();
    if (_stores.isNotEmpty && _selectedStore == null) {
      _selectedStore = _stores.firstWhere(
        (s) => s.storeId == 'DS-BLR-INDIRANAGAR',
        orElse: () => _stores.first,
      );
    }
    notifyListeners();
  }

  Future<void> selectStore(Store store) async {
    _selectedStore = store;
    notifyListeners();
    await loadDirectives();
  }

  Future<void> loadCategories() async {
    _categories = await _api.fetchCategories();
    notifyListeners();
  }

  Future<void> filterByCategory(String? category) async {
    _selectedCategory = category;
    await loadDirectives();
  }

  Future<void> loadDirectives() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final result = await _api.fetchDirectives(
        category: _selectedCategory,
        storeId: _selectedStore?.storeId,
      );
      _directives = result.directives;
      _budgetSummary = result.budgetSummary;
      _monsoonStatus = await _api.fetchMonsoonStatus();
      _isOffline = false;
      await _db.cacheDirectives(_directives);
      // Load categories if not yet loaded
      if (_categories.isEmpty) {
        _categories = await _api.fetchCategories();
      }
      // Load stores if not yet loaded
      if (_stores.isEmpty) {
        await loadStores();
      }
    } catch (e) {
      _directives = await _db.getCachedDirectives();
      _isOffline = _directives.isNotEmpty;
      if (_directives.isEmpty) {
        _error = e.toString();
      }
    }

    _isLoading = false;
    notifyListeners();
  }

  Future<bool> approveDirective(Directive directive) async {
    try {
      final result = await _api.confirmOrder(
        directive.sku,
        directive.recommendedQty,
        directive.id,
      );

      directive.status = 'approved';
      directive.confirmedQty = directive.recommendedQty;
      directive.orderId = result['order_id'];
      directive.leadTimeDays = result['lead_time_days'];

      await _db.updateDirectiveStatus(
        directive.id,
        'approved',
        confirmedQty: directive.recommendedQty,
        orderId: result['order_id'],
        leadTimeDays: result['lead_time_days'],
      );
      notifyListeners();
      return true;
    } catch (e) {
      await _db.queueOfflineAction(
        'confirm',
        jsonEncode({
          'sku': directive.sku,
          'quantity': directive.recommendedQty,
          'directive_id': directive.id,
        }),
      );

      directive.status = 'approved';
      directive.confirmedQty = directive.recommendedQty;
      await _db.updateDirectiveStatus(
        directive.id,
        'approved',
        confirmedQty: directive.recommendedQty,
      );
      notifyListeners();
      return false;
    }
  }

  Future<bool> adjustDirective(
      Directive directive, int adjustedQty, String? reason) async {
    try {
      await _api.submitAdjustment(
        directiveId: directive.id,
        sku: directive.sku,
        originalQty: directive.recommendedQty,
        adjustedQty: adjustedQty,
        reason: reason,
      );

      directive.status = 'adjusted';
      directive.confirmedQty = adjustedQty;
      directive.adjustmentReason = reason;
      await _db.updateDirectiveStatus(
        directive.id,
        'adjusted',
        confirmedQty: adjustedQty,
      );
      notifyListeners();
      return true;
    } catch (e) {
      await _db.queueOfflineAction(
        'adjust',
        jsonEncode({
          'directive_id': directive.id,
          'sku': directive.sku,
          'original_qty': directive.recommendedQty,
          'adjusted_qty': adjustedQty,
          'reason': reason,
        }),
      );

      directive.status = 'adjusted';
      directive.confirmedQty = adjustedQty;
      directive.adjustmentReason = reason;
      await _db.updateDirectiveStatus(
        directive.id,
        'adjusted',
        confirmedQty: adjustedQty,
      );
      notifyListeners();
      return false;
    }
  }

  Future<int> syncPendingActions() async {
    final pending = await _db.getPendingActions();
    int synced = 0;

    for (final action in pending) {
      try {
        final payload = jsonDecode(action['payload']);
        if (action['action_type'] == 'confirm') {
          await _api.confirmOrder(
              payload['sku'], payload['quantity'], payload['directive_id']);
        } else if (action['action_type'] == 'adjust') {
          await _api.submitAdjustment(
            directiveId: payload['directive_id'],
            sku: payload['sku'],
            originalQty: payload['original_qty'],
            adjustedQty: payload['adjusted_qty'],
            reason: payload['reason'],
          );
        }
        await _db.clearPendingAction(action['id']);
        synced++;
      } catch (_) {
        break;
      }
    }

    if (synced > 0) {
      _isOffline = false;
      notifyListeners();
    }
    return synced;
  }

  Future<void> updateBudget(double amount) async {
    await _api.updateBudget(amount);
    await loadDirectives();
  }
}
