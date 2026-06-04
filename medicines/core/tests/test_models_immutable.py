"""
Test Suite: Immutable Model Constraints Enforcement
===================================================

Validates that Sale, SaleItem, and StockMovement enforce immutability.
Replaces the mutable delete/update tests from the original test_sale_transaction.py.

Business Rules Under Test:
--------------------------
1. Sale.delete() raises ValidationError (audit trail integrity)
2. SaleItem.save() on existing instance raises ValidationError
3. SaleItem.delete() raises ValidationError (audit trail integrity)
4. StockMovement.save() on existing instance raises ValidationError
5. StockMovement.delete() raises ValidationError (audit trail integrity)
6. Creation flows still trigger side effects correctly (movements, stock updates)
7. FK constraints on StockMovement types remain enforced
"""

from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from medicines.core.models import (
    Sale, SaleItem, StockMovement, Supplier
)
from .helpers import *

User = get_user_model()


class ImmutableModelsTestCase(TestCase):
    """Test suite for immutable model constraints."""

    def setUp(self):
        """Create test prerequisites."""
        self.cashier = User.objects.create_user(
            username='immutable_cashier',
            password='testpass123',
            is_staff=True
        )
        self.product_a = create_product_with_stock(
            name='Immutable Product A',
            stock_quantity=100,
            created_by=self.cashier
        )

    # =========================================================================
    # GROUP 1: Sale Immutability
    # =========================================================================

    def test_sale_can_be_created(self):
        """Verify Sale creation still works."""
        sale = Sale.objects.create(cashier=self.cashier)
        self.assertIsNotNone(sale.pk)
        self.assertTrue(sale.sale_number.startswith('SL-'))

    def test_sale_cannot_be_deleted(self):
        """Verify Sale.delete() raises ValidationError to protect audit trail."""
        sale = Sale.objects.create(cashier=self.cashier)
        
        with self.assertRaises(ValidationError) as context:
            sale.delete()
            
        self.assertIn('immutable audit records', str(context.exception))

    # =========================================================================
    # GROUP 2: SaleItem Immutability
    # =========================================================================

    def test_sale_item_create_auto_movement(self):
        """Verify SaleItem creation still auto-creates StockMovement."""
        sale = Sale.objects.create(cashier=self.cashier)
        
        SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=10,
            unit_price=self.product_a.selling_price
        )

        movement = StockMovement.objects.filter(
            product=self.product_a,
            sale=sale,
            movement_type=StockMovement.Reason.SALE
        ).first()

        self.assertIsNotNone(movement, "StockMovement should be auto-created")
        self.assertEqual(movement.quantity, 10)

    def test_sale_item_create_updates_total(self):
        """Verify SaleItem creation still updates Sale.total_amount."""
        sale = Sale.objects.create(cashier=self.cashier)
        
        SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=10,
            unit_price=Decimal('10.00')
        )

        sale.refresh_from_db()
        self.assertEqual(sale.total_amount, Decimal('100.00'))

    def test_sale_item_cannot_be_updated(self):
        """Verify SaleItem.save() on existing pk raises ValidationError."""
        sale = Sale.objects.create(cashier=self.cashier)
        item = SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=5,
            unit_price=Decimal('10.00')
        )

        with self.assertRaises(ValidationError) as context:
            item.quantity = 10
            item.save()

        self.assertIn('cannot be updated', str(context.exception))

    def test_sale_item_cannot_be_deleted(self):
        """Verify SaleItem.delete() raises ValidationError to protect audit trail."""
        sale = Sale.objects.create(cashier=self.cashier)
        item = SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=5,
            unit_price=Decimal('10.00')
        )

        with self.assertRaises(ValidationError) as context:
            item.delete()

        self.assertIn('immutable audit records', str(context.exception))

    # =========================================================================
    # GROUP 3: StockMovement Immutability
    # =========================================================================

    def test_stock_movement_create_updates_stock(self):
        """Verify StockMovement creation still updates Product.stock_quantity."""
        initial_stock = self.product_a.stock_quantity
        
        movement = StockMovement.objects.create(
            product=self.product_a,
            movement_type=StockMovement.Reason.PURCHASE,
            quantity=50,
            supplier=Supplier.objects.first(), # From helper
            created_by=self.cashier
        )

        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, initial_stock + 50)

    def test_stock_movement_cannot_be_updated(self):
        """Verify StockMovement.save() on existing pk raises ValidationError."""
        movement = StockMovement.objects.first() # Fetched from setUp product creation
        
        with self.assertRaises(ValidationError) as context:
            movement.quantity = 999
            movement.save()

        self.assertIn('immutable and cannot be updated', str(context.exception))

    def test_stock_movement_cannot_be_deleted(self):
        """Verify StockMovement.delete() raises ValidationError to protect ledger."""
        movement = StockMovement.objects.first()
        
        with self.assertRaises(ValidationError) as context:
            movement.delete()

        self.assertIn('immutable ledger records', str(context.exception))

    # =========================================================================
    # GROUP 4: FK Constraint Validation (Carried over from original)
    # =========================================================================

    def test_stock_in_cannot_have_sale_fk(self):
        """Verify IN movement with sale FK raises ValidationError."""
        sale = Sale.objects.create(cashier=self.cashier)

        with self.assertRaises(ValidationError) as context:
            StockMovement.objects.create(
                product=self.product_a,
                movement_type=StockMovement.Reason.PURCHASE,
                quantity=50,
                sale=sale,
                created_by=self.cashier
            )

        error_dict = context.exception.message_dict
        self.assertIn('sale', error_dict)

    def test_stock_out_cannot_have_supplier_fk(self):
        """Verify OUT movement with supplier FK raises ValidationError."""
        with self.assertRaises(ValidationError) as context:
            StockMovement.objects.create(
                product=self.product_a,
                movement_type=StockMovement.Reason.DAMAGED,
                quantity=10,
                supplier=Supplier.objects.first(),
                created_by=self.cashier
            )

        error_dict = context.exception.message_dict
        self.assertIn('supplier', error_dict)

    def test_stock_movement_quantity_must_be_positive(self):
        """Verify StockMovement with zero quantity raises ValidationError."""
        with self.assertRaises(ValidationError) as context:
            StockMovement.objects.create(
                product=self.product_a,
                movement_type=StockMovement.Reason.PURCHASE,
                quantity=0,
                supplier=Supplier.objects.first(),
                created_by=self.cashier
            )

        error_dict = context.exception.message_dict
        self.assertIn('quantity', error_dict)