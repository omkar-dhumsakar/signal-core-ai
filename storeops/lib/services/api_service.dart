import 'dart:convert';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:http/http.dart' as http;
import '../models/directive.dart';
import '../models/purchase_order.dart';

class ApiService {
  static String get baseUrl =>
      kIsWeb ? 'http://localhost:8002' : 'http://10.0.2.2:8002';

  final http.Client _client;

  ApiService({http.Client? client}) : _client = client ?? http.Client();

  Future<({List<Directive> directives, BudgetSummary budgetSummary})> fetchDirectives({String? category, String? storeId}) async {
    try {
      final params = <String, String>{};
      if (category != null) params['category'] = category;
      if (storeId != null) params['store_id'] = storeId;
      final uri = Uri.parse('$baseUrl/api/v1/directives').replace(queryParameters: params.isNotEmpty ? params : null);
      final response = await _client
          .get(uri)
          .timeout(const Duration(seconds: 60));

      if (response.statusCode == 200) {
        final Map<String, dynamic> body = jsonDecode(response.body);
        final List<dynamic> data = body['directives'] ?? [];
        final List<Directive> directives = data.map((j) => Directive.fromJson(j)).toList();
        final BudgetSummary budgetSummary = BudgetSummary.fromJson(body['budget_summary'] ?? {});
        
        return (
          directives: directives, 
          budgetSummary: budgetSummary
        );
      }
      throw ApiException(
          'Failed to fetch directives: ${response.statusCode}');
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('Network error: $e');
    }
  }

  Future<List<Store>> fetchStores() async {
    try {
      final response = await _client
          .get(Uri.parse('$baseUrl/api/v1/stores'))
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final List<dynamic> data = jsonDecode(response.body);
        return data.map((j) => Store.fromJson(j)).toList();
      }
      return [];
    } catch (_) {
      return [];
    }
  }

  Future<List<String>> fetchCategories() async {
    try {
      final response = await _client
          .get(Uri.parse('$baseUrl/api/v1/categories'))
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final List<dynamic> data = jsonDecode(response.body);
        return data.map((e) => e.toString()).toList();
      }
      return [];
    } catch (_) {
      return [];
    }
  }

  Future<Map<String, dynamic>> confirmOrder(
      String sku, int quantity, String directiveId) async {
    try {
      final response = await _client
          .post(
            Uri.parse('$baseUrl/api/v1/orders/confirm'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'sku': sku,
              'quantity': quantity,
              'directive_id': directiveId,
            }),
          )
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
      throw ApiException(
          'Order confirmation failed: ${response.statusCode}');
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('Network error: $e');
    }
  }

  Future<Map<String, dynamic>> submitAdjustment({
    required String directiveId,
    required String sku,
    required int originalQty,
    required int adjustedQty,
    String? reason,
  }) async {
    try {
      final response = await _client
          .post(
            Uri.parse('$baseUrl/api/v1/orders/adjust'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'directive_id': directiveId,
              'sku': sku,
              'original_qty': originalQty,
              'adjusted_qty': adjustedQty,
              'reason': reason,
            }),
          )
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
      throw ApiException('Adjustment failed: ${response.statusCode}');
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('Network error: $e');
    }
  }

  Future<MonsoonStatus> fetchMonsoonStatus() async {
    try {
      final response = await _client
          .get(Uri.parse('$baseUrl/api/v1/monsoon/status'))
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return MonsoonStatus.fromJson(jsonDecode(response.body));
      }
      throw ApiException(
          'Failed to fetch monsoon status: ${response.statusCode}');
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('Network error: $e');
    }
  }

  Future<Map<String, dynamic>> submitAudit(String sku, int onHandQty) async {
    try {
      final response = await _client
          .post(
            Uri.parse('$baseUrl/api/v1/inventory/audit'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'sku': sku,
              'on_hand_qty': onHandQty,
            }),
          )
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
      throw ApiException('Audit failed: ${response.statusCode}');
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('Network error: $e');
    }
  }

  Future<List<PurchaseOrder>> generatePurchaseOrders(String storeId) async {
    try {
      final response = await _client
          .post(Uri.parse('$baseUrl/api/v1/orders/generate-pos?store_id=$storeId'))
          .timeout(const Duration(seconds: 60));

      if (response.statusCode == 200) {
        final List<dynamic> data = jsonDecode(response.body);
        return data.map((j) => PurchaseOrder.fromJson(j)).toList();
      }
      throw ApiException('Failed to generate POs: ${response.statusCode}');
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('Network error: $e');
    }
  }

  Future<List<InventoryItem>> fetchProducts() async {
    try {
      final response = await _client
          .get(Uri.parse('$baseUrl/api/v1/products'))
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final List<dynamic> data = jsonDecode(response.body);
        return data.map((j) => InventoryItem.fromJson(j)).toList();
      }
      throw ApiException(
          'Failed to fetch products: ${response.statusCode}');
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('Network error: $e');
    }
  }

  /// Upload a supplier CSV/XLSX file to the backend.
  /// Returns the parsed response with inserted/updated counts.
  Future<Map<String, dynamic>> uploadSupplierFile(
      List<int> fileBytes, String fileName) async {
    try {
      final uri = Uri.parse('$baseUrl/api/v1/suppliers/upload');
      final request = http.MultipartRequest('POST', uri)
        ..files.add(http.MultipartFile.fromBytes(
          'file',
          fileBytes,
          filename: fileName,
        ));

      final streamed =
          await request.send().timeout(const Duration(seconds: 120));
      final response = await http.Response.fromStream(streamed);

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
      final detail = jsonDecode(response.body)['detail'] ?? 'Unknown error';
      throw ApiException('Upload failed: $detail');
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('Network error: $e');
    }
  }

  // ── Authentication ────────────────────────────────────────────────

  /// Authenticate a store manager. Returns the full response map on
  /// success (includes token, full_name, store_name, etc).
  Future<Map<String, dynamic>> login(String username, String password) async {
    try {
      final response = await _client
          .post(
            Uri.parse('$baseUrl/api/v1/auth/login'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'username': username, 'password': password}),
          )
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
      if (response.statusCode == 401) {
        throw ApiException('Invalid username or password');
      }
      throw ApiException('Login failed: ${response.statusCode}');
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('Network error: $e');
    }
  }

  /// Authenticate a store manager via Google Sign-In backend endpoint.
  Future<Map<String, dynamic>> loginWithGoogle(String email, String name) async {
    try {
      final response = await _client
          .post(
            Uri.parse('$baseUrl/api/v1/auth/google'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'email': email, 'name': name}),
          )
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
      if (response.statusCode == 401) {
        throw ApiException('Google authentication failed');
      }
      throw ApiException('Google login failed: ${response.statusCode}');
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('Network error: $e');
    }
  }

  /// Validate an existing token and fetch current manager info.
  Future<Map<String, dynamic>> fetchMe(String token) async {
    try {
      final response = await _client
          .get(Uri.parse('$baseUrl/api/v1/auth/me?token=$token'))
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
      throw ApiException('Token invalid: ${response.statusCode}');
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('Network error: $e');
    }
  }

  /// Sign out — invalidate the token server-side.
  Future<void> logout(String token) async {
    try {
      await _client
          .post(Uri.parse('$baseUrl/api/v1/auth/logout?token=$token'))
          .timeout(const Duration(seconds: 10));
    } catch (_) {
      // Best-effort; even if server unreachable, we clear local state.
    }
  }

  // ── Budget ─────────────────────────────────────────────────────

  Future<double> fetchBudget() async {
    try {
      final response = await _client
          .get(Uri.parse('$baseUrl/api/v1/budget'))
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return (data['daily_budget'] ?? 50000).toDouble();
      }
      return 50000;
    } catch (_) {
      return 50000;
    }
  }

  Future<double> updateBudget(double dailyBudget) async {
    try {
      final response = await _client
          .put(
            Uri.parse('$baseUrl/api/v1/budget'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'daily_budget': dailyBudget}),
          )
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return (data['daily_budget'] ?? dailyBudget).toDouble();
      }
      throw ApiException('Update budget failed: ${response.statusCode}');
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('Network error: $e');
    }
  }
}

class ApiException implements Exception {
  final String message;
  ApiException(this.message);

  @override
  String toString() => message;
}
