from django.db import models

class CoreAbstractModel(models.Model):
    """
    The absolute base record. Inherited by EVERY single entity
    including ledger records (Sales, StockMovements).
    """
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class UpdatableAbstractModel(CoreAbstractModel):
    """
    Inherits is_active and created_at, but adds tracking for updates.
    Inherited by entities that change over time (Products, Categories, Suppliers).
    """
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True