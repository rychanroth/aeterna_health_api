from django.db import models
from django.contrib.auth.models import AbstractUser

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
