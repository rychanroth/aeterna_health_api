from django.db import models
from .abstracts import UpdatableAbstractModel

class Supplier(UpdatableAbstractModel):
    name = models.CharField(max_length=150)
    image = models.ImageField(upload_to='suppliers/', blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=300, blank=True)

    class Meta:
        db_table = 'suppliers'
        ordering = ['name']

    def __str__(self):
        return self.name