from django.db import models
from .abstracts import UpdatableAbstractModel

class Doctor(UpdatableAbstractModel):
    name = models.CharField(max_length=150)
    image = models.ImageField(upload_to='doctors/', blank=True, null=True)
    license_number = models.CharField(max_length=50, unique=True, blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True)
    clinic_name = models.CharField(max_length=200, blank=True)
    clinic_address = models.CharField(max_length=300, blank=True)

    class Meta:
        db_table = 'doctors'
        ordering = ['name']

    def __str__(self):
        return self.name