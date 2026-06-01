import datetime
from decimal import Decimal
from django.db import models, transaction
from django.core.exceptions import ValidationError
from .abstracts import CoreAbstractModel

class Sale(CoreAbstractModel):
    class PaymentMethod(models.TextChoices):
        CASH = 'cash', 'Cash'
        CARD = 'card', 'Card'
        INSURANCE = 'insurance', 'Insurance'

    sale_number = models.CharField(max_length=30, unique=True)
    cashier = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, related_name='sales')
    prescription = models.ForeignKey('Prescription', on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'sales'
        ordering = ['-created_at']

    def __str__(self):
        return self.sale_number

    def calculate_total(self):
        return sum(item.subtotal for item in self.items.all())

    def save(self, *args, **kwargs):
        if not self.pk:
            today = datetime.date.today()
            count = Sale.objects.filter(created_at__date=today).count() + 1
            self.sale_number = f"SL-{today.strftime('%Y%m%d')}-{count:04d}"
        super().save(*args, **kwargs)


class SaleItem(CoreAbstractModel):
    sale = models.ForeignKey('Sale', on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('Product', on_delete=models.SET_NULL, null=True, related_name='sale_items')
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        db_table = 'sale_items'

    def clean(self):
        super().clean()
        if self.product and self.quantity is not None:
            if self.product.stock_quantity < self.quantity:
                raise ValidationError({
                    'quantity': f'Insufficient stock. Available: {self.product.stock_quantity} {self.product.base_unit}(s)'
                })

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("SaleItem cannot be updated. Delete and create a new one instead.")

        self.subtotal = Decimal(self.quantity) * Decimal(self.unit_price)

        with transaction.atomic():
            super().save(*args, **kwargs)

            if self.product:
                from .stock_movement import StockMovement # Import here to prevent circular imports
                
                if self.product.stock_quantity < self.quantity:
                    raise ValidationError({
                        'quantity': f'Insufficient stock for {self.product.name}'
                    })

                StockMovement.objects.create(
                    product=self.product,
                    movement_type=StockMovement.Reason.SALE,
                    quantity=self.quantity,
                    sale=self.sale,
                    sale_item=self,
                    notes=f'Auto-created from Sale #{self.sale.sale_number}',
                    created_by=self.sale.cashier
                )

            self.sale.total_amount = self.sale.calculate_total()
            self.sale.save(update_fields=['total_amount'])

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            if self.product:
                from .stock_movement import StockMovement
                movement = StockMovement.objects.filter(sale_item=self).first()
                if movement:
                    movement.delete()

            sale = self.sale
            super().delete(*args, **kwargs)

            sale.total_amount = sale.calculate_total()
            sale.save(update_fields=['total_amount'])

    def __str__(self):
        return f"{self.sale.sale_number} - {self.product}"