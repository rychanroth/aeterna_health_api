"""
Test Suite: Sale → SaleItem → StockMovement Transactional Flow
==============================================================

Business Rules Under Test:
--------------------------
1. SaleItem.save() auto-creates StockMovement (type=SALE)
2. StockMovement.save() updates Product.stock_quantity
3. SaleItem.delete() restores stock via StockMovement.delete()
4. Validation: Insufficient stock rejection
5. Validation: FK constraints on StockMovement types
6. Transaction atomicity on failures
7. Multi-item sale calculations

Usage:
    python manage.py test medicines.tests.test_sale_transaction -v 2

Note: Follows patterns from test_category_recursion.py
"""

from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from medicines.models import (
    ProductType, Category, Supplier, Product,
    Sale, SaleItem, StockMovement
)


User = get_user_model()


class SaleTransactionTestCase(TestCase):
    """
    Test suite for Sale → SaleItem → StockMovement flow.
    
    Consistent with test_category_recursion.py patterns:
    - Uses Equipment type (no expiration required) for simple tests
    - Uses Medicine type with expiration_date when needed
    """
    
    def setUp(self):
        """Create test prerequisites matching first test suite patterns."""
        today = date.today()
        
        # Create cashier user
        self.cashier = User.objects.create_user(
            username='test_cashier',
            password='testpass123',
            is_staff=True
        )
        
        # === ProductTypes (matching test_category_recursion.py) ===
        self.medicine = ProductType.objects.create(
            name='Medicine',
            requires_expiration=True,
            requires_prescription=True
        )
        self.equipment = ProductType.objects.create(
            name='Equipment',
            requires_expiration=False,
            requires_prescription=False
        )
        
        # === Categories ===
        self.medicine_category = Category.objects.create(
            name='Test Medicine Category',
            product_type=self.medicine
        )
        self.equipment_category = Category.objects.create(
            name='Test Equipment Category',
            product_type=self.equipment
        )
        
        # === Supplier ===
        self.supplier = Supplier.objects.create(
            name='Test Supplier',
            phone='+1-555-0000'
        )
        
        # === Products ===
        # Product A: Equipment type (no expiration needed for simple tests)
        self.product_a = Product.objects.create(
            name='Test Product A',
            product_type=self.equipment,
            category=self.equipment_category,
            base_unit='piece',
            selling_price=Decimal('10.00'),
            stock_quantity=0  # Will be set via StockMovement
        )
        self.product_a.suppliers.add(self.supplier)
        
        # Create initial stock via PURCHASE movement
        self.initial_movement = StockMovement.objects.create(
            product=self.product_a,
            movement_type=StockMovement.Reason.PURCHASE,
            quantity=100,
            suppliers=self.supplier,
            unit_cost=Decimal('6.00'),
            created_by=self.cashier
        )
        
        self.product_a.refresh_from_db()
        self.initial_stock = self.product_a.stock_quantity  # Should be 100
    
    def _create_product(self, name, selling_price=Decimal('10.00'), stock_quantity=100, 
                        product_type=None, with_expiration=False):
        """
        Helper to create additional test products.
        
        Args:
            name: Product name
            selling_price: Price per unit
            stock_quantity: Initial stock (added via StockMovement)
            product_type: ProductType instance (default: equipment)
            with_expiration: If True, adds expiration_date for Medicine type
        """
        today = date.today()
        
        if product_type is None:
            product_type = self.equipment
        
        category = self.equipment_category
        expiration_date = None
        
        if product_type == self.medicine:
            category = self.medicine_category
            if with_expiration or product_type.requires_expiration:
                expiration_date = today + timedelta(days=365)
        
        product = Product.objects.create(
            name=name,
            product_type=product_type,
            category=category,
            base_unit='piece',
            selling_price=selling_price,
            stock_quantity=0,
            expiration_date=expiration_date
        )
        product.suppliers.add(self.supplier)
        
        # Add stock via movement (proper business flow)
        if stock_quantity > 0:
            StockMovement.objects.create(
                product=product,
                movement_type=StockMovement.Reason.PURCHASE,
                quantity=stock_quantity,
                suppliers=self.supplier,
                created_by=self.cashier
            )
            product.refresh_from_db()
        
        return product
    
    # =========================================================================
    # GROUP 1: Happy Path - Sale Item Creation
    # =========================================================================
    
    def test_sale_item_creates_stock_movement(self):
        """Verify SaleItem creation auto-generates StockMovement with type=SALE."""
        sale = Sale.objects.create(
            cashier=self.cashier,
            payment_method=Sale.PaymentMethod.CASH
        )
        
        sale_item = SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=10,
            unit_price=self.product_a.selling_price
        )
        
        # Verify StockMovement was created
        movement = StockMovement.objects.filter(
            product=self.product_a,
            sale=sale,
            movement_type=StockMovement.Reason.SALE
        ).first()
        
        self.assertIsNotNone(movement, "StockMovement should be auto-created")
        self.assertEqual(movement.quantity, 10)
        self.assertEqual(movement.movement_type, StockMovement.Reason.SALE)
    
    def test_sale_item_deducts_stock(self):
        """Verify stock is deducted from Product after SaleItem creation."""
        initial_stock = self.product_a.stock_quantity
        
        sale = Sale.objects.create(cashier=self.cashier)
        
        SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=15,
            unit_price=self.product_a.selling_price
        )
        
        self.product_a.refresh_from_db()
        
        self.assertEqual(
            self.product_a.stock_quantity,
            initial_stock - 15,
            f"Stock should be {initial_stock - 15}"
        )
    
    def test_sale_total_updated(self):
        """Verify sale.total_amount is updated after SaleItem creation."""
        sale = Sale.objects.create(cashier=self.cashier)
        
        SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=10,
            unit_price=Decimal('10.00')
        )
        
        sale.refresh_from_db()
        
        expected_total = Decimal('100.00')
        self.assertEqual(sale.total_amount, expected_total)
    
    # =========================================================================
    # GROUP 2: Stock Restoration on Delete
    # =========================================================================
    
    def test_delete_sale_item_restores_stock(self):
        """Verify deleting SaleItem restores stock and removes StockMovement."""
        initial_stock = self.product_a.stock_quantity
        
        sale = Sale.objects.create(cashier=self.cashier)
        sale_item = SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=20,
            unit_price=self.product_a.selling_price
        )
        
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, initial_stock - 20)
        
        sale_item.delete()
        
        self.product_a.refresh_from_db()
        self.assertEqual(
            self.product_a.stock_quantity,
            initial_stock,
            f"Stock should be restored to {initial_stock}"
        )
        
        movement_count = StockMovement.objects.filter(
            sale=sale,
            product=self.product_a,
            movement_type=StockMovement.Reason.SALE
        ).count()
        
        self.assertEqual(movement_count, 0, "StockMovement should be deleted")
    
    def test_delete_sale_item_updates_sale_total(self):
        """Verify sale.total_amount is recalculated after SaleItem deletion."""
        sale = Sale.objects.create(cashier=self.cashier)
        
        item1 = SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=10,
            unit_price=Decimal('10.00')
        )
        
        product2 = self._create_product('Test Product B', Decimal('5.00'), 50)
        
        SaleItem.objects.create(
            sale=sale,
            product=product2,
            quantity=5,
            unit_price=Decimal('5.00')
        )
        
        sale.refresh_from_db()
        self.assertEqual(sale.total_amount, Decimal('125.00'))
        
        item1.delete()
        
        sale.refresh_from_db()
        self.assertEqual(sale.total_amount, Decimal('25.00'))
    
    # =========================================================================
    # GROUP 3: SaleItem Update Flow
    # =========================================================================
    
    def test_update_sale_item_replaces_stock_movement(self):
        """Verify updating SaleItem deletes old StockMovement and creates new one."""
        initial_stock = self.product_a.stock_quantity
        
        sale = Sale.objects.create(cashier=self.cashier)
        sale_item = SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=5,
            unit_price=self.product_a.selling_price
        )
        
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, initial_stock - 5)
        
        sale_item.quantity = 3
        sale_item.save()
        
        self.product_a.refresh_from_db()
        self.assertEqual(
            self.product_a.stock_quantity,
            initial_stock - 3,
            "Stock should be initial - 3 (not initial - 5 - 3)"
        )
        
        movement_count = StockMovement.objects.filter(
            sale=sale,
            product=self.product_a,
            movement_type=StockMovement.Reason.SALE
        ).count()
        
        self.assertEqual(movement_count, 1, "Should have exactly one StockMovement")
    
    def test_update_sale_item_corrects_subtotal(self):
        """Verify subtotal is recalculated when quantity changes."""
        sale = Sale.objects.create(cashier=self.cashier)
        sale_item = SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=10,
            unit_price=Decimal('10.00')
        )
        
        sale_item.refresh_from_db()
        self.assertEqual(sale_item.subtotal, Decimal('100.00'))
        
        sale_item.quantity = 5
        sale_item.save()
        
        sale_item.refresh_from_db()
        self.assertEqual(sale_item.subtotal, Decimal('50.00'))
        
        sale.refresh_from_db()
        self.assertEqual(sale.total_amount, Decimal('50.00'))
    
    # =========================================================================
    # GROUP 4: Insufficient Stock Rejection
    # =========================================================================
    
    def test_insufficient_stock_raises_validation_error(self):
        """Verify ValidationError when trying to sell more than available stock."""
        self.product_a.stock_quantity = 10
        self.product_a.save()
        
        sale = Sale.objects.create(cashier=self.cashier)
        
        with self.assertRaises(ValidationError) as context:
            SaleItem.objects.create(
                sale=sale,
                product=self.product_a,
                quantity=15,
                unit_price=self.product_a.selling_price
            )
        
        error_dict = context.exception.message_dict
        self.assertIn('quantity', error_dict)
    
    def test_insufficient_stock_no_movement_created(self):
        """Verify no StockMovement created when stock validation fails."""
        self.product_a.stock_quantity = 5
        self.product_a.save()
        
        sale = Sale.objects.create(cashier=self.cashier)
        
        try:
            SaleItem.objects.create(
                sale=sale,
                product=self.product_a,
                quantity=100,
                unit_price=self.product_a.selling_price
            )
        except ValidationError:
            pass
        
        movement_count = StockMovement.objects.filter(
            sale=sale,
            product=self.product_a
        ).count()
        
        self.assertEqual(movement_count, 0)
    
    def test_insufficient_stock_unchanged(self):
        """Verify stock unchanged when validation fails."""
        initial_stock = 5
        self.product_a.stock_quantity = initial_stock
        self.product_a.save()
        
        sale = Sale.objects.create(cashier=self.cashier)
        
        try:
            SaleItem.objects.create(
                sale=sale,
                product=self.product_a,
                quantity=100,
                unit_price=self.product_a.selling_price
            )
        except ValidationError:
            pass
        
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, initial_stock)
    
    # =========================================================================
    # GROUP 5: StockMovement FK Validation
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
                suppliers=self.supplier,
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
                suppliers=self.supplier,
                created_by=self.cashier
            )
        
        error_dict = context.exception.message_dict
        self.assertIn('quantity', error_dict)
    
    def test_valid_stock_movement_in_with_supplier(self):
        """Verify IN movement with supplier FK is valid."""
        movement = StockMovement.objects.create(
            product=self.product_a,
            movement_type=StockMovement.Reason.PURCHASE,
            quantity=50,
            suppliers=self.supplier,
            unit_cost=Decimal('5.00'),
            created_by=self.cashier
        )
        
        self.assertIsNotNone(movement.pk)
    
    def test_valid_stock_movement_out_with_sale(self):
        """Verify OUT movement (SALE) with sale FK is valid via SaleItem."""
        sale = Sale.objects.create(cashier=self.cashier)
        
        SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=5,
            unit_price=self.product_a.selling_price
        )
        
        movement = StockMovement.objects.get(
            sale=sale,
            product=self.product_a,
            movement_type=StockMovement.Reason.SALE
        )
        
        self.assertEqual(movement.quantity, 5)
    
    # =========================================================================
    # GROUP 6: Transaction Atomicity
    # =========================================================================
    
    def test_transaction_rollback_on_failure(self):
        """Verify rollback on failure during SaleItem.save()."""
        initial_stock = self.product_a.stock_quantity
        
        sale = Sale.objects.create(cashier=self.cashier)
        
        item1 = SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=5,
            unit_price=self.product_a.selling_price
        )
        
        self.product_a.refresh_from_db()
        stock_after_item1 = self.product_a.stock_quantity
        
        self.product_a.stock_quantity = 2
        self.product_a.save()
        
        try:
            with transaction.atomic():
                SaleItem.objects.create(
                    sale=sale,
                    product=self.product_a,
                    quantity=10,
                    unit_price=self.product_a.selling_price
                )
        except ValidationError:
            pass
        
        self.assertEqual(SaleItem.objects.filter(sale=sale).count(), 1)
    
    def test_concurrent_sale_protection(self):
        """Verify stock consistency under sequential operations."""
        initial_stock = self.product_a.stock_quantity
        
        sale1 = Sale.objects.create(cashier=self.cashier)
        sale2 = Sale.objects.create(cashier=self.cashier)
        
        SaleItem.objects.create(
            sale=sale1,
            product=self.product_a,
            quantity=20,
            unit_price=self.product_a.selling_price
        )
        
        SaleItem.objects.create(
            sale=sale2,
            product=self.product_a,
            quantity=30,
            unit_price=self.product_a.selling_price
        )
        
        self.product_a.refresh_from_db()
        
        expected_stock = initial_stock - 50
        self.assertEqual(self.product_a.stock_quantity, expected_stock)
    
    # =========================================================================
    # GROUP 7: Multi-Item Sale
    # =========================================================================
    
    def test_multi_item_sale_total_calculation(self):
        """Verify sale.total_amount equals sum of all SaleItem subtotals."""
        product_b = self._create_product('Test Product B', Decimal('15.00'), 100)
        product_c = self._create_product('Test Product C', Decimal('20.00'), 100)
        
        sale = Sale.objects.create(cashier=self.cashier)
        
        SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=2,
            unit_price=Decimal('10.00')
        )
        
        SaleItem.objects.create(
            sale=sale,
            product=product_b,
            quantity=3,
            unit_price=Decimal('15.00')
        )
        
        SaleItem.objects.create(
            sale=sale,
            product=product_c,
            quantity=1,
            unit_price=Decimal('20.00')
        )
        
        sale.refresh_from_db()
        self.assertEqual(sale.total_amount, Decimal('85.00'))
    
    def test_multi_item_sale_stock_deduction(self):
        """Verify each product's stock is deducted correctly."""
        product_b = self._create_product('Test Product B', Decimal('15.00'), 100)
        
        initial_a = self.product_a.stock_quantity
        initial_b = product_b.stock_quantity
        
        sale = Sale.objects.create(cashier=self.cashier)
        
        SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=10,
            unit_price=self.product_a.selling_price
        )
        
        SaleItem.objects.create(
            sale=sale,
            product=product_b,
            quantity=25,
            unit_price=product_b.selling_price
        )
        
        self.product_a.refresh_from_db()
        product_b.refresh_from_db()
        
        self.assertEqual(self.product_a.stock_quantity, initial_a - 10)
        self.assertEqual(product_b.stock_quantity, initial_b - 25)
    
    def test_multi_item_sale_delete_one_item(self):
        """Verify deleting one item from multi-item sale."""
        product_b = self._create_product('Test Product B', Decimal('15.00'), 100)
        
        sale = Sale.objects.create(cashier=self.cashier)
        
        item_a = SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=10,
            unit_price=Decimal('10.00')
        )
        
        SaleItem.objects.create(
            sale=sale,
            product=product_b,
            quantity=5,
            unit_price=Decimal('15.00')
        )
        
        sale.refresh_from_db()
        self.assertEqual(sale.total_amount, Decimal('175.00'))
        
        initial_a = self.product_a.stock_quantity
        item_a.delete()
        
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, initial_a + 10)
        
        sale.refresh_from_db()
        self.assertEqual(sale.total_amount, Decimal('75.00'))
    
    # =========================================================================
    # ADDITIONAL TESTS
    # =========================================================================
    
    def test_sale_item_subtotal_auto_calculation(self):
        """Verify subtotal is auto-calculated."""
        sale = Sale.objects.create(cashier=self.cashier)
        
        sale_item = SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=7,
            unit_price=Decimal('12.50')
        )
        
        sale_item.refresh_from_db()
        self.assertEqual(sale_item.subtotal, Decimal('87.50'))
    
    def test_stock_movement_is_stock_in_property(self):
        """Verify is_stock_in property."""
        in_reasons = StockMovement.Reason.get_in_reasons()
        
        for reason in in_reasons:
            movement = StockMovement(
                product=self.product_a,
                movement_type=reason,
                quantity=10
            )
            self.assertTrue(movement.is_stock_in)
            self.assertFalse(movement.is_stock_out)
    
    def test_stock_movement_is_stock_out_property(self):
        """Verify is_stock_out property."""
        out_reasons = StockMovement.Reason.get_out_reasons()
        
        for reason in out_reasons:
            movement = StockMovement(
                product=self.product_a,
                movement_type=reason,
                quantity=10
            )
            self.assertTrue(movement.is_stock_out)
            self.assertFalse(movement.is_stock_in)
    
    def test_expired_stock_removal(self):
        """Verify EXPIRED movement reduces stock."""
        initial_stock = self.product_a.stock_quantity
        
        StockMovement.objects.create(
            product=self.product_a,
            movement_type=StockMovement.Reason.EXPIRED,
            quantity=10,
            notes='Expired medication disposal',
            created_by=self.cashier
        )
        
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, initial_stock - 10)
    
    def test_damaged_stock_removal(self):
        """Verify DAMAGED movement reduces stock."""
        initial_stock = self.product_a.stock_quantity
        
        StockMovement.objects.create(
            product=self.product_a,
            movement_type=StockMovement.Reason.DAMAGED,
            quantity=5,
            notes='Damaged during handling',
            created_by=self.cashier
        )
        
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, initial_stock - 5)
    
    def test_return_customer_increases_stock(self):
        """Verify RETURN_CUSTOMER movement increases stock."""
        initial_stock = self.product_a.stock_quantity
        
        StockMovement.objects.create(
            product=self.product_a,
            movement_type=StockMovement.Reason.RETURN_CUSTOMER,
            quantity=3,
            notes='Customer return',
            created_by=self.cashier
        )
        
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, initial_stock + 3)
    
    def test_delete_stock_movement_reverses_stock(self):
        """Verify deleting StockMovement reverses the stock change."""
        initial_stock = self.product_a.stock_quantity
        
        movement = StockMovement.objects.create(
            product=self.product_a,
            movement_type=StockMovement.Reason.PURCHASE,
            quantity=50,
            suppliers=self.supplier,
            created_by=self.cashier
        )
        
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, initial_stock + 50)
        
        movement.delete()
        
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, initial_stock)
    
    def test_sale_number_auto_generation(self):
        """Verify sale_number is auto-generated."""
        sale = Sale.objects.create(cashier=self.cashier)
        
        self.assertTrue(sale.sale_number.startswith('SL-'))
        self.assertEqual(len(sale.sale_number), 17)
    
    def test_unit_price_snapshot(self):
        """Verify unit_price is snapshotted at sale time."""
        sale = Sale.objects.create(cashier=self.cashier)
        sale_item = SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=10,
            unit_price=self.product_a.selling_price
        )
        
        self.product_a.selling_price = Decimal('15.00')
        self.product_a.save()
        
        sale_item.refresh_from_db()
        self.assertEqual(sale_item.unit_price, Decimal('10.00'))
    
    # =========================================================================
    # INTEGRATION WITH MEDICINE TYPE (requires expiration)
    # =========================================================================
    
    def test_medicine_product_sale(self):
        """Test sale with Medicine type product (requires expiration)."""
        # Create Medicine product with expiration (following first test suite pattern)
        medicine_product = self._create_product(
            name='Lisinopril 10mg',
            selling_price=Decimal('8.50'),
            stock_quantity=100,
            product_type=self.medicine,
            with_expiration=True
        )
        
        sale = Sale.objects.create(cashier=self.cashier)
        
        SaleItem.objects.create(
            sale=sale,
            product=medicine_product,
            quantity=30,
            unit_price=medicine_product.selling_price
        )
        
        medicine_product.refresh_from_db()
        self.assertEqual(medicine_product.stock_quantity, 70)
        
        # Verify expiration date exists
        self.assertIsNotNone(medicine_product.expiration_date)
