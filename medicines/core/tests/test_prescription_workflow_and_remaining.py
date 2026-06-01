"""
Prescription Workflow, Serializer Validation & Remaining Actions Test Suite
===========================================================================

Tests the critical blind spots left by existing test suites:
- test_category_recursion: Hierarchy, depth, circular refs
- test_sale_transaction: SaleItem creation, stock deduction, immutability
- test_rbac: Permission checks, basic verify/reject

This suite covers:
- Prescription -> Sale workflow (SaleSerializer.validate)
- Product & StockMovement serializer validations
- ViewSet custom actions (expired, low_stock, report, etc.)
- Bug documentation
- Model properties

Run with: python manage.py test medicines.tests.test_prescription_workflow_and_remaining -v 2
"""

from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

from medicines.core.models import (
    User, Supplier, ProductType, Category, Product,
    Doctor, Patient, Prescription, PrescriptionItem,
    Sale, SaleItem, StockMovement
)


class PrescriptionWorkflowAndRemainingTestCase(APITestCase):
    """
    Test suite for Prescription-Sale integration, serializer validations,
    and untested ViewSet custom actions.
    """

    def setUp(self):
        """Create test prerequisites for all test groups."""
        today = date.today()

        # === CREATE USERS ===
        self.admin_user = User.objects.create_user(
            username='admin',
            password='pass123',
            role='admin'
        )
        self.pharmacist_user = User.objects.create_user(
            username='pharmacist',
            password='pass123',
            role='pharmacist'
        )
        self.cashier_user = User.objects.create_user(
            username='cashier',
            password='pass123',
            role='cashier'
        )

        # === PRODUCT TYPES ===
        # Medicine type: requires_expiration=True, requires_prescription=True
        self.medicine_type = ProductType.objects.create(
            name='Medicine',
            requires_expiration=True,
            requires_prescription=True
        )

        # Equipment type: no special requirements
        self.equipment_type = ProductType.objects.create(
            name='Equipment',
            requires_expiration=False,
            requires_prescription=False
        )

        # === CATEGORIES ===
        self.medicine_category = Category.objects.create(
            name='Test Medicine Category',
            product_type=self.medicine_type
        )
        self.equipment_category = Category.objects.create(
            name='Test Equipment Category',
            product_type=self.equipment_type
        )

        # === SUPPLIER ===
        self.supplier = Supplier.objects.create(
            name='Test Supplier',
            phone='+1-555-0000'
        )

        # === PRODUCTS ===
        # Product A: Medicine type, NOT expired, requires prescription
        self.product_a = Product.objects.create(
            name='Lisinopril 10mg',
            product_type=self.medicine_type,
            category=self.medicine_category,
            base_unit='tablet',
            selling_price=Decimal('10.00'),
            stock_quantity=100,
            expiration_date=today + timedelta(days=365)
        )
        self.product_a.suppliers.add(self.supplier)

        # Product B: Medicine type, EXPIRED
        self.product_b = Product.objects.create(
            name='Expired Amoxicillin',
            product_type=self.medicine_type,
            category=self.medicine_category,
            base_unit='capsule',
            selling_price=Decimal('8.00'),
            stock_quantity=50,
            expiration_date=today - timedelta(days=30)  # EXPIRED
        )
        self.product_b.suppliers.add(self.supplier)

        # Product C: Equipment type (no prescription required)
        self.product_c = Product.objects.create(
            name='Bandages',
            product_type=self.equipment_type,
            category=self.equipment_category,
            base_unit='roll',
            selling_price=Decimal('5.00'),
            stock_quantity=200,
            expiration_date=None
        )
        self.product_c.suppliers.add(self.supplier)

        # Product D: Medicine type for multi-item Rx tests
        self.product_d = Product.objects.create(
            name='Metformin 500mg',
            product_type=self.medicine_type,
            category=self.medicine_category,
            base_unit='tablet',
            selling_price=Decimal('12.00'),
            stock_quantity=150,
            expiration_date=today + timedelta(days=180)
        )
        self.product_d.suppliers.add(self.supplier)

        # === DOCTOR & PATIENT ===
        self.doctor = Doctor.objects.create(
            name='Dr. Test',
            license_number='DOC123'
        )
        self.patient = Patient.objects.create(
            name='Test Patient',
            phone='555-1234'
        )

        # Authenticate as admin by default
        self.client.force_authenticate(user=self.admin_user)

    # =========================================================================
    # GROUP 1: Prescription-Sale Integration (Serializer Level)
    # =========================================================================

    def test_sale_fails_without_prescription_for_rx_product(self):
        """
        Verify that selling a prescription-required product WITHOUT a prescription
        returns 400 with appropriate error message.
        """
        url = reverse('sale-list')
        data = {
            'items': [{
                'product_id': self.product_a.id,
                'quantity': 10,
                'unit_price': '10.00'
            }]
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('prescription', str(response.data).lower())

    def test_sale_fails_with_unverified_prescription(self):
        """
        Verify that attempting a sale with a PENDING prescription
        returns 400 ('must be verified').
        """
        # Create PENDING prescription
        prescription = Prescription.objects.create(
            doctor=self.doctor,
            patient=self.patient,
            status=Prescription.Status.PENDING,
            prescription_date=date.today()
        )
        PrescriptionItem.objects.create(
            prescription=prescription,
            product=self.product_a,
            quantity_prescribed=20
        )

        url = reverse('sale-list')
        data = {
            'prescription_id': prescription.id,
            'items': [{
                'product_id': self.product_a.id,
                'quantity': 10,
                'unit_price': '10.00'
            }]
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('verified', str(response.data).lower())

    def test_sale_fails_if_rx_product_not_on_prescription(self):
        """
        Verify that selling products NOT listed on the prescription
        returns 400 ('not in the provided prescription').

        Rx has Product A, but sale attempts to include Product A AND Product D.
        """
        # Create and verify prescription for Product A only
        prescription = Prescription.objects.create(
            doctor=self.doctor,
            patient=self.patient,
            status=Prescription.Status.VERIFIED,
            prescription_date=date.today(),
            verified_by=self.pharmacist_user
        )
        PrescriptionItem.objects.create(
            prescription=prescription,
            product=self.product_a,
            quantity_prescribed=30
        )

        url = reverse('sale-list')
        data = {
            'prescription_id': prescription.id,
            'items': [
                {
                    'product_id': self.product_a.id,
                    'quantity': 10,
                    'unit_price': '10.00'
                },
                {
                    'product_id': self.product_d.id,  # NOT on prescription
                    'quantity': 5,
                    'unit_price': '12.00'
                }
            ]
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not in the provided prescription', str(response.data).lower())

    def test_sale_succeeds_and_marks_prescription_dispensed(self):
        """
        Verify that a successful sale with a verified prescription:
        1. Returns 201
        2. Auto-changes Prescription.status to DISPENSED
        """
        # Create and verify prescription
        prescription = Prescription.objects.create(
            doctor=self.doctor,
            patient=self.patient,
            status=Prescription.Status.VERIFIED,
            prescription_date=date.today(),
            verified_by=self.pharmacist_user
        )
        PrescriptionItem.objects.create(
            prescription=prescription,
            product=self.product_a,
            quantity_prescribed=30
        )

        url = reverse('sale-list')
        data = {
            'prescription_id': prescription.id,
            'items': [{
                'product_id': self.product_a.id,
                'quantity': 10,
                'unit_price': '10.00'
            }]
        }
        response = self.client.post(url, data, format='json')

        # Verify sale created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify prescription status changed to DISPENSED
        prescription.refresh_from_db()
        self.assertEqual(prescription.status, Prescription.Status.DISPENSED)

    def test_sale_fails_for_expired_product(self):
        """
        Verify that attempting to sell an expired product returns 400
        with message about expiration.
        """
        # Create verified prescription for expired product
        prescription = Prescription.objects.create(
            doctor=self.doctor,
            patient=self.patient,
            status=Prescription.Status.VERIFIED,
            prescription_date=date.today(),
            verified_by=self.pharmacist_user
        )
        PrescriptionItem.objects.create(
            prescription=prescription,
            product=self.product_b,  # EXPIRED product
            quantity_prescribed=20
        )

        url = reverse('sale-list')
        data = {
            'prescription_id': prescription.id,
            'items': [{
                'product_id': self.product_b.id,  # Expired product
                'quantity': 5,
                'unit_price': '8.00'
            }]
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('expired', str(response.data).lower())

    def test_sale_allows_otc_product_with_rx_product(self):
        """
        Verify that OTC products (like bandages) can be included in a sale
        that also has prescription products, as long as the Rx products
        are on the prescription.
        """
        # Create and verify prescription for Product A
        prescription = Prescription.objects.create(
            doctor=self.doctor,
            patient=self.patient,
            status=Prescription.Status.VERIFIED,
            prescription_date=date.today(),
            verified_by=self.pharmacist_user
        )
        PrescriptionItem.objects.create(
            prescription=prescription,
            product=self.product_a,
            quantity_prescribed=30
        )

        url = reverse('sale-list')
        data = {
            'prescription_id': prescription.id,
            'items': [
                {
                    'product_id': self.product_a.id,  # Rx product (on prescription)
                    'quantity': 10,
                    'unit_price': '10.00'
                },
                {
                    'product_id': self.product_c.id,  # OTC product (bandages)
                    'quantity': 5,
                    'unit_price': '5.00'
                }
            ]
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # =========================================================================
    # GROUP 2: Product & Stock Validations
    # =========================================================================

    def test_product_create_fails_zero_price(self):
        """
        Verify that creating a product with selling_price <= 0
        returns 400 validation error.
        """
        url = reverse('product-list')
        data = {
            'name': 'Invalid Product',
            'product_type_id': self.equipment_type.id,
            'category_id': self.equipment_category.id,
            'selling_price': '0.00',
            'stock_quantity': 10
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('selling_price', response.data)

    def test_product_create_fails_negative_price(self):
        """
        Verify that creating a product with negative selling_price
        returns 400 validation error.
        """
        url = reverse('product-list')
        data = {
            'name': 'Negative Price Product',
            'product_type_id': self.equipment_type.id,
            'category_id': self.equipment_category.id,
            'selling_price': '-5.00',
            'stock_quantity': 10
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('selling_price', response.data)

    def test_product_create_fails_missing_expiration_for_medicine(self):
        """
        Verify that creating a Medicine-type product without expiration_date
        returns 400 validation error.
        """
        url = reverse('product-list')
        data = {
            'name': 'New Medicine',
            'product_type_id': self.medicine_type.id,  # requires_expiration=True
            'category_id': self.medicine_category.id,
            'selling_price': '15.00',
            'stock_quantity': 50,
            'expiration_date': None  # Missing!
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('expiration_date', response.data)

    def test_stock_movement_create_fails_insufficient_stock(self):
        """
        Verify that creating an OUT-type StockMovement with quantity
        greater than product stock returns 400.
        """
        url = reverse('stock-movement-list')
        data = {
            'product_id': self.product_a.id,
            'movement_type': 'damaged',
            'quantity': 500,  # More than stock (100)
            'notes': 'Testing insufficient stock'
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Insufficient stock', str(response.data))

    def test_stock_movement_auto_sets_created_by(self):
        """
        Verify that StockMovement.created_by is auto-assigned
        to the authenticated user.
        """
        url = reverse('stock-movement-list')
        data = {
            'product_id': self.product_a.id,
            'movement_type': 'purchase',
            'quantity': 50,
            'supplier_id': self.supplier.id
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created_by'], self.admin_user.id)

    # =========================================================================
    # GROUP 3: ViewSet Custom Actions
    # =========================================================================

    def test_product_expired_action(self):
        """
        Verify /products/expired/ returns only expired products.
        """
        url = reverse('product-expired')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        product_names = [p['name'] for p in response.data]
        self.assertIn('Expired Amoxicillin', product_names)  # product_b
        self.assertNotIn('Lisinopril 10mg', product_names)  # product_a (not expired)

    def test_product_low_stock_action(self):
        """
        Verify /products/low_stock/ returns products with stock < 10.
        """
        # Create a low-stock product
        low_stock_product = Product.objects.create(
            name='Low Stock Item',
            product_type=self.equipment_type,
            category=self.equipment_category,
            selling_price=Decimal('3.00'),
            stock_quantity=5  # < 10
        )

        url = reverse('product-low-stock')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        product_names = [p['name'] for p in response.data]
        self.assertIn('Low Stock Item', product_names)

    def test_product_expiring_soon_action(self):
        """
        Verify /products/expiring_soon/ returns products expiring in 30 days.
        """
        # Create product expiring in 15 days
        soon_expiring = Product.objects.create(
            name='Expiring Soon Item',
            product_type=self.medicine_type,
            category=self.medicine_category,
            selling_price=Decimal('7.00'),
            stock_quantity=30,
            expiration_date=date.today() + timedelta(days=15)
        )

        url = reverse('product-expiring-soon')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        product_names = [p['name'] for p in response.data]
        self.assertIn('Expiring Soon Item', product_names)

    def test_product_by_type_missing_param_400(self):
        """
        Verify /products/by_type/ returns 400 if product_type_id is missing.
        """
        url = reverse('product-by-type')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_product_by_type_with_valid_param(self):
        """
        Verify /products/by_type/?product_type_id=X returns filtered products.
        """
        url = reverse('product-by-type')
        response = self.client.get(url, {'product_type_id': self.medicine_type.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # All returned products should be Medicine type
        for product in response.data:
            self.assertEqual(product['product_type']['id'], self.medicine_type.id)

    def test_sale_today_action(self):
        """
        Verify /sales/today/ returns today's sales.
        """
        # Create a sale today
        sale = Sale.objects.create(cashier=self.admin_user)
        SaleItem.objects.create(
            sale=sale,
            product=self.product_c,
            quantity=5,
            unit_price=Decimal('5.00')
        )

        url = reverse('sale-today')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

    def test_sale_my_sales_action(self):
        """
        Verify /sales/my_sales/ returns only current user's sales.
        """
        # Create sales for different users
        admin_sale = Sale.objects.create(cashier=self.admin_user)
        cashier_sale = Sale.objects.create(cashier=self.cashier_user)

        # Authenticate as cashier
        self.client.force_authenticate(user=self.cashier_user)
        url = reverse('sale-my-sales')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sale_ids = [s['id'] for s in response.data]
        self.assertIn(cashier_sale.id, sale_ids)
        self.assertNotIn(admin_sale.id, sale_ids)

    def test_sale_report_action_structure(self):
        """
        Verify /sales/report/ returns correct JSON structure with
        today.total_sales and this_month.transaction_count keys.
        """
        # Create some sales for data
        sale = Sale.objects.create(cashier=self.admin_user)
        SaleItem.objects.create(
            sale=sale,
            product=self.product_c,
            quantity=10,
            unit_price=Decimal('5.00')
        )

        url = reverse('sale-report')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify structure
        self.assertIn('today', response.data)
        self.assertIn('this_month', response.data)
        self.assertIn('total_sales', response.data['today'])
        self.assertIn('transaction_count', response.data['today'])
        self.assertIn('total_sales', response.data['this_month'])
        self.assertIn('transaction_count', response.data['this_month'])

    def test_prescription_pending_action(self):
        """
        Verify /prescriptions/pending/ returns only PENDING prescriptions.
        """
        # Create prescriptions with different statuses
        pending_rx = Prescription.objects.create(
            doctor=self.doctor,
            patient=self.patient,
            status=Prescription.Status.PENDING,
            prescription_date=date.today()
        )
        verified_rx = Prescription.objects.create(
            doctor=self.doctor,
            patient=self.patient,
            status=Prescription.Status.VERIFIED,
            prescription_date=date.today(),
            verified_by=self.pharmacist_user
        )

        url = reverse('prescription-pending')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rx_ids = [r['id'] for r in response.data]
        self.assertIn(pending_rx.id, rx_ids)
        self.assertNotIn(verified_rx.id, rx_ids)

    def test_prescription_verified_action(self):
        """
        Verify /prescriptions/verified/ returns only VERIFIED prescriptions.
        """
        # Create prescriptions with different statuses
        pending_rx = Prescription.objects.create(
            doctor=self.doctor,
            patient=self.patient,
            status=Prescription.Status.PENDING,
            prescription_date=date.today()
        )
        verified_rx = Prescription.objects.create(
            doctor=self.doctor,
            patient=self.patient,
            status=Prescription.Status.VERIFIED,
            prescription_date=date.today(),
            verified_by=self.pharmacist_user
        )

        url = reverse('prescription-verified')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rx_ids = [r['id'] for r in response.data]
        self.assertIn(verified_rx.id, rx_ids)
        self.assertNotIn(pending_rx.id, rx_ids)

    def test_patient_with_allergies_action(self):
        """
        Verify /patients/with_allergies/ returns only patients with
        non-empty allergy_notes.
        """
        # Create patients with and without allergies
        patient_with_allergies = Patient.objects.create(
            name='Allergic Patient',
            phone='111-1111',
            allergy_notes='Penicillin allergy'
        )
        patient_without_allergies = Patient.objects.create(
            name='Non-Allergic Patient',
            phone='222-2222',
            allergy_notes=''  # Empty
        )

        url = reverse('patient-with-allergies')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        patient_ids = [p['id'] for p in response.data]
        self.assertIn(patient_with_allergies.id, patient_ids)
        self.assertNotIn(patient_without_allergies.id, patient_ids)

    def test_stock_movement_stock_in_action(self):
        """
        Verify /stock-movements/stock_in/ returns only IN-type movements.
        """
        # Create IN and OUT movements
        in_movement = StockMovement.objects.create(
            product=self.product_a,
            movement_type=StockMovement.Reason.PURCHASE,
            quantity=50,
            suppliers=self.supplier,
            created_by=self.admin_user
        )
        out_movement = StockMovement.objects.create(
            product=self.product_a,
            movement_type=StockMovement.Reason.DAMAGED,
            quantity=5,
            created_by=self.admin_user
        )

        url = reverse('stock-movement-stock-in')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        movement_types = [m['movement_type'] for m in response.data]
        # All should be IN types
        for mt in movement_types:
            self.assertIn(mt, ['purchase', 'return_customer', 'adjustment_in'])

    def test_stock_movement_stock_out_action(self):
        """
        Verify /stock-movements/stock_out/ returns only OUT-type movements.
        """
        # Create IN and OUT movements
        in_movement = StockMovement.objects.create(
            product=self.product_a,
            movement_type=StockMovement.Reason.PURCHASE,
            quantity=50,
            suppliers=self.supplier,
            created_by=self.admin_user
        )
        out_movement = StockMovement.objects.create(
            product=self.product_a,
            movement_type=StockMovement.Reason.DAMAGED,
            quantity=5,
            created_by=self.admin_user
        )

        url = reverse('stock-movement-stock-out')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        movement_types = [m['movement_type'] for m in response.data]
        # All should be OUT types
        for mt in movement_types:
            self.assertIn(mt, ['sale', 'expired', 'damaged', 'return_supplier', 'adjustment_out'])

    def test_stock_movement_summary_action_math(self):
        """
        Verify /stock-movements/summary/ math:
        net_change == total_in - total_out
        """
        # Create some movements
        StockMovement.objects.create(
            product=self.product_a,
            movement_type=StockMovement.Reason.PURCHASE,
            quantity=100,
            suppliers=self.supplier,
            created_by=self.admin_user
        )
        StockMovement.objects.create(
            product=self.product_a,
            movement_type=StockMovement.Reason.DAMAGED,
            quantity=20,
            created_by=self.admin_user
        )
        StockMovement.objects.create(
            product=self.product_a,
            movement_type=StockMovement.Reason.RETURN_CUSTOMER,
            quantity=10,
            created_by=self.admin_user
        )

        url = reverse('stock-movement-summary')
        response = self.client.get(url, {'product': self.product_a.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        total_in = response.data['total_in']
        total_out = response.data['total_out']
        net_change = response.data['net_change']

        # Verify math: net_change = total_in - total_out
        self.assertEqual(net_change, total_in - total_out)
        # Verify specific values: 100 + 10 = 110 IN, 20 OUT
        self.assertEqual(total_in, 110)
        self.assertEqual(total_out, 20)
        self.assertEqual(net_change, 90)

    # =========================================================================
    # GROUP 4: Bug Documentation
    # =========================================================================

    def test_category_stock_summary_calculates_value(self):
        """
        BUG DOCUMENTATION: CategoryViewSet.stock_summary calculates total_value
        incorrectly using get_total_stock() instead of get_total_value().

        This test creates a product with stock=10 and price=5.00.
        Expected total_value = 50.00, but current implementation returns 10.

        NOTE: This test will FAIL until the bug is fixed.
        Bug location: views.py line ~200
        Fix: Change 'total_value': category.get_total_stock() to
             'total_value': category.get_total_value()
        """
        # Create category with a product
        category = Category.objects.create(
            name='Test Value Category',
            product_type=self.equipment_type
        )
        product = Product.objects.create(
            name='Value Test Product',
            product_type=self.equipment_type,
            category=category,
            selling_price=Decimal('5.00'),
            stock_quantity=10
        )

        url = reverse('category-stock-summary', args=[category.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Expected: total_value = stock (10) * price (5.00) = 50.00
        # Actual (buggy): total_value = stock = 10
        expected_value = Decimal('50.00')
        actual_value = response.data['total_value']

        # This assertion documents the bug
        # After fix, this should pass
        self.assertEqual(
            actual_value,
            expected_value,
            f"BUG: total_value should be {expected_value} (stock * price), "
            f"but got {actual_value}. Fix: Use category.get_total_value() "
            f"instead of category.get_total_stock() in stock_summary action."
        )

    # =========================================================================
    # GROUP 5: Model Helpers
    # =========================================================================

    def test_patient_age_calculation(self):
        """
        Verify Patient.age property calculates correctly from date_of_birth.
        Test with DOB 25 years ago -> expect 25.
        """
        today = date.today()
        dob_25_years_ago = today.replace(year=today.year - 25)

        patient = Patient.objects.create(
            name='Age Test Patient',
            phone='333-3333',
            date_of_birth=dob_25_years_ago
        )

        self.assertEqual(patient.age, 25)

    def test_patient_age_with_birthday_not_yet_this_year(self):
        """
        Verify age calculation when birthday hasn't occurred this year yet.
        """
        today = date.today()
        # Set DOB to later this year (but 25 years ago)
        future_date = today + timedelta(days=30)  # 30 days in future
        dob = future_date.replace(year=today.year - 25)

        patient = Patient.objects.create(
            name='Birthday Pending Patient',
            phone='444-4444',
            date_of_birth=dob
        )

        # Age should be 24 (birthday hasn't happened yet this year)
        self.assertEqual(patient.age, 24)

    def test_stock_movement_create_adjustment_in(self):
        """
        Verify StockMovement.create_adjustment() with positive quantity
        creates an ADJUSTMENT_IN movement.
        """
        initial_stock = self.product_a.stock_quantity

        movement = StockMovement.create_adjustment(
            product=self.product_a,
            quantity=25,  # Positive = IN
            user=self.admin_user,
            notes='Positive adjustment test'
        )

        self.assertEqual(movement.movement_type, StockMovement.Reason.ADJUSTMENT_IN)
        self.assertEqual(movement.quantity, 25)

        # Verify stock increased
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, initial_stock + 25)

    def test_stock_movement_create_adjustment_out(self):
        """
        Verify StockMovement.create_adjustment() with negative quantity
        creates an ADJUSTMENT_OUT movement.
        """
        initial_stock = self.product_a.stock_quantity

        movement = StockMovement.create_adjustment(
            product=self.product_a,
            quantity=-15,  # Negative = OUT
            user=self.admin_user,
            notes='Negative adjustment test'
        )

        self.assertEqual(movement.movement_type, StockMovement.Reason.ADJUSTMENT_OUT)
        self.assertEqual(movement.quantity, 15)  # Stored as positive

        # Verify stock decreased
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, initial_stock - 15)

    def test_product_effective_requires_prescription(self):
        """
        Verify effective_requires_prescription property combines
        product and ProductType settings.
        """
        # Product A: type requires prescription
        self.assertTrue(self.product_a.effective_requires_prescription)

        # Product C: Equipment type, no prescription required
        self.assertFalse(self.product_c.effective_requires_prescription)

        # Create product with product-level override
        override_product = Product.objects.create(
            name='Override Rx Product',
            product_type=self.equipment_type,  # Type doesn't require Rx
            category=self.equipment_category,
            selling_price=Decimal('10.00'),
            stock_quantity=50,
            requires_prescription=True  # But product itself requires
        )

        self.assertTrue(override_product.effective_requires_prescription)

    def test_product_is_expired_property(self):
        """
        Verify Product.is_expired property works correctly.
        """
        self.assertTrue(self.product_b.is_expired)  # Expired product
        self.assertFalse(self.product_a.is_expired)  # Not expired
        self.assertFalse(self.product_c.is_expired)  # No expiration date

    def test_product_is_low_stock_property(self):
        """
        Verify Product.is_low_stock property (stock < 10).
        """
        low_stock = Product.objects.create(
            name='Very Low Stock',
            product_type=self.equipment_type,
            category=self.equipment_category,
            selling_price=Decimal('2.00'),
            stock_quantity=5
        )
        self.assertTrue(low_stock.is_low_stock)
        self.assertFalse(self.product_a.is_low_stock)  # stock=100
