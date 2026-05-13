from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from decimal import Decimal
from django.core.exceptions import ValidationError

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


class CoreModel(models.Model):
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
    
class Supplier(CoreModel):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=300, blank=True)

    class Meta:
        db_table = 'suppliers'
        ordering = ['name']
    
    def __str__(self):
        return self.name

# ProductType
class ProductType(CoreModel):
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

    class Meta:
        db_table = 'producttypes'
        ordering = ['name']

    def __str__(self):
        return self.name
    
class Category(CoreModel):
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
    
    # === Recursive HELPER METHODS ===
    @property
    def full_path(self):
        """Return full hierarchical path: 'Medicine > Cardiovascular > Antihypertensives'"""
        if self.parent:
            return f"{self.parent.full_path} > {self.name}"
        return f"{self.product_type.name} > {self.name}"
    
    @property
    def depth(self):
        """Calculate depth in category tree with circular reference guard."""
        if not self.parent_id:
            return 0
        # Guard against self-reference (parent_id == self.pk)
        if self.parent_id == self.pk:
            return 1  # Or raise error
        return self.parent.depth + 1
    
    def get_ancestors(self):
        """Return list of all parent categories up to root"""
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return ancestors

    def get_descendants(self):
        """Return all nested children recursively"""
        descendants = []
        for child in self.children.all():
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants
    
    def is_ancestor_of(self, category):
        """Check if this category is an ancestor of another"""
        return self in category.get_ancestors()
    
    def is_descendant_of(self, category):
        """Check if this category is a descendant of another"""
        return category in self.get_ancestors()

    # === Custom Validations ===
    def clean(self):
        """Validate category constraints."""
        from django.core.exceptions import ValidationError
        
        # 1. Self-parent check - MUST use parent_id comparison
        if self.parent_id is not None and self.parent_id == self.pk:
            raise ValidationError({'parent': 'Category cannot be its own parent.'})
        
        # 2. Type consistency check
        if self.parent_id:
            # Fetch parent if not already loaded
            parent = self.parent if self.parent_id == getattr(self.parent, 'pk', None) else Category.objects.get(pk=self.parent_id)
            if parent.product_type_id != self.product_type_id:
                raise ValidationError({
                    'parent': f'Parent must belong to same ProductType.'
                })
            
            # 3. Circular reference check (parent is among descendants)
            descendants = self.get_descendants() if self.pk else []
            if parent in descendants:
                raise ValidationError({'parent': 'Circular reference detected.'})
        
        # 4. Depth limit
        if self.depth > 5:
            raise ValidationError({'parent': 'Maximum depth (5) exceeded.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    # === AGGREGATION HELPERS ===

    def get_all_products(self):
        """Returns queryset of all products in this category AND all descendants"""
        from django.db.models import Q
        
        # Start with own products
        category_ids = [self.id]
        
        # Add all descendant category IDs
        for descendant in self.get_descendants():
            category_ids.append(descendant.id)
        
        return Product.objects.filter(category_id__in=category_ids)

    def get_total_stock(self):
        """Returns total stock quantity for this category and all descendants"""
        return self.get_all_products().aggregate(
            total=models.Sum('stock_quantity')
        )['total'] or 0

    def get_total_value(self):
        """Returns total inventory value for this category and all descendants"""
        from django.db.models import F
        return self.get_all_products().aggregate(
            total=models.Sum(models.F('stock_quantity') * models.F('selling_price'))
        )['total'] or 0

    
class Product(CoreModel):
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


class Sale(CoreModel):
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

    class Meta:
        db_table = 'sales'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.sale_number
    
    def calculate_total(self):
        """Sum total of all items subtotal"""
        return sum(item.subtotal for item in self.items.all())

    def save(self, *args, **kwargs):
        # Auto-generate sale number matching Prescription pattern
        if not self.pk:
            import datetime
            today = datetime.date.today()
            count = Sale.objects.filter(created_at__date=today).count() + 1
            self.sale_number = f"SL-{today.strftime('%Y%m%d')}-{count:04d}"
        super().save(*args, **kwargs)
    
class SaleItem(CoreModel):
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
        
        if self.product and self.quantity is not None:
            if self.product.stock_quantity < self.quantity:
                raise ValidationError({
                    'quantity': f'Insufficient stock. Available: {self.product.stock_quantity} {self.product.base_unit}(s)'
                })
    
    def save(self, *args, **kwargs):
        """Save with transaction and auto-create StockMovement"""
        # Calculate subtotal
        self.subtotal = Decimal(self.quantity) * Decimal(self.unit_price)
        
        is_new = self.pk is None
        old_item = None
        
        # Get old quantity if updating
        if not is_new:
            try:
                old_item = SaleItem.objects.get(pk=self.pk)
            except SaleItem.DoesNotExist:
                pass
        
        with transaction.atomic():

            # FIX: If updating, find and delete the old StockMovement to safely reverse stock
            if old_item and old_item.product:
                old_movement = StockMovement.objects.filter(
                    sale_item=self
                ).first()
                if old_movement:
                    old_movement.delete() # StockMovement.delete() now handles reversing the stock

            super().save(*args, **kwargs)
            
            # FIX: Only create the StockMovement. Do NOT manually edit stock_quantity here.
            if self.product:
                if self.product.stock_quantity < self.quantity:
                    raise ValidationError({
                        'quantity': f'Insufficient stock for {self.product.name}'
                    })

                StockMovement.objects.create(
                    product=self.product,
                    movement_type=StockMovement.Reason.SALE,
                    quantity=self.quantity,
                    sale=self.sale,
                    sale_item=self,
                    notes=f'Auto-created from Sale #{self.sale.sale_number}',
                    created_by=self.sale.cashier
                )

            self.sale.total_amount = self.sale.calculate_total()
            self.sale.save(update_fields=['total_amount'])

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            # FIX: Use sale_item field for consistent lookup
            if self.product:
                movement = StockMovement.objects.filter(
                    sale_item=self  # ← Use sale_item, same as in save()
                ).first()
                if movement:
                    movement.delete()

            sale = self.sale
            super().delete(*args, **kwargs)

            sale.total_amount = sale.calculate_total()
            sale.save(update_fields=['total_amount'])

    def __str__(self):
        return f"{self.sale.sale_number} - {self.product}"

# === Doctor and Patient ===
class Doctor(CoreModel):
    name = models.CharField(max_length=150)
    license_number = models.CharField(max_length=50, unique=True, blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True)
    clinic_name = models.CharField(max_length=200, blank=True)
    clinic_address = models.CharField(max_length=300, blank=True)

    class Meta:
        db_table = 'doctors'
        ordering = ['name']

    def __str__(self):
        return self.name
    
class Patient(CoreModel):
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

class Prescription(CoreModel):
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

    def save(self, *args, **kwargs):
        if not self.pk:
            import datetime
            today = datetime.date.today()
            # FIX: Filter by prescription_date instead of created_at to prevent DB timezone edge cases
            count = Prescription.objects.filter(prescription_date=today).count() + 1
            self.prescription_number = f"RX-{today.strftime('%Y%m%d')}-{count:04d}"
        return super().save(*args, **kwargs)

    class Meta:
        db_table = 'prescriptions'
        ordering = ['-created_at']

    def __str__(self):
        return self.prescription_number
    
class PrescriptionItem(CoreModel):
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
class StockMovement(CoreModel):
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
    sale_item = models.ForeignKey(
        'SaleItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
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
                suppliers=supplier,
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
        if self.is_stock_out and self.suppliers:
            raise ValidationError({
                'suppliers': 'Supplier reference should not be set for stock OUT movements.'
            })
        
        # Quantity must be positive
        if self.quantity <= 0:
            raise ValidationError({
                'quantity': 'Quantity must be a positive number.'
            })
    
    def save(self, *args, **kwargs):
        from django.db import transaction
        is_new = self.pk is None
        self.clean()

        with transaction.atomic():
            super().save(*args, **kwargs)

            # Single source of truth for stock updates
            if is_new and self.product:
                change = self.quantity if self.is_stock_in else -self.quantity
                self.product.stock_quantity += change
                self.product.save(update_fields=['stock_quantity'])

    def delete(self, *args, **kwargs):
        # FIX: Conventional Workaround - If an audit log is deleted, reverse the stock change
        if self.product:
            change = self.quantity if self.is_stock_in else -self.quantity
            self.product.stock_quantity -= change  # Reverse the original math
            self.product.save(update_fields=['stock_quantity'])
            
        super().delete(*args, **kwargs)
