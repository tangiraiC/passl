from django.db import models
from django.conf import settings

class Shop(models.Model):
    """
    Represents a physical or virtual store.
    Owner is the User who manages this shop.
    Address text is critical for landmark-based navigation.
    """
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shops')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Zimbabwe addressing relies heavily on landmarks
    address_text = models.TextField(help_text="Landmark based address")
    
    # Geolocation for calculating distance to user
    lat = models.FloatField(default=-17.824858) # Default to Harare
    lng = models.FloatField(default=31.053028)
    
    is_open = models.BooleanField(default=True)
    image_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    """
    Item for sale in a Shop.
    """
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)
    image_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.name

class Order(models.Model):
    """
    Central model for the marketplace workflow.
    Tracks lifecycle: Created -> Accepted -> Picked Up -> Delivered.
    """
    class Status(models.TextChoices):
        CREATED = "CREATED", "Created"
        ACCEPTED = "ACCEPTED", "Accepted by Shop"
        READY_FOR_PICKUP = "READY", "Ready for Pickup"
        PICKED_UP = "PICKED_UP", "Picked Up"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    class PaymentMethod(models.TextChoices):
        PAYNOW = "PAYNOW", "Paynow"
        COD = "COD", "Cash on Delivery"

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        REFUNDED = "REFUNDED", "Refunded"

    # Relationships
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='orders')
    # Rider is assigned only after they accept the job
    rider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='deliveries')
    
    # For MVP, storing items as JSON to avoid complexity of OrderItem model.
    # Structure: [{"product_id": 1, "quantity": 2, "price": 10.00}]
    items = models.JSONField(default=list) 
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CREATED)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.COD)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    
    delivery_address = models.TextField()
    # Coordinates where the rider needs to go
    delivery_lat = models.FloatField(blank=True, null=True)
    delivery_lng = models.FloatField(blank=True, null=True)
    
    # 4-6 digit code the customer gives to rider to verify delivery
    delivery_otp = models.CharField(max_length=6, blank=True, null=True, help_text="OTP for delivery confirmation")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.id} - {self.status}"
