import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart'; // for kIsWeb

class ApiClient {
  // Use localhost for Web/iOS, 10.0.2.2 for Android Emulator
  static String get baseUrl {
    if (kIsWeb) return 'http://127.0.0.1:8000/api/v1/';
    return 'http://10.0.2.2:8000/api/v1/';
  }

  final Dio _dio;

  ApiClient()
      : _dio = Dio(BaseOptions(
          baseUrl: baseUrl,
          connectTimeout: const Duration(seconds: 15),
          receiveTimeout: const Duration(seconds: 15),
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
        )) {
    _dio.interceptors.add(LogInterceptor(
      request: true,
      requestBody: true,
      responseBody: true,
      error: true,
    ));
  }

  Dio get client => _dio;
}
