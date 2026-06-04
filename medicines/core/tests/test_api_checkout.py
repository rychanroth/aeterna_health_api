"""
Test Suite: POS Checkout API Endpoint
======================================

Validates the SaleViewSet.checkout() atomic transaction flow.
This is the highest-risk endpoint as it mutates 4 models atomically.

Business Rules Under Test:
--------------------------
1. Happy path: Single item, multi-item, and prescription sales
2. Stock validation: Insufficient stock and atomic rollback
3. Prescription validation: Required products, unverified/dispensed RX
4. Input validation: Empty cart, invalid product, negative quantity
5. Payment method handling
"""

from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from medicines.core.models import (
    Product, Sale, SaleItem, StockMovement,
    Prescription, Doctor, Patient
)
from .helpers import *

User = get_user_model()


class CheckoutAPITestCase(TestCase):
    """Test suite for the /api/sales/checkout/ endpoint."""

    def setUp(self):
        """Create test prerequisites."""
        self.cashier = User.objects.create_user(
            username='checkout_cashier',
            password='testpass123',
            role='cashier',
            is_staff=True
        )
        self.client = create_authenticated_client(self.cashier)
        
        # Standard products
        self.product_a = create_product_with_stock(
            name='Checkout Product A',
            stock_quantity=100,
            selling_price=Decimal('10.00'),
            created_by=self.cashier
        )
        self.product_b = create_product_with_stock(
            name='Checkout Product B',
            stock_quantity=50,
            selling_price=Decimal('20.00'),
            created_by=self.cashier
        )
        
        # Prescription-required product
        self.rx_product = create_product_with_stock(
            name='Prescription Medication',
            stock_quantity=30,
            selling_price=Decimal('15.00'),
            created_by=self.cashier,
            product_type_name='Medicine',
            requires_prescription=True
        )
        
        # Prescription prerequisites
        self.doctor = Doctor.objects.create(name='Dr. Checkout')
        self.patient = Patient.objects.create(name='Patient Checkout')
        
        self.url = reverse('sale-checkout')

    def _create_prescription(self, status=Prescription.Status.VERIFIED):
        """Helper to create a prescription with specific status."""
        rx = Prescription.objects.create(
            doctor=self.doctor,
            patient=self.patient,
            prescription_date=date.today(),
            status=status
        )
        return rx

    # =========================================================================
    # GROUP 1: Happy Path
    # =========================================================================

    def test_checkout_single_item(self):
        """Verify successful checkout of a single item."""
        payload = {
            "items": [{"product_id": self.product_a.id, "quantity": 5}],
            "payment_method": "cash"
        }
        
        response = self.client.post(self.url, payload, format='json')
        
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(SaleItem.objects.count(), 1)
        
        # Verify stock deducted
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 95)
        
        # Verify total calculated
        sale = Sale.objects.first()
        self.assertEqual(sale.total_amount, Decimal('50.00'))
        self.assertEqual(sale.cashier, self.cashier)

    def test_checkout_multi_item(self):
        """Verify successful checkout of multiple items."""
        payload = {
            "items": [
                {"product_id": self.product_a.id, "quantity": 2},
                {"product_id": self.product_b.id, "quantity": 3}
            ],
            "payment_method": "card"
        }
        
        response = self.client.post(self.url, payload, format='json')
        
        self.assertEqual(response.status_code, 201)
        
        # Verify both stocks deducted
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 98)
        self.assertEqual(self.product_b.stock_quantity, 47)
        
        # Verify total = (2*10) + (3*20) = 80
        sale = Sale.objects.first()
        self.assertEqual(sale.total_amount, Decimal('80.00'))

    def test_checkout_with_verified_rx(self):
        """Verify successful checkout linking a verified prescription."""
        rx = self._create_prescription(status=Prescription.Status.VERIFIED)
        
        payload = {
            "items": [{"product_id": self.rx_product.id, "quantity": 1}],
            "payment_method": "insurance",
            "prescription_id": rx.id
        }
        
        response = self.client.post(self.url, payload, format='json')
        
        self.assertEqual(response.status_code, 201)
        
        # Verify prescription status updated to DISPENSED
        rx.refresh_from_db()
        self.assertEqual(rx.status, Prescription.Status.DISPENSED)
        
        # Verify sale linked to prescription
        sale = Sale.objects.first()
        self.assertEqual(sale.prescription_id, rx.id)

    # =========================================================================
    # GROUP 2: Stock Validation
    # =========================================================================

    def test_checkout_insufficient_stock(self):
        """Verify checkout fails if any item exceeds available stock."""
        payload = {
            "items": [{"product_id": self.product_a.id, "quantity": 999}],
            "payment_method": "cash"
        }
        
        response = self.client.post(self.url, payload, format='json')
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('Insufficient stock', str(response.data))
        
        # Verify no records created
        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(SaleItem.objects.count(), 0)
        
        # Verify stock unchanged
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 100)

    def test_checkout_partial_stock_fail(self):
        """Verify entire transaction rolls back if second item fails stock check."""
        # Product A has 100 stock, Product B has 50 stock
        payload = {
            "items": [
                {"product_id": self.product_a.id, "quantity": 10},  # Valid
                {"product_id": self.product_b.id, "quantity": 999}  # Invalid
            ],
            "payment_method": "cash"
        }
        
        response = self.client.post(self.url, payload, format='json')
        
        self.assertEqual(response.status_code, 400)
        
        # Verify NO records created (atomicity)
        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(SaleItem.objects.count(), 0)
        self.assertEqual(StockMovement.objects.filter(movement_type=StockMovement.Reason.SALE).count(), 0)
        
        # Verify BOTH stocks unchanged
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 100)
        self.assertEqual(self.product_b.stock_quantity, 50)

    # =========================================================================
    # GROUP 3: Prescription Validation
    # =========================================================================

    def test_checkout_rx_product_without_rx(self):
        """Verify prescription-required product fails without prescription_id."""
        payload = {
            "items": [{"product_id": self.rx_product.id, "quantity": 1}],
            "payment_method": "cash"
        }
        
        response = self.client.post(self.url, payload, format='json')
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('requires a prescription', str(response.data))

    def test_checkout_unverified_rx(self):
        """Verify checkout fails if prescription is not verified."""
        rx = self._create_prescription(status=Prescription.Status.PENDING)
        
        payload = {
            "items": [{"product_id": self.rx_product.id, "quantity": 1}],
            "payment_method": "cash",
            "prescription_id": rx.id
        }
        
        response = self.client.post(self.url, payload, format='json')
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('must be verified', str(response.data))
        
        # Verify prescription status unchanged
        rx.refresh_from_db()
        self.assertEqual(rx.status, Prescription.Status.PENDING)

    def test_checkout_dispensed_rx(self):
        """Verify checkout fails if prescription is already dispensed."""
        rx = self._create_prescription(status=Prescription.Status.DISPENSED)
        
        payload = {
            "items": [{"product_id": self.rx_product.id, "quantity": 1}],
            "payment_method": "cash",
            "prescription_id": rx.id
        }
        
        response = self.client.post(self.url, payload, format='json')
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('must be verified', str(response.data))

    # =========================================================================
    # GROUP 4: Input Validation
    # =========================================================================

    def test_checkout_empty_cart(self):
        """Verify checkout fails with empty items array."""
        payload = {"items": [], "payment_method": "cash"}
        
        response = self.client.post(self.url, payload, format='json')
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('Cart is empty', str(response.data))

    def test_checkout_invalid_product(self):
        """Verify checkout fails with non-existent product_id."""
        payload = {
            "items": [{"product_id": 99999, "quantity": 1}],
            "payment_method": "cash"
        }
        
        response = self.client.post(self.url, payload, format='json')
        
        self.assertEqual(response.status_code, 404)
        self.assertIn('not found', str(response.data))

    def test_checkout_negative_quantity(self):
        """Verify checkout fails with negative quantity."""
        payload = {
            "items": [{"product_id": self.product_a.id, "quantity": -5}],
            "payment_method": "cash"
        }
        
        response = self.client.post(self.url, payload, format='json')
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('Invalid quantity', str(response.data))

    # =========================================================================
    # GROUP 5: Payment Method
    # =========================================================================

    def test_checkout_cash_payment(self):
        """Verify cash payment method is saved correctly."""
        payload = {
            "items": [{"product_id": self.product_a.id, "quantity": 1}],
            "payment_method": "cash"
        }
        
        response = self.client.post(self.url, payload, format='json')
        sale = Sale.objects.first()
        
        self.assertEqual(response.status_code, 201)
        self.assertEqual(sale.payment_method, Sale.PaymentMethod.CASH)

    def test_checkout_card_payment(self):
        """Verify card payment method is saved correctly."""
        payload = {
            "items": [{"product_id": self.product_a.id, "quantity": 1}],
            "payment_method": "card"
        }
        
        response = self.client.post(self.url, payload, format='json')
        sale = Sale.objects.first()
        
        self.assertEqual(response.status_code, 201)
        self.assertEqual(sale.payment_method, Sale.PaymentMethod.CARD)

    def test_checkout_insurance_payment(self):
        """Verify insurance payment method is saved correctly."""
        payload = {
            "items": [{"product_id": self.product_a.id, "quantity": 1}],
            "payment_method": "insurance"
        }
        
        response = self.client.post(self.url, payload, format='json')
        sale = Sale.objects.first()
        
        self.assertEqual(response.status_code, 201)
        self.assertEqual(sale.payment_method, Sale.PaymentMethod.INSURANCE)