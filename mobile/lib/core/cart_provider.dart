import 'package:flutter/material.dart';

class CartItem {
  final int productId;
  final String name;
  final double price;
  int quantity;

  CartItem({required this.productId, required this.name, required this.price, this.quantity = 1});
  
  double get total => price * quantity;
}

class CartProvider extends ChangeNotifier {
  final List<CartItem> _items = [];

  List<CartItem> get items => _items;

  double get totalAmount => _items.fold(0, (sum, item) => sum + item.total);

  void addItem(int productId, String name, double price) {
    final index = _items.indexWhere((item) => item.productId == productId);
    if (index >= 0) {
      _items[index].quantity++;
    } else {
      _items.add(CartItem(productId: productId, name: name, price: price));
    }
    notifyListeners();
  }

  void clear() {
    _items.clear();
    notifyListeners();
  }
}
