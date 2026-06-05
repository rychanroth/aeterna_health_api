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
    product = models.ForeignKey(
        'Product',
        on_delete=models.RESTRICT,
        related_name='batches'
    )
    batch_number = models.CharField(max_length=30, unique=True, default=generate_batch_number)
    quantity = models.IntegerField(default=0)
    expiration_date = models.DateField(null=True, blank=True)
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
        ordering = ['expiration_date']

    def __str__(self):
        return f"{self.batch_number} ({self.product.name})"

    @property
    def is_expired(self):
        """Check if THIS specific batch is expired."""
        if not self.expiration_date:
            return False
        return self.expiration_date < datetime.date.today()

    def clean(self):
        super().clean()
        if self.quantity < 0:
            raise ValidationError({'quantity': 'Batch quantity cannot be negative.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)