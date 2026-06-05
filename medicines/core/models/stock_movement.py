import datetime
from django.db import models, transaction
from django.core.exceptions import ValidationError
from .abstracts import UpdatableAbstractModel

class StockMovement(UpdatableAbstractModel):
    class Type(models.TextChoices):
        IN = 'in', 'Stock In'
        OUT  = 'out', 'Stock Out'
        
    class Reason(models.TextChoices):
        PURCHASE = 'purchase', 'Purchase'
        RETURN_CUSTOMER = 'return_customer', 'Return from Customer'
        ADJUSTMENT_IN = 'adjustment_in', 'Adjustment (In)'
        SALE = 'sale', 'Sale'
        EXPIRED = 'expired', 'Expired'
        DAMAGED = 'damaged', 'Damaged'
        RETURN_SUPPLIER = 'return_supplier', 'Return to Supplier'
        ADJUSTMENT_OUT = 'adjustment_out', 'Adjustment (Out)'

        @classmethod
        def get_in_reasons(cls):
            return [cls.PURCHASE, cls.RETURN_CUSTOMER, cls.ADJUSTMENT_IN]

        @classmethod
        def get_out_reasons(cls):
            return [cls.SALE, cls.EXPIRED, cls.DAMAGED, cls.RETURN_SUPPLIER, cls.ADJUSTMENT_OUT]

    # CHANGE: Movement now targets a Batch, not a Product directly
    batch = models.ForeignKey('Batch', on_delete=models.RESTRICT, related_name='stock_movements')
    movement_type = models.CharField(max_length=20, choices=Reason.choices, verbose_name='reason')
    
    supplier = models.ForeignKey('Supplier', on_delete=models.RESTRICT, null=True, blank=True, related_name='stock_movements')
    sale = models.ForeignKey('Sale', on_delete=models.RESTRICT, null=True, blank=True, related_name='stock_movements')
    sale_item = models.ForeignKey('SaleItem', on_delete=models.RESTRICT, null=True, blank=True)
    quantity = models.IntegerField()
    
    # REMOVED: unit_cost (Tracked at Batch level)
    
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, related_name='stock_movements')

    class Meta:
        db_table = 'stock_movements'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.movement_type} - {self.batch} x {self.quantity}"

    @property
    def is_stock_in(self):
        return self.movement_type in [r.value for r in self.Reason.get_in_reasons()]

    @property
    def is_stock_out(self):
        return self.movement_type in [r.value for r in self.Reason.get_out_reasons()]

    @property
    def movement_direction(self):
        return self.Type.IN.value if self.is_stock_in else self.Type.OUT.value

    def clean(self):
        super().clean()
        if self.is_stock_in and self.sale:
            raise ValidationError({'sale': 'Sale reference should not be set for stock IN movements.'})
        if self.is_stock_out and self.supplier:
            raise ValidationError({'supplier': 'Supplier reference should not be set for stock OUT movements.'})
        if self.quantity <= 0:
            raise ValidationError({'quantity': 'Quantity must be a positive number.'})

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("Stock movements are immutable and cannot be updated.")
        
        self.clean()

        with transaction.atomic():
            super().save(*args, **kwargs) # 1. Save the movement record first
            
            # 2. NOW update the live Batch balance
            if self.batch:
                if self.is_stock_in:
                    # IN: ADD to the batch
                    self.batch.quantity += self.quantity
                else: # is_stock_out
                    # OUT: SUBTRACT from the batch
                    self.batch.quantity -= self.quantity
                    
                # This will trigger Batch.clean(), preventing negative stock
                self.batch.save(update_fields=['quantity']) 

    def delete(self, *args, **kwargs):
        raise ValidationError("Stock movements cannot be deleted as they are immutable ledger records.")