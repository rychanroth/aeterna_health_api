from django.db import models
from .abstracts import UpdatableAbstractModel

class ProductType(UpdatableAbstractModel):
    name = models.CharField(max_length=50, unique=True)
    image = models.ImageField(upload_to='product_types/', blank=True, null=True)
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