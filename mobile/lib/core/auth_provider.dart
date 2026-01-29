import 'package:flutter/material.dart';
import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../core/api_client.dart';

class AuthProvider extends ChangeNotifier {
  final ApiClient _apiClient;
  bool _isAuthenticated = false;
  String? _token;
  String? _role;

  bool get isAuthenticated => _isAuthenticated;
  String? get role => _role;

  AuthProvider(this._apiClient);

  Future<void> login(String username, String password) async {
    try {
      // MVP: Django default auth doesn't give token easily without DRF Token Auth.
      // For MVP we assume we might need to implement a simple token view or use Basic Auth.
      // BUT, we have DRF installed. Let's use a custom login flow if needed, OR 
      // easiest for now: assume backend has a /auth/login endpoint or we just register.
      
      // Let's implement REGISTER flow first as it's cleaner for new users
      throw UnimplementedError("Login not fully implemented in backend yet, try register");
    } catch (e) {
      rethrow;
    }
  }

  Future<bool> register(String username, String password, String phone) async {
    try {
      final response = await _apiClient.client.post('/auth/register/', data: {
        'username': username,
        'password': password,
        'phone_number': phone,
        'role': 'CUSTOMER', // Default
      });
      
      if (response.statusCode == 201) {
        // Auto login (store credentials or token - for MVP just marking as authenticated locally)
        // In real world, get Token from response
        _isAuthenticated = true;
        _role = 'CUSTOMER';
        notifyListeners();
        return true;
      }
      return false;
    } catch (e) {
      print("Register Error: $e");
      return false;
    }
  }

  void logout() {
    _isAuthenticated = false;
    _token = null;
    notifyListeners();
  }
}
