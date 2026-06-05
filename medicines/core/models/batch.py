import datetime
import string
import secrets
from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from .abstracts import UpdatableAbstractModel

def generate_batch_number():
    """Generate a unique BAT-YYYYMMDD-XXXX format number."""
    today_str = datetime.date.today().strftime('%Y%m%d')
    chars = string.ascii_uppercase + string.digits
    random_str = ''.join(secrets.choice(chars) for _ in range(4))
    return f"BAT-{today_str}-{random_str}"

class Batch(UpdatableAbstractModel):
    # The Product this batch belongs to
    product = models.ForeignKey(
        'Product',
        on_delete=models.RESTRICT,
        related_name='batches'
    )
    # Unique identifier for this specific lot
    batch_number = models.CharField(max_length=30, unique=True, default=generate_batch_number)
    
    # Current stock available in THIS specific lot
    quantity = models.IntegerField(default=0)
    
    # The specific expiration date for THIS lot
    expiration_date = models.DateField(null=True, blank=True)
    
    # Purchase/Receipt details
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    received_date = models.DateField(default=datetime.date.today)
    supplier = models.ForeignKey(
        'Supplier',
        on_delete=models.RESTRICT,
        null=True, blank=True,
        related_name='batches'
    )

    class Meta:
        db_table = 'batches'
        ordering = ['expiration_date'] # Default to FEFO ordering

    def __str__(self):
        return f"{self.batch_number} ({self.product.name})"

    @property
    def total_stock(self):
        """Sum of all active batches."""
        return sum(b.quantity for b in self.batches.filter(is_active=True))

    @property
    def nearest_expiration(self):
        """Find the soonest expiration date among active batches."""
        active_batches = self.batches.filter(is_active=True, expiration_date__isnull=False).order_by('expiration_date')
        return active_batches.first().expiration_date if active_batches.exists() else None

    @property
    def is_expired(self):
        """Check if ALL active batches are expired."""
        active_batches = self.batches.filter(is_active=True, expiration_date__isnull=False)
        if not active_batches.exists():
            return False
        return all(b.is_expired for b in active_batches)

    @property
    def is_low_stock(self):
        return self.total_stock < 10

    @property
    def effective_requires_prescription(self):
        if not self.product_type:
            return self.requires_prescription
        return self.requires_prescription or self.product_type.requires_prescription

    def clean(self):
        super().clean()
        if self.quantity < 0:
            raise ValidationError({'quantity': 'Batch quantity cannot be negative.'})
        # Removed stock_quantity and expiration validation from here
        if self.product_type and self.product_type.requires_expiration and self.requires_prescription and not self.requires_prescription:
            pass # Logic can be refined if needed

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)