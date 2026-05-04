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


class Medicine(models.Model):
    name = models.CharField(max_length=200)
    suppliers = models.ManyToManyField(
        Supplier,
        blank=True,
        related_name='medicines'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='medicines'
    )
    description = models.TextField(blank=True)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.IntegerField(default=0)
    expiration_date = models.DateField(null=True, blank=True)
    requires_prescription = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'medicines'
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

    sale_number = models.CharField(max_length=30, unique=True) # TODO: Implement auto number id generation
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
    
    def save(self, *args, **kwargs):
        if not self.sale_number:
            # Generate sales number
            import datetime
            today = datetime.date.today()
            count = Sale.objects.filter(created_at__date=today).count()+1
            self.sale_number = f"INV-{today.strftime('%Y%m%d')}-{count:04d}"
        return super().save(*args, **kwargs)
    
    def calculate_total(self):
        """Sum total of all items subtotal"""
        return sum(item.subtotal for item in self.items.all())
    
class SaleItem(models.Model):
    sale = models.ForeignKey(
        'Sale', 
        on_delete=models.CASCADE,
        related_name='items'
    )
    medicine = models.ForeignKey(
        'Medicine',
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
        # Auto-fill price from Medicine if not provided
        if not self.unit_price and self.medicine:
            self.unit_price =  self.medicine.selling_price

        # Double type handling
        if self.quantity and self.unit_price:
            self.subtotal = Decimal(str(self.quantity)) * Decimal(str(self.unit_price))

        # Stock management logic
        if not self.pk:
            if self.medicine and self.medicine.stock_quantity >= self.quantity:
                self.medicine.stock_quantity -= self.quantity
                self.medicine.save()
            else:
                raise ValueError("Not enough stock available!")
        super().save(*args, **kwargs)
            
        # Update total_amount field in Sale
        self.sale.total_amount = self.sale.calculate_total()
        self.sale.save(update_fields=['total_amount'])    

    def __str__(self):
        return f"{self.sale.sale_number} - {self.medicine}"


class Prescription(models.Model):
    prescription_number = models.CharField(max_length=30) # TODO: Implement auto number id generation
    doctor = models.ForeignKey(
        'Doctor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prescriptions'
    )

    class Meta:
        db_table = 'prescriptions'

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