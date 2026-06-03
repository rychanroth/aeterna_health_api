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
        # CONSTRAINT ENFORCEMENT: Cannot update a sale audit trail
        if self.pk is not None:
            raise ValidationError("Sales are immutable audit trails and cannot be updated. Please void and create a new one if correction is needed.")
        
        # Auto-generate sale number on creation
        if not self.pk:
            today = datetime.date.today()
            count = Sale.objects.filter(created_at__date=today).count() + 1
            self.sale_number = f"SL-{today.strftime('%Y%m%d')}-{count:04d}"
            
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # CONSTRAINT ENFORCEMENT: Cannot delete a sale audit trail
        raise ValidationError("Sales cannot be deleted as they are immutable audit records.")


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
        # CONSTRAINT ENFORCEMENT: Cannot update a sale item audit trail
        if self.pk is not None:
            raise ValidationError("Sale items cannot be updated. Please void the sale and create a new one if correction is needed.")

        self.subtotal = Decimal(self.quantity) * Decimal(self.unit_price)

        with transaction.atomic():
            super().save(*args, **kwargs)

            if self.product:
                from .stock_movement import StockMovement # Prevent circular import
                
                # Re-fetch product inside transaction to lock it and ensure stock hasn't changed
                self.product.refresh_from_db()
                if self.product.stock_quantity < self.quantity:
                    raise ValidationError({
                        'quantity': f'Insufficient stock for {self.product.name}'
                    })

                # Automatically create the immutable Stock Movement ledger entry
                StockMovement.objects.create(
                    product=self.product,
                    movement_type=StockMovement.Reason.SALE,
                    quantity=self.quantity,
                    sale=self.sale,
                    sale_item=self,
                    notes=f'Auto-created from Sale #{self.sale.sale_number}',
                    created_by=self.sale.cashier
                )

            # Recalculate and update the parent Sale total
            self.sale.total_amount = self.sale.calculate_total()
            # Bypass the Sale.save() update constraint for internal calculation updates
            Sale.objects.filter(pk=self.sale.pk).update(total_amount=self.sale.total_amount)

    def delete(self, *args, **kwargs):
        # CONSTRAINT ENFORCEMENT: Cannot delete a sale item audit trail
        # This also prevents orphaning the immutable StockMovement records
        raise ValidationError("Sale items cannot be deleted as they are immutable audit records.")

    def __str__(self):
        return f"{self.sale.sale_number} - {self.product}"