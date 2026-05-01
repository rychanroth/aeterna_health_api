from . import views
from django.urls import path

urlpatterns = [
    # Medicines
    path('medicines/', views.medicine_list, name='medicine-list'),
    path('medicines/<int:pk>/', views.medicine_detail, name='medicine-detail'),

    # Categories
    path('categories/', views.category_list, name='category-list'),
    path('categories/<int:pk>', views.category_detail, name='category-detail'),

    # Suppliers
    path('suppliers/', views.supplier_list, name='supplier-list'),
    path('suppliers/<int:pk>', views.supplier_detail, name='supplier-detail'),
]