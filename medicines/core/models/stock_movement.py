from django.db import models, transaction
from django.core.exceptions import ValidationError
from .abstracts import CoreAbstractModel

class StockMovement(CoreAbstractModel):
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

    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='stock_movements')
    movement_type = models.CharField(max_length=20, choices=Reason.choices, verbose_name='reason')
    suppliers = models.ForeignKey('Supplier', on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_movements', help_text="For IN movements from Suppliers")
    sale = models.ForeignKey('Sale', on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_movements', help_text="For OUT movements from Sales")
    sale_item = models.ForeignKey('SaleItem', on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.IntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    reference = models.CharField(max_length=100, blank=True, help_text="Manual reference for adjustments or other movements...")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, related_name='stock_movements')

    class Meta:
        db_table = 'stock_movements'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.movement_type} - {self.product} x {self.quantity}"

    @property
    def is_stock_in(self):
        return self.movement_type in [r.value for r in self.Reason.get_in_reasons()]

    @property
    def is_stock_out(self):
        return self.movement_type in [r.value for r in self.Reason.get_out_reasons()]

    @property
    def movement_direction(self):
        return self.Type.IN.value if self.is_stock_in else self.Type.OUT.value

    @classmethod
    def create_purchase(cls, product, quantity, supplier, user, unit_cost=None, notes=''):
        with transaction.atomic():
            movement = cls.objects.create(
                product=product,
                movement_type=cls.Reason.PURCHASE,
                quantity=quantity,
                suppliers=supplier,
                unit_cost=unit_cost,
                notes=notes,
                created_by=user
            )
            return movement

    @classmethod
    def create_adjustment(cls, product, quantity, user, notes=''):
        if quantity >= 0:
            reason = cls.Reason.ADJUSTMENT_IN
        else:
            reason = cls.Reason.ADJUSTMENT_OUT
            quantity = abs(quantity)

        with transaction.atomic():
            movement = cls.objects.create(
                product=product,
                movement_type=reason,
                quantity=quantity,
                notes=notes,
                created_by=user
            )
            return movement

    def clean(self):
        super().clean()
        if self.is_stock_in and self.sale:
            raise ValidationError({'sale': 'Sale reference should not be set for stock IN movements.'})
        if self.is_stock_out and self.suppliers:
            raise ValidationError({'suppliers': 'Supplier reference should not be set for stock OUT movements.'})
        if self.quantity <= 0:
            raise ValidationError({'quantity': 'Quantity must be a positive number.'})

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        self.clean()

        with transaction.atomic():
            super().save(*args, **kwargs)

            if is_new and self.product:
                change = self.quantity if self.is_stock_in else -self.quantity
                self.product.stock_quantity += change
                self.product.save(update_fields=['stock_quantity'])

    def delete(self, *args, **kwargs):
        if self.product:
            change = self.quantity if self.is_stock_in else -self.quantity
            self.product.stock_quantity -= change
            self.product.save(update_fields=['stock_quantity'])
        super().delete(*args, **kwargs)