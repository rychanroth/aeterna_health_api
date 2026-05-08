from django.db import models
from django.contrib.auth.models import AbstractUser
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction

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
    name = models.CharField(max_length=200)
    parent = models.ForeignKey(
        'self', # foreign key to ITSELF
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name = 'children' # access subcategories(children) with category.children.all()
    )
    product_type = models.ForeignKey(
        'ProductType',
        on_delete=models.CASCADE,
        related_name='categories',
        verbose_name='product type'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'Categories' # Fix admin pluralization
        ordering = ['name']
        constraints = [ # Constraint name
            models.UniqueConstraint(
                fields=['name', 'product_type'],
                name='unique_category_per_product_type'
            )
        ] 

    def __str__(self):
        return self.name
    
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
    requires_expiration = models.BooleanField(
        default=True,
        help_text="Products of this type have expiration dates (e.g., Medicine)"
    )
    requires_prescription = models.BooleanField(
        default=False,
        help_text="Product of this type requires a prescription to purchase"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'producttypes'
        ordering = ['name']

    def __str__(self):
        return self.name
    
class Product(models.Model):
    class BaseUnit(models.TextChoices):
        # Medicine - Oral
        TABLET = 'tablet', 'Tablet'
        CAPSULE = 'capsule', 'Capsule'
        SYRUP = 'syrup', 'Syrup'
        
        # Medicine - Liquid/Measurement
        ML = 'ml', 'Milliliter (mL)'
        G = 'g', 'Gram (g)'
        MG = 'mg', 'Milligram (mg)'
        
        # Medicine - Packaging
        VIAL = 'vial', 'Vial'
        AMPOULE = 'ampoule', 'Ampoule'
        TUBE = 'tube', 'Tube'
        BOTTLE = 'bottle', 'Bottle'
        
        # Medical Equipment
        PIECE = 'piece', 'Piece'
        PACK = 'pack', 'Pack'
        ROLL = 'roll', 'Roll'
        BOX = 'box', 'Box'
        SET = 'set', 'Set'
        
        # Baby Care / Skin Care
        DIAPER = 'diaper', 'Diaper'
        WIPES = 'wipes', 'Wipes'
        SACHET = 'sachet', 'Sachet'
        
        # General
        UNIT = 'unit', 'Unit'

        @classmethod
        def get_medicine_units(cls):
            """Units typically used for medicine"""
            return [cls.TABLET, cls.CAPSULE, cls.SYRUP, cls.ML, cls.G, 
                    cls.MG, cls.VIAL, cls.AMPOULE, cls.TUBE, cls.BOTTLE]
        
        @classmethod
        def get_equipment_units(cls):
            """Units typically used for medical equipment"""
            return [cls.PIECE, cls.PACK, cls.ROLL, cls.BOX, cls.SET]
        
        @classmethod
        def get_consumable_units(cls):
            """Units for baby care, skin care, etc."""
            return [cls.DIAPER, cls.WIPES, cls.SACHET, cls.PIECE, cls.PACK]

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
    
    @property
    def effective_requires_prescription(self):
        if not self.product_type:
            return self.requires_prescription
        return self.requires_prescription or self.product_type.requires_prescription

    def clean(self):
        """Validate product fields based on ProductType rules"""
        super().clean()
        
        if self.product_type:
            # Expiration validation
            if self.product_type.requires_expiration and not self.expiration_date:
                raise ValidationError({
                    'expiration_date': f'Expiration date is required for {self.product_type.name} products.'
                })
            
            # Prescription validation - product can override type default
            # (handled at serializer level for better UX)
        
        # Stock quantity validation
        if self.stock_quantity < 0:
            raise ValidationError({
                'stock_quantity': 'Stock quantity cannot be negative.'
            })
    
    def save(self, *args, **kwargs):
        """Run validation before save"""
        self.clean()
        super().save(*args, **kwargs)


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

    def clean(self):
        """Validate stock availability before save"""
        super().clean()
        
        if self.product and self.quantity:
            if self.product.stock_quantity < self.quantity:
                raise ValidationError({
                    'quantity': f'Insufficient stock. Available: {self.product.stock_quantity} {self.product.base_unit}(s)'
                })
    
    def save(self, *args, **kwargs):
        """Save with transaction and auto-create StockMovement"""
        # Calculate subtotal
        self.subtotal = Decimal(self.quantity) * Decimal(self.unit_price)
        
        is_new = self.pk is None
        old_quantity = 0
        old_product = None
        
        # Get old quantity if updating
        if not is_new:
            try:
                old_item = SaleItem.objects.get(pk=self.pk)
                old_quantity = old_item.quantity
                old_product = old_item.product
            except SaleItem.DoesNotExist:
                pass
        
        with transaction.atomic():
            from django.db import transaction
            super().save(*args, **kwargs)
            
            # Update product stock (deduct for new, adjust for update)
            if self.product:
                if is_new:
                    if self.product.stock_quantity < self.quantity:
                        raise ValidationError({
                            f'Insufficient stock for {self.product.name}'
                        })
                    
                    # New item: deduct stock
                    self.product.stock_quantity -= self.quantity
                    self.product.save(update_fields=['stock_quantity'])

                    # Create StockMovement audit record
                    StockMovement.objects.create(
                        product=self.product,
                        movement_type=StockMovement.Reason.SALE,
                        quantity=self.quantity,
                        sale=self.sale,
                        notes=f'Auto-created from Sale #{self.sale.sale_number}',
                        created_by=self.sale.cashier
                    )
                else:
                    # Update: adjust by difference
                    if old_product and old_product != self.product:
                        # Product changed: restore old, deduct new
                        old_product.stock_quantity += old_quantity
                        old_product.save(update_fields=['stock_quantity'])
                        
                        self.product.stock_quantity -= self.quantity
                        self.product.save(update_fields=['stock_quantity'])
                    elif old_quantity != self.quantity:
                        # Same product, quantity changed: adjust difference
                        quantity_diff = old_quantity - self.quantity
                        self.product.stock_quantity += quantity_diff
                        self.product.save(update_fields=['stock_quantity'])
            
            # Update sale total
            self.sale.total_amount = self.sale.calculate_total()
            self.sale.save(update_fields=['total_amount'])

    def delete(self, *args, **kwargs):
        """Delete with transaction and restore stock"""
        from django.db import transaction
        
        with transaction.atomic():
            if self.product:
                self.product.stock_quantity += self.quantity
                self.product.save(update_fields=['stock_quantity'])

            # Store sale reference before deletion
            sale = self.sale
            
            super().delete(*args, **kwargs)
            
            # Update sale total
            sale.total_amount = sale.calculate_total()
            sale.save(update_fields=['total_amount'])  

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
    class Type(models.TextChoices):
        IN = 'in', 'Stock In'
        OUT  = 'out', 'Stock Out'
    class Reason(models.TextChoices):
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

        @classmethod
        def get_in_reasons(cls):
            """Return reasons that result in stock IN"""
            return [cls.PURCHASE, cls.RETURN_CUSTOMER, cls.ADJUSTMENT_IN]
        
        @classmethod
        def get_out_reasons(cls):
            """Return reasons that result in stock OUT"""
            return [cls.SALE, cls.EXPIRED, cls.DAMAGED, cls.RETURN_SUPPLIER, cls.ADJUSTMENT_OUT]
    
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='stock_movements'
    )
    movement_type = models.CharField(
        max_length=20,
        choices=Reason.choices,
        verbose_name='reason'
    )
    suppliers = models.ForeignKey(
        'Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements',
        help_text="For IN movements from Suppliers"
    )
    sale = models.ForeignKey(
        'Sale',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements',
        help_text="For OUT movements from Sales"
    )
    quantity = models.IntegerField() 
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Manual reference for adjustments or other movements..."
    )
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
        return self.movement_type in [r.value for r in self.Reason.get_in_reasons()]

    @property
    def is_stock_out(self):
        """Check if this movement decreases stock"""
        return self.movement_type in [r.value for r in self.Reason.get_out_reasons()]
    
    @property
    def movement_direction(self):
        """Return 'in' or 'out' based on reason"""
        return self.Type.IN.value if self.is_stock_in else self.Type.OUT.value
    
    # === Business Logic Stock Movements ===
    @classmethod
    def create_purchase(cls, product, quantity, supplier, user, unit_cost=None, notes=''):
        """
        Create a purchase stock-in movement.
        Usage: StockMovement.create_purchase(product, 100, supplier, request.user)
        """
        from django.db import transaction
        
        with transaction.atomic():
            movement = cls.objects.create(
                product=product,
                movement_type=cls.Reason.PURCHASE,
                quantity=quantity,
                supplier=supplier,
                unit_cost=unit_cost,
                notes=notes,
                created_by=user
            )
            # Stock update handled in save()
            return movement
    
    @classmethod
    def create_adjustment(cls, product, quantity, user, notes=''):
        """
        Create an adjustment movement.
        Positive quantity = IN, Negative = OUT.
        """
        from django.db import transaction
        
        if quantity >= 0:
            reason = cls.Reason.ADJUSTMENT_IN
        else:
            reason = cls.Reason.ADJUSTMENT_OUT
            quantity = abs(quantity)
        
        with transaction.atomic():
            movement = cls.objects.create(
                product=product,
                movement_type=reason,
                quantity=quantity,
                notes=notes,
                created_by=user
            )
            return movement
        
    # === CLEAN AND SAVE ===
    
    def clean(self):
        """Validate FK fields match movement type"""
        super().clean()
        
        # IN movements should have supplier 
        if self.is_stock_in and self.sale:
            raise ValidationError({
                'sale': 'Sale reference should not be set for stock IN movements.'
            })
        
        # OUT movements should have sale or manual reference
        if self.is_stock_out and self.supplier:
            raise ValidationError({
                'supplier': 'Supplier reference should not be set for stock OUT movements.'
            })
        
        # Quantity must be positive
        if self.quantity <= 0:
            raise ValidationError({
                'quantity': 'Quantity must be a positive number.'
            })
    
    def save(self, *args, **kwargs):
        from django.db import transaction
        self.clean()
        super().save(*args, **kwargs)
