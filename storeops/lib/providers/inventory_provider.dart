import 'package:flutter/material.dart';
import '../models/directive.dart';
import '../services/api_service.dart';

class InventoryProvider extends ChangeNotifier {
  final ApiService _api;

  List<InventoryItem> _items = [];
  bool _isLoading = false;
  String? _error;
  final Map<String, bool> _auditStatus = {};

  InventoryProvider({ApiService? api}) : _api = api ?? ApiService();

  List<InventoryItem> get items => _items;
  bool get isLoading => _isLoading;
  String? get error => _error;
  Map<String, bool> get auditStatus => _auditStatus;

  Future<void> loadProducts() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      _items = await _api.fetchProducts();
    } catch (e) {
      _error = e.toString();
    }

    _isLoading = false;
    notifyListeners();
  }

  Future<bool> submitAudit(String sku, int onHandQty) async {
    try {
      await _api.submitAudit(sku, onHandQty);
      final idx = _items.indexWhere((i) => i.sku == sku);
      if (idx >= 0) {
        _items[idx].onHandQty = onHandQty;
      }
      _auditStatus[sku] = true;
      notifyListeners();
      return true;
    } catch (e) {
      _error = e.toString();
      notifyListeners();
      return false;
    }
  }

  void clearAuditStatus() {
    _auditStatus.clear();
    notifyListeners();
  }
}
