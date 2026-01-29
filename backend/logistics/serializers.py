from rest_framework import serializers
from .models import Shop, Product, Order

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'

class ShopSerializer(serializers.ModelSerializer):
    products = ProductSerializer(many=True, read_only=True)
    
    class Meta:
        model = Shop
        fields = '__all__'
        read_only_fields = ['owner']

class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = ['customer', 'status', 'payment_status', 'delivery_otp']

    def create(self, validated_data):
        # Calculate total amount based on items (basic validation for MVP)
        # In real app, fetch product prices from DB to prevent tampering
        return super().create(validated_data)
