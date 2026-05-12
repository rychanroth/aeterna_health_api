from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from medicines.models import ProductType, Category, Product
from decimal import Decimal
from datetime import date, timedelta


class CategoryRecursionTestCase(TestCase):
    """Test suite for recursive category structure"""

    def setUp(self):
        """Create test data"""
        # Create ProductTypes
        self.medicine = ProductType.objects.create(
            name='Medicine',
            requires_expiration=True,
            requires_prescription=True
        )
        self.equipment = ProductType.objects.create(
            name='Medical Equipment',
            requires_expiration=False,
            requires_prescription=False
        )

        # Create hierarchical categories for Medicine
        # Medicine > Cardiovascular > Antihypertensives > ACE Inhibitors
        self.cardio = Category.objects.create(
            name='Cardiovascular',
            product_type=self.medicine,
            parent=None
        )
        self.antihypertensives = Category.objects.create(
            name='Antihypertensives',
            product_type=self.medicine,
            parent=self.cardio
        )
        self.ace_inhibitors = Category.objects.create(
            name='ACE Inhibitors',
            product_type=self.medicine,
            parent=self.antihypertensives
        )

        # Create a category for Equipment (different type)
        self.diagnostic = Category.objects.create(
            name='Diagnostic Tools',
            product_type=self.equipment,
            parent=None
        )

    # ==========================================
    # TEST 1: Type Consistency
    # ==========================================

    def test_type_consistency_valid_parent(self):
        """Category can have parent from same ProductType"""
        new_category = Category(
            name='Beta Blockers',
            product_type=self.medicine,
            parent=self.antihypertensives
        )
        # Should not raise
        new_category.full_clean()
        new_category.save()
        self.assertEqual(new_category.parent, self.antihypertensives)

    def test_type_consistency_invalid_parent(self):
        """Category cannot have parent from different ProductType"""
        new_category = Category(
            name='Blood Pressure Monitors',
            product_type=self.equipment,
            parent=self.cardio  # cardio is Medicine type!
        )
        with self.assertRaises(ValidationError) as context:
            new_category.full_clean()
        self.assertIn('parent', str(context.exception))

    def test_type_consistency_on_update(self):
        """Prevent changing parent to different ProductType"""
        # Try to move Equipment category under Medicine parent
        with self.assertRaises(ValidationError):
            self.diagnostic.parent = self.cardio
            self.diagnostic.full_clean()

    # ==========================================
    # TEST 2: Circular Reference Protection
    # ==========================================

    def test_circular_reference_self_parent(self):
        """Category cannot be its own parent"""
        with self.assertRaises(ValidationError):
            self.cardio.parent = self.cardio
            self.cardio.full_clean()

    def test_circular_reference_direct_loop(self):
        """Prevent A → B → A loop"""
        # Create a child
        child = Category.objects.create(
            name='Test Child',
            product_type=self.medicine,
            parent=self.cardio
        )
        # Try to make cardio parent of child
        with self.assertRaises(ValidationError):
            self.cardio.parent = child
            self.cardio.full_clean()

    def test_circular_reference_deep_loop(self):
        """Prevent A → B → C → A loop (3-level)"""
        # cardio -> antihypertensives -> ace_inhibitors
        # Try to make cardio parent of ace_inhibitors
        with self.assertRaises(ValidationError):
            self.cardio.parent = self.ace_inhibitors
            self.cardio.full_clean()

    # ==========================================
    # TEST 3: Depth Calculation
    # ==========================================

    def test_depth_calculation(self):
        """Verify depth property calculates correctly"""
        self.assertEqual(self.cardio.depth, 1)
        self.assertEqual(self.antihypertensives.depth, 2)
        self.assertEqual(self.ace_inhibitors.depth, 3)

    def test_full_path_generation(self):
        """Verify full_path property generates correctly"""
        self.assertEqual(
            self.ace_inhibitors.full_path,
            'Medicine > Cardiovascular > Antihypertensives > ACE Inhibitors'
        )

    # ==========================================
    # TEST 4: Ancestor/Descendant Methods
    # ==========================================

    def test_get_ancestors(self):
        """Verify ancestor traversal"""
        ancestors = self.ace_inhibitors.get_ancestors()
        self.assertEqual(len(ancestors), 2)
        self.assertIn(self.antihypertensives, ancestors)
        self.assertIn(self.cardio, ancestors)

    def test_get_descendants(self):
        """Verify descendant traversal"""
        descendants = self.cardio.get_descendants()
        self.assertEqual(len(descendants), 2)
        self.assertIn(self.antihypertensives, descendants)
        self.assertIn(self.ace_inhibitors, descendants)

    def test_is_ancestor_of(self):
        """Verify ancestor checking"""
        self.assertTrue(self.cardio.is_ancestor_of(self.ace_inhibitors))
        self.assertFalse(self.ace_inhibitors.is_ancestor_of(self.cardio))

    # ==========================================
    # TEST 5: Depth-First Aggregation
    # ==========================================

    def test_get_all_products_recursive(self):
        """Verify products fetched from all descendants"""
        # Create products at different levels
        today = date.today()
        
        Product.objects.create(
            name='Lisinopril 10mg',
            product_type=self.medicine,
            category=self.ace_inhibitors,
            base_unit='tablet',
            selling_price=Decimal('5.00'),
            stock_quantity=100,
            expiration_date=today + timedelta(days=365)
        )
        Product.objects.create(
            name='Amlodipine 5mg',
            product_type=self.medicine,
            category=self.antihypertensives,
            base_unit='tablet',
            selling_price=Decimal('4.00'),
            stock_quantity=200,
            expiration_date=today + timedelta(days=365)
        )

        # Get all products under Cardiovascular
        products = self.cardio.get_all_products()
        self.assertEqual(products.count(), 2)

    def test_get_total_stock_recursive(self):
        """Verify stock aggregation includes descendants"""
        today = date.today()
        
        Product.objects.create(
            name='Lisinopril 10mg',
            product_type=self.medicine,
            category=self.ace_inhibitors,
            base_unit='tablet',
            selling_price=Decimal('5.00'),
            stock_quantity=100,
            expiration_date=today + timedelta(days=365)
        )
        Product.objects.create(
            name='Amlodipine 5mg',
            product_type=self.medicine,
            category=self.antihypertensives,
            base_unit='tablet',
            selling_price=Decimal('4.00'),
            stock_quantity=200,
            expiration_date=today + timedelta(days=365)
        )

        # Total stock should be 300
        self.assertEqual(self.cardio.get_total_stock(), 300)

    # ==========================================
    # TEST 6: Transaction Safety
    # ==========================================

    def test_bulk_move_transaction_rollback(self):
        """Verify transaction rolls back on partial failure"""
        # Create categories to move
        cat1 = Category.objects.create(
            name='Cat 1',
            product_type=self.medicine,
            parent=None
        )
        cat2 = Category.objects.create(
            name='Cat 2',
            product_type=self.equipment,  # Different type!
            parent=None
        )

        # Try to move both under cardio (should fail for cat2)
        with transaction.atomic():
            try:
                cat1.parent = self.cardio
                cat1.save()
                cat2.parent = self.cardio  # This will fail validation
                cat2.full_clean()
                cat2.save()
            except ValidationError:
                transaction.set_rollback(True)

        # cat1 should NOT have been moved (transaction rolled back)
        cat1.refresh_from_db()
        self.assertIsNone(cat1.parent)

    # ==========================================
    # TEST 7: Serializer Validation
    # ==========================================

    def test_serializer_type_consistency_error(self):
        """Serializer rejects type mismatch"""
        from medicines.serializers import CategorySerializer

        data = {
            'name': 'Test Category',
            'product_type_id': self.equipment.id,
            'parent_id': self.cardio.id  # Medicine type!
        }

        serializer = CategorySerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('parent_id', serializer.errors)

    def test_serializer_circular_reference_error(self):
        """Serializer rejects circular reference on update"""
        from medicines.serializers import CategorySerializer

        # Try to make cardio parent of ace_inhibitors
        data = {'parent_id': self.ace_inhibitors.id}
        serializer = CategorySerializer(self.cardio, data=data, partial=True)

        self.assertFalse(serializer.is_valid())
        self.assertIn('parent_id', serializer.errors)