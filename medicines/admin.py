from django.contrib import admin
from .models import *
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'role', 'is_active']
    list_filter = ['role', 'is_active']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('role', 'phone')}),
    )

@admin.register(ProductType)
class ProductTypeAdmin(admin.ModelAdmin):
    list_display = ['image', 'name', 'requires_expiration', 'requires_prescription', 'is_active']
    list_filter = ['is_active', 'requires_expiration', 'requires_prescription']
    search_fields = ['name']

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['image', 'name', 'parent', 'product_type', 'is_active']
    list_filter = ['is_active', 'product_type']
    search_fields = ['name']

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['image', 'name', 'phone', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['image', 'name', 'category', 'selling_price', 'stock_quantity', 'expiration_date', 'is_active']
    list_filter = ['category', 'is_active', 'requires_prescription', 'product_type']
    search_fields = ['name']
    filter_horizontal = ['suppliers']
    readonly_fields = ['is_expired', 'is_low_stock']

@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ['image', 'name', 'license_number', 'phone', 'clinic_name', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'license_number']

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['image', 'name', 'phone', 'gender', 'date_of_birth', 'is_active']
    list_filter = ['is_active', 'gender']
    search_fields = ['name', 'phone']

@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ['prescription_number', 'patient', 'doctor', 'prescription_date', 'status', 'is_active']
    list_filter = ['status', 'is_active', 'prescription_date']
    search_fields = ['prescription_number', 'patient__name']
    readonly_fields = ['prescription_number']

@admin.register(PrescriptionItem)
class PrescriptionItemAdmin(admin.ModelAdmin):
    list_display = ['prescription', 'product', 'quantity_prescribed', 'is_dispensed', 'is_active']
    list_filter = ['is_dispensed', 'is_active']
    search_fields = ['prescription__prescription_number']

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['sale_number', 'cashier', 'total_amount', 'payment_method', 'created_at', 'is_active']
    list_filter = ['created_at', 'payment_method', 'is_active']
    search_fields = ['sale_number']
    readonly_fields = ['sale_number', 'total_amount']

@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ['sale', 'product', 'quantity', 'unit_price', 'subtotal', 'is_active']
    list_filter = ['is_active', 'sale__created_at']
    search_fields = ['sale__sale_number', 'product__name']
    readonly_fields = ['subtotal']

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ['product', 'movement_type', 'quantity', 'movement_direction', 'created_at', 'is_active']
    list_filter = ['movement_type', 'is_active', 'created_at']
    search_fields = ['product__name', 'reference']
    readonly_fields = ['movement_direction', 'is_stock_in', 'is_stock_out']