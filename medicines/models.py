from django.db import models
from django.contrib.auth.models import AbstractUser
from decimal import Decimal

# Create your models here.

class User(AbstractUser):
    """Custom user model with role-based access"""
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        PHARMACIST = 'pharmacist', 'Pharmacist'
        CASHIER = 'cashier', 'Cashier'
    
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CASHIER
    )
    phone = models.CharField(max_length=20, blank=True)

    class Meta:
        db_table = 'users'

    def is_admin(self):
        return self.role == self.Role.ADMIN
    
    def is_pharmacist(self):
        return self.role == self.Role.PHARMACIST
    
    def is_cashier(self):
        return self.role == self.Role.CASHIER

class Category(models.Model):
    name = models.CharField(max_length=200, unique=True)
    parent = models.ForeignKey(
        'self', # foreign key to ITSELF
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name = 'children' # access subcategories(children) with category.children.all()
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'Categories' # Fix admin pluralization
        ordering = ['name']

    def __str__(self):
        return self.name6
    
class Supplier(models.Model):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=300, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'suppliers'
        ordering = ['name']
    
    def __str__(self):
        return self.name

# ProductType
class ProductType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'product_types'
        ordering = ['name']

    def __str__(self):
        return self.name
    
class Product(models.Model):
    class BaseUnit(models.TextChoices):
        TABLET = 'tablet', 'Tablet'
        CAPSULE = 'capsule', 'Capsule'
        ML = 'ml', 'Milliliter (mL)'
        G = 'g', 'Gram (g)'
        MG = 'mg', 'Milligram (mg)'
        PIECE = 'piece', 'Piece'
        TUBE = 'tube', 'Tube'
        BOTTLE = 'bottle', 'Bottle'

    name = models.CharField(max_length=200)
    product_type = models.ForeignKey(
        'ProductType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )
    base_unit = models.CharField(
        max_length=20,
        choices=BaseUnit.choices,
        default=BaseUnit.TABLET
    )
    category = models.ForeignKey(
        'Category',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )
    suppliers = models.ManyToManyField(
        'Supplier',
        blank=True,
        related_name='products'
    )
    description = models.TextField(blank=True)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.IntegerField(default=0)
    expiration_date = models.DateField(null=True, blank=True)
    requires_prescription = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'products'
        ordering = ['-created_at']

    def __str__(self):
        return self.name
    
    @property
    def is_expired(self):
        from django.utils import timezone
        if self.expiration_date:
            return self.expiration_date < timezone.now().date()
        return False
    
    @property
    def is_low_stock(self):
        return self.stock_quantity < 10

class Sale(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = 'cash', 'Cash'
        CARD = 'card', 'Card'
        INSURANCE = 'insurance', 'Insurance'

    sale_number = models.CharField(max_length=30, unique=True)
    cashier = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='sales'
    )
    prescription = models.ForeignKey(
        'Prescription',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales'
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sales'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.sale_number
    
    def calculate_total(self):
        """Sum total of all items subtotal"""
        return sum(item.subtotal for item in self.items.all())
    
class SaleItem(models.Model):
    sale = models.ForeignKey(
        'Sale', 
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        'Product',
        on_delete=models.SET_NULL,
        null=True,
        related_name='sale_items'
    )
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        db_table = 'sale_items'
    
    def save(self, *args, **kwargs):
        # Calculate subtotal
        self.subtotal = Decimal(self.quantity) * Decimal(self.unit_price)
        
        is_new = self.pk is None
        old_quantity = 0
        
        # Get old quantity if updating
        if not is_new:
            try:
                old_item = SaleItem.objects.get(pk=self.pk)
                old_quantity = old_item.quantity
            except SaleItem.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        # Update product stock (deduct for new, adjust for update)
        if self.product:
            if is_new:
                # New item: deduct stock
                self.product.stock_quantity -= self.quantity
            else:
                # Update: adjust by difference
                quantity_diff = old_quantity - self.quantity
                self.product.stock_quantity += quantity_diff
            
            self.product.save(update_fields=['stock_quantity'])
        
        # Update sale total
        self.sale.total_amount = self.sale.calculate_total()
        self.sale.save(update_fields=['total_amount'])

    def delete(self, *args, **kwargs):
        # Restore stock on delete
        if self.product:
            self.product.stock_quantity += self.quantity
            self.product.save(update_fields=['stock_quantity'])
        
        super().delete(*args, **kwargs)
        
        # Update sale total
        self.sale.total_amount = self.sale.calculate_total()
        self.sale.save(update_fields=['total_amount'])  

    def __str__(self):
        return f"{self.sale.sale_number} - {self.product}"

# === Doctor and Patient ===
class Doctor(models.Model):
    name = models.CharField(max_length=150)
    license_number = models.CharField(max_length=50, unique=True, blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True)
    clinic_name = models.CharField(max_length=200, blank=True)
    clinic_address = models.CharField(max_length=300, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'doctors'
        ordering = ['name']

    def __str__(self):
        return self.name
    
class Patient(models.Model):
    class Gender(models.TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'
        OTHER = 'other', 'Other'

    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        blank=True
    )
    address = models.CharField(max_length=300, blank=True)
    allergy_notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'patients'
        ordering = ['name']

    def __str__(self):
        return self.name
    
    @property
    def age(self):
        """Calculate age from date_of_birth"""
        if self.date_of_birth:
            from django.utils import timezone
            today = timezone.now().date()
            return today.year - self.date_of_birth.year  - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        return None

class Prescription(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        VERIFIED = 'verified', 'Verified'
        DISPENSED = 'dispensed', 'Dispensed'
        REJECTED = 'rejected', 'Rejected'

    prescription_number = models.CharField(max_length=30, unique=True)
    doctor = models.ForeignKey(
        'Doctor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prescriptions'
    )
    patient = models.ForeignKey(
        'Patient',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prescriptions'
    )
    prescription_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    verified_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_prescriptions'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            import datetime
            today = datetime.date.today() 
            count = Prescription.objects.filter(created_at__date=today).count()+1
            self.prescription_number = f"RX-{today.strftime('%Y%m%d')}-{count:04d}"
        return super().save(*args, **kwargs)

    class Meta:
        db_table = 'prescriptions'
        ordering = ['-created_at']

    def __str__(self):
        return self.prescription_number
    
class PrescriptionItem(models.Model):
    prescription = models.ForeignKey(
        'Prescription',
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        'Product',
        on_delete=models.SET_NULL,
        null=True,
        related_name='prescription_items'
    )
    quantity_prescribed = models.PositiveIntegerField()
    dosage_instructions = models.CharField(max_length=200, blank=True)
    is_dispensed = models.BooleanField(default=False)

    class Meta:
        db_table = 'prescription_items'

    def __str__(self):
        product_name = self.product.name if self.product else "Unknown Product"
        return f"{self.prescription.prescription_number} - {product_name}"
    
# === STOCK MOVEMENT ===
class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        # IN 
        PURCHASE = 'purchase', 'Purchase'
        RETURN_CUSTOMER = 'return_customer', 'Return from Customer'
        ADJUSTMENT_IN = 'adjustment_in', 'Adjustment (In)'
        # OUT
        SALE = 'sale', 'Sale'
        EXPIRED = 'expired', 'Expired'
        DAMAGED = 'damaged', 'Damaged'
        RETURN_SUPPLIER = 'return_supplier', 'Return to Supplier'
        ADJUSTMENT_OUT = 'adjustment_out', 'Adjustment (Out)'
    
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='stock_movements'
    )
    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices
    )
    quantity = models.IntegerField()  # positive for int, negative for out
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    reference = models.CharField(max_length=100, blank=True)  # invoice, sale, etc...
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='stock_movements'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'stock_movements'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.movement_type} - {self.product} x {self.quantity}"

    @property
    def is_stock_in(self):
        """Check if this movement increases stock"""
        return self.movement_type in [
            self.MovementType.PURCHASE,
            self.MovementType.RETURN_CUSTOMER,
            self.MovementType.ADJUSTMENT_IN
        ]

    @property
    def is_stock_out(self):
        """Check if this movement decreases stock"""
        return self.movement_type in [
            self.MovementType.SALE,
            self.MovementType.EXPIRED,
            self.MovementType.DAMAGED,
            self.MovementType.RETURN_SUPPLIER,
            self.MovementType.ADJUSTMENT_OUT
        ]
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
    
        # Update product stock on the movement
        if is_new and self.product:
            if self.is_stock_in:
                self.product.stock_quantity += self.quantity
            else:
                self.product.stock_quantity -= self.quantity
            self.product.save(update_fields=['stock_quantity'])
