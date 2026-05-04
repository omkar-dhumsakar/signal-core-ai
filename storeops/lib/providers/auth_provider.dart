import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:google_sign_in/google_sign_in.dart';
import '../services/api_service.dart';

/// Manages authentication state for the StoreOps app.
class AuthProvider extends ChangeNotifier {
  final ApiService _api = ApiService();

  bool _isAuthenticated = false;
  bool _isLoading = true; // starts true until tryAutoLogin completes
  String? _token;
  String? _managerName;
  String? _storeName;
  String? _role;
  String? _error;

  bool get isAuthenticated => _isAuthenticated;
  bool get isLoading => _isLoading;
  String? get token => _token;
  String? get managerName => _managerName;
  String? get storeName => _storeName;
  String? get role => _role;
  String? get error => _error;

  // ── Login ──────────────────────────────────────────────────────────

  Future<bool> login(String username, String password) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final data = await _api.login(username, password);
      _token = data['token'] as String?;
      _managerName = data['full_name'] as String?;
      _storeName = data['store_name'] as String?;
      _role = data['role'] as String?;
      _isAuthenticated = true;
      _error = null;

      // Persist token
      final prefs = await SharedPreferences.getInstance();
      if (_token != null) {
        await prefs.setString('auth_token', _token!);
      }
    } on ApiException catch (e) {
      _error = e.message;
      _isAuthenticated = false;
    } catch (e) {
      _error = 'Connection error. Please check that the server is running.';
      _isAuthenticated = false;
    }

    _isLoading = false;
    notifyListeners();
    return _isAuthenticated;
  }

  Future<bool> loginWithGoogle(String email, String name) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final data = await _api.loginWithGoogle(email, name);
      _token = data['token'] as String?;
      _managerName = data['full_name'] as String?;
      _storeName = data['store_name'] as String?;
      _role = data['role'] as String?;
      _isAuthenticated = true;
      _error = null;

      // Persist token
      final prefs = await SharedPreferences.getInstance();
      if (_token != null) {
        await prefs.setString('auth_token', _token!);
      }
    } on ApiException catch (e) {
      _error = e.message;
      _isAuthenticated = false;
    } catch (e) {
      _error = 'Connection error. Please check that the server is running.';
      _isAuthenticated = false;
    }

    _isLoading = false;
    notifyListeners();
    return _isAuthenticated;
  }

  // ── Auto-login ─────────────────────────────────────────────────────

  Future<void> tryAutoLogin() async {
    _isLoading = true;
    notifyListeners();

    try {
      final prefs = await SharedPreferences.getInstance();
      final storedToken = prefs.getString('auth_token');

      if (storedToken != null && storedToken.isNotEmpty) {
        // Validate the stored token against the backend
        final data = await _api.fetchMe(storedToken);
        _token = storedToken;
        _managerName = data['full_name'] as String?;
        _storeName = data['store_name'] as String?;
        _role = data['role'] as String?;
        _isAuthenticated = true;
      } else {
        _isAuthenticated = false;
      }
    } catch (_) {
      // Token invalid or server unreachable — require fresh login
      _isAuthenticated = false;
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove('auth_token');
    }

    _isLoading = false;
    notifyListeners();
  }

  // ── Logout ─────────────────────────────────────────────────────────

  Future<void> logout() async {
    // Invalidate token on the server (best-effort)
    if (_token != null) {
      await _api.logout(_token!);
    }

    // Sign out of Google if applicable (best-effort)
    try {
      await GoogleSignIn().signOut();
    } catch (_) {}

    // Clear persisted token
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('auth_token');

    _token = null;
    _managerName = null;
    _storeName = null;
    _role = null;
    _isAuthenticated = false;
    _error = null;
    notifyListeners();
  }
}
