import 'package:flutter/material.dart';
import 'package:dio/dio.dart';
import 'package:provider/provider.dart';
import '../../core/api_client.dart';

class ShopListScreen extends StatefulWidget {
  const ShopListScreen({super.key});

  @override
  State<ShopListScreen> createState() => _ShopListScreenState();
}

class _ShopListScreenState extends State<ShopListScreen> {
  late Future<List<dynamic>> _shopsFuture;

  @override
  void initState() {
    super.initState();
    _shopsFuture = _fetchShops();
  }

  Future<List<dynamic>> _fetchShops() async {
    try {
      final dio = context.read<ApiClient>().client;
      final response = await dio.get('/shops/');
      return response.data;
    } catch (e) {
      // Return empty list on error for MVP stability
      print("Error fetching shops: $e");
      return [];
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<dynamic>>(
      future: _shopsFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }
        
        final shops = snapshot.data ?? [];
        if (shops.isEmpty) {
          return const Center(child: Text('No shops found or API error.'));
        }

        return ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: shops.length,
          itemBuilder: (context, index) {
            final shop = shops[index];
            return Card(
              margin: const EdgeInsets.only(bottom: 16),
              clipBehavior: Clip.antiAlias,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    height: 150,
                    color: Colors.grey[300],
                    child: shop['image_url'] != null 
                        ? Image.network(shop['image_url'], fit: BoxFit.cover, width: double.infinity)
                        : Center(child: Icon(Icons.store, size: 48, color: Colors.grey[600])),
                  ),
                  Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          shop['name'] ?? 'Unknown Shop',
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          shop['address_text'] ?? 'No address',
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey[600]),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }
}

