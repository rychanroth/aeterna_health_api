import datetime
from django.db import models
from .abstracts import UpdatableAbstractModel

class Prescription(UpdatableAbstractModel):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        VERIFIED = 'verified', 'Verified'
        DISPENSED = 'dispensed', 'Dispensed'
        REJECTED = 'rejected', 'Rejected'

    prescription_number = models.CharField(max_length=30, unique=True)
    doctor = models.ForeignKey('Doctor', on_delete=models.SET_NULL, null=True, blank=True, related_name='prescriptions')
    patient = models.ForeignKey('Patient', on_delete=models.SET_NULL, null=True, blank=True, related_name='prescriptions')
    prescription_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    verified_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_prescriptions')
    notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            today = datetime.date.today()
            count = Prescription.objects.filter(prescription_date=today).count() + 1
            self.prescription_number = f"RX-{today.strftime('%Y%m%d')}-{count:04d}"
        return super().save(*args, **kwargs)

    class Meta:
        db_table = 'prescriptions'
        ordering = ['-created_at']

    def __str__(self):
        return self.prescription_number


class PrescriptionItem(UpdatableAbstractModel):
    prescription = models.ForeignKey('Prescription', on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('Product', on_delete=models.SET_NULL, null=True, related_name='prescription_items')
    quantity_prescribed = models.PositiveIntegerField()
    dosage_instructions = models.CharField(max_length=200, blank=True)
    is_dispensed = models.BooleanField(default=False)

    class Meta:
        db_table = 'prescription_items'

    def __str__(self):
        product_name = self.product.name if self.product else "Unknown Product"
        return f"{self.prescription.prescription_number} - {product_name}"