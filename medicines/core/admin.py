from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Supplier, ProductType, Category, Product, Batch,
    Doctor, Patient, Prescription, PrescriptionItem,
    Sale, SaleItem, StockMovement
)

# ==========================================
# USER ADMIN
# ==========================================
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'first_name', 'last_name', 'role', 'is_active')
    list_filter = ('role', 'is_active')
    
    # 1. Add custom fields to the EDIT user page
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('role', 'phone', 'image')}),
    )
    
    # 2. Add custom fields to the CREATE user page
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'role', 'first_name', 'last_name'),
        }),
    )

# ==========================================
# CORE INVENTORY ADMIN
# ==========================================
@admin.register(ProductType)
class ProductTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'requires_expiration', 'requires_prescription')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'product_type', 'parent')
    list_filter = ('product_type',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'base_unit', 'selling_price', 'requires_prescription', 'is_active')
    list_filter = ('is_active', 'requires_prescription', 'product_type')
    search_fields = ('name',)

@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('batch_number', 'product', 'quantity', 'expiration_date', 'is_active')
    list_filter = ('is_active',)

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone')

# ==========================================
# MEDICAL RECORDS ADMIN
# ==========================================
@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('name', 'license_number', 'phone')

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'gender', 'date_of_birth')
    list_filter = ('gender',)

class PrescriptionItemInline(admin.TabularInline):
    model = PrescriptionItem
    extra = 1

@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ('prescription_number', 'doctor', 'patient', 'status', 'prescription_date')
    list_filter = ('status',)
    inlines = [PrescriptionItemInline]

# ==========================================
# IMMUTABLE LEDGER ADMIN (Read-Only)
# ==========================================
class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ('batch', 'product', 'quantity', 'unit_price', 'subtotal')

    # Prevent adding/deleting items directly from the Sale admin
    def has_add_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('sale_number', 'cashier', 'total_amount', 'payment_method', 'created_at')
    list_filter = ('payment_method',)
    readonly_fields = ('sale_number', 'cashier', 'total_amount', 'payment_method', 'prescription', 'notes', 'created_at')
    inlines = [SaleItemInline]

    # Sales are immutable, prevent editing and deleting
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('batch', 'movement_type', 'quantity', 'created_by', 'created_at')
    list_filter = ('movement_type',)
    readonly_fields = ('batch', 'movement_type', 'quantity', 'supplier', 'sale', 'reference', 'notes', 'created_by', 'created_at')

    # Stock Movements are immutable, prevent adding, editing, and deleting
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False