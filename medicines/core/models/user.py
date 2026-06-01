from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    """Custom user model with role-based access"""
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        PHARMACIST = 'pharmacist', 'Pharmacist'
        CASHIER = 'cashier', 'Cashier'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.ADMIN
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