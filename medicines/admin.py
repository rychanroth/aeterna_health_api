from django.contrib import admin
from .models import *
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
# Register your models here.

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'role', 'is_active']
    list_filter = ['role', 'is_active']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('role', 'phone')}),
    )

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name']

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name']

@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'selling_price', 'stock_quantity', 'expiration_date', 'is_active']
    list_filter = ['category', 'is_active', 'requires_prescription']
    search_fields = ['name']
    filter_horizontal = ['suppliers']

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['sale_number', 'medicine', 'quantity', 'total_price', 'cashier', 'created_at']
    list_filter = ['created_at', 'cashier']
    search_fields = ['sale_number']
    readonly_fields = ['sale_number', 'total_price']