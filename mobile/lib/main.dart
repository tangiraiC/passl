import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:google_fonts/google_fonts.dart';

import 'core/api_client.dart';
import 'core/auth_provider.dart';
import 'core/cart_provider.dart';
import 'features/auth/login_screen.dart';
import 'features/home/home_screen.dart';
import 'features/shop/checkout_screen.dart';
import 'features/rider/job_feed_screen.dart';

void main() {
  runApp(
    MultiProvider(
      providers: [
        Provider(create: (_) => ApiClient()),
        ChangeNotifierProxyProvider<ApiClient, AuthProvider>(
          create: (context) => AuthProvider(context.read<ApiClient>()),
          update: (context, apiClient, previous) => AuthProvider(apiClient),
        ),
        ChangeNotifierProvider(create: (_) => CartProvider()),
      ],
      child: const PasslApp(),
    ),
  );
}

final _router = GoRouter(
  initialLocation: '/login',
  routes: [
    GoRoute(
      path: '/login',
      builder: (context, state) => const LoginScreen(),
    ),
    GoRoute(
      path: '/home',
      builder: (context, state) => const HomeScreen(),
    ),
    GoRoute(
      path: '/rider',
      builder: (context, state) => const RiderJobFeedScreen(),
    ),
    GoRoute(
      path: '/checkout',
      builder: (context, state) => const CheckoutScreen(),
    ),
  ],
);

class PasslApp extends StatelessWidget {
  const PasslApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'PASSL',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF2196F3)), // Blue
        useMaterial3: true,
        textTheme: GoogleFonts.interTextTheme(),
      ),
      routerConfig: _router,
    );
  }
}
