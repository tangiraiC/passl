from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Shop, Product, Order
from .serializers import ShopSerializer, ProductSerializer, OrderSerializer

class IsShopOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.owner == request.user

class ShopViewSet(viewsets.ModelViewSet):
    """
    Standard ViewSet for Shops.
    - Public: List/Retrieve
    - Owner: Create/Update/Delete
    """
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsShopOwnerOrReadOnly]

    def perform_create(self, serializer):
        # Automatically assign the creator as owner
        serializer.save(owner=self.request.user)

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class OrderViewSet(viewsets.ModelViewSet):
    """
    Handles Order creation and status management.
    Restricts querysets based on user role (Customer vs Shop vs Rider).
    """
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Filter orders by role:
        - Customer: See only their own orders
        - Shop Owner: See orders for their shops
        - Rider: See jobs assigned to them OR accepted orders available for pickup
        """
        user = self.request.user
        if user.role == "CUSTOMER":
            return Order.objects.filter(customer=user)
        elif user.role == "SHOP_OWNER":
            return Order.objects.filter(shop__owner=user)
        elif user.role == "RIDER":
            return Order.objects.filter(rider=user) | Order.objects.filter(status=Order.Status.ACCEPTED) # Riders see accepted orders to pick up
        return Order.objects.none()

    def perform_create(self, serializer):
        serializer.save(customer=self.request.user)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        """
        Initiate Paynow payment for this order.
        """
        order = self.get_object()
        if order.payment_status == Order.PaymentStatus.PAID:
            return Response({"error": "Already paid"}, status=status.HTTP_400_BAD_REQUEST)

        # In a real app, get email from user profile or request
        email = request.user.email or "customer@passl.app"
        
        from .paynow_service import PaynowService
        service = PaynowService()
        result = service.initiate_payment(order, email)
        
        if result['success']:
            # Store poll URL if needed (omitted for MVP simplicity, usually stored in DB)
            return Response(result)
        else:
            return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """
        Shop owner action to accept an incoming order.
        """
        order = self.get_object()
        # Only shop owner
        if order.shop.owner != request.user:
            return Response({"error": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)
        order.status = Order.Status.ACCEPTED
        order.save()
        return Response({"status": "Order Accepted"})
