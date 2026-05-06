from . import views
from rest_framework.routers import DefaultRouter
from django.urls import path

router = DefaultRouter()
router.register(r'users', views.UserViewSet, basename='user')
router.register(r'categories', views.CategoryViewSet, basename='category')
router.register(r'suppliers', views.SupplierViewSet, basename='supplier')
router.register(r'product-types', views.ProductTypeViewSet, basename='product-type')
router.register(r'medicines', views.MedicineViewSet, basename='medicine')
router.register(r'sales', views.SaleViewSet, basename='sale')
router.register(r'doctors', views.DoctorViewSet, basename='doctor')
router.register(r'patients', views.PatientViewSet, basename='patient')
router.register(r'prescriptions', views.PrescriptionViewSet, basename='prescription')
router.register(r'stock-movements', views.StockMovementViewSet, basename='stock-movement')

urlpatterns = [
    path('login/', views.login, name="login")
] + router.urls