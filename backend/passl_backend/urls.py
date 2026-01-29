from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from users.views import RegisterView, UserDetailView
from logistics.views import ShopViewSet, ProductViewSet, OrderViewSet

router = DefaultRouter()
router.register(r'shops', ShopViewSet)
router.register(r'products', ProductViewSet)
router.register(r'orders', OrderViewSet, basename='order')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include(router.urls)),
    path('api/v1/auth/register/', RegisterView.as_view(), name='register'),
    path('api/v1/auth/me/', UserDetailView.as_view(), name='user-detail'),
]
