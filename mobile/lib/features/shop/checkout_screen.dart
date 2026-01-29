import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:dio/dio.dart';
import 'package:url_launcher/url_launcher.dart'; // For Paynow Webview
import '../../core/api_client.dart';
import '../../core/cart_provider.dart';
import '../../core/auth_provider.dart';

class CheckoutScreen extends StatefulWidget {
  const CheckoutScreen({super.key});

  @override
  State<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends State<CheckoutScreen> {
  String _paymentMethod = 'COD'; // or PAYNOW
  bool _isLoading = false;
  final _addressController = TextEditingController();

  Future<void> _placeOrder() async {
    final cart = context.read<CartProvider>();
    final auth = context.read<AuthProvider>();
    
    // Quick validation
    if (cart.items.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Cart is empty")));
      return;
    }
    if (_addressController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Enter address")));
      return;
    }

    setState(() => _isLoading = true);

    try {
      final dio = context.read<ApiClient>().client;
      // HARDCODED: Shop ID 1 for MVP (in real app, cart would be tied to shop)
      final shopId = 1; 

      final orderData = {
        'shop': shopId,
        'items': cart.items.map((e) => {'product_id': e.productId, 'quantity': e.quantity, 'price': e.price}).toList(),
        'total_amount': cart.totalAmount,
        'payment_method': _paymentMethod,
        'delivery_address': _addressController.text,
      };

      // 1. Create Order
      final response = await dio.post('/orders/', data: orderData);
      final orderId = response.data['id'];

      // 2. Handle Payment
      if (_paymentMethod == 'PAYNOW') {
        await _initiatePaynow(dio, orderId);
      } else {
        _handleSuccess();
      }

    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Error: $e")));
      setState(() => _isLoading = false);
    }
  }

  Future<void> _initiatePaynow(Dio dio, int orderId) async {
    try {
      final res = await dio.post('/orders/$orderId/pay/');
      if (res.data['redirect_url'] != null) {
        final url = Uri.parse(res.data['redirect_url']);
        if (await canLaunchUrl(url)) {
          await launchUrl(url, mode: LaunchMode.externalApplication);
          // In real app, we would poll for status here.
          _handleSuccess(); 
        } else {
          throw "Could not launch payment page";
        }
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Payment Init Error: $e")));
      setState(() => _isLoading = false);
    }
  }

  void _handleSuccess() {
    context.read<CartProvider>().clear();
    setState(() => _isLoading = false);
    
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => AlertDialog(
        title: const Text('Order Placed!'),
        content: const Text('Your order has been received.'),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.of(context).pop(); // Close dialog
              Navigator.of(context).pop(); // Go back to Home
            }, 
            child: const Text('OK')
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final cart = context.watch<CartProvider>();

    return Scaffold(
      appBar: AppBar(title: const Text('Checkout')),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            // Items Summary
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12.0),
                child: Column(
                  children: [
                    Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                      Text('${cart.items.length} Items'),
                      Text('\$${cart.totalAmount.toStringAsFixed(2)}', style: const TextStyle(fontWeight: FontWeight.bold)),
                    ]),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _addressController,
              decoration: const InputDecoration(
                labelText: 'Delivery Address',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.location_on),
              ),
              maxLines: 2,
            ),
            const SizedBox(height: 16),
            const Text("Payment Method", style: TextStyle(fontWeight: FontWeight.bold)),
            RadioListTile(
              title: const Text("Cash on Delivery"),
              value: "COD", 
              groupValue: _paymentMethod, 
              onChanged: (v) => setState(() => _paymentMethod = v.toString())
            ),
            RadioListTile(
              title: const Text("Paynow (EcoCash/OneMoney)"),
              value: "PAYNOW", 
              groupValue: _paymentMethod, 
              onChanged: (v) => setState(() => _paymentMethod = v.toString())
            ),
            const Spacer(),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _isLoading ? null : _placeOrder,
                child: _isLoading ? const CircularProgressIndicator(color: Colors.white) : const Text("Place Order"),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
