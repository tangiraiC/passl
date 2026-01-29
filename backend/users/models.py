from django.contrib.auth.models import AbstractUser
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField

class User(AbstractUser):
    class Roles(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer"
        RIDER = "RIDER", "Rider"
        SHOP_OWNER = "SHOP_OWNER", "Shop Owner"
        ADMIN = "ADMIN", "Admin"

    # Role fields define permissions in the app
    # CUSTOMER: Can buy products
    # RIDER: Can accept delivery jobs
    # SHOP_OWNER: Can manage shops and products
    # ADMIN: Superuser access
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.CUSTOMER)
    
    # Using PhoneNumberField to automaticallly validate Zimbabwe numbers (+263...)
    phone_number = PhoneNumberField(blank=True, null=True, unique=True, region="ZW")
    
    # Rider specific fields (could be in a separate Profile model, but putting here for MVP simplicity)
    # is_available: Toggles rider visibility for job matching
    is_available = models.BooleanField(default=False)
    # vehicle_type: e.g., 'Bike', 'Car', 'Scooter'
    vehicle_type = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
