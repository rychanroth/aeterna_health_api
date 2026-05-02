from . import views
from rest_framework.routers import DefaultRouter
from django.urls import path

router = DefaultRouter()
router.register(r'categories', views.CategoryViewSet, basename='category')
router.register(r'suppliers', views.SupplierViewSet, basename='supplier')
router.register(r'medicines', views.MedicineViewSet, basename='medicine')

urlpatterns = [
    path('login/', views.login, name="login")
] + router.urls