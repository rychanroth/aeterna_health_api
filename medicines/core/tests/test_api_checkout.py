"""
Test Suite: POS Checkout API Endpoint
======================================
"""

from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.db.models import Sum
from django.urls import reverse
from django.contrib.auth import get_user_model

from medicines.core.models import (
    Product, Sale, SaleItem, StockMovement, Batch,
    Prescription, Doctor, Patient
)
from .helpers import *

User = get_user_model()

# FIX: Helper to calculate total stock since model property was removed
def get_total_stock(product):
    return product.batches.filter(is_active=True).aggregate(
        total=Sum('quantity')
    )['total'] or 0


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

        # Standard products (Helper creates 1 batch per product automatically)
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
            requires_prescription=True,
            requires_expiration=True
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
        payload = {
            "items": [{"product_id": self.product_a.id, "quantity": 5}],
            "payment_method": "cash"
        }
        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(SaleItem.objects.count(), 1)

        # FIX: Use helper function
        self.assertEqual(get_total_stock(self.product_a), 95)

        sale = Sale.objects.first()
        self.assertEqual(sale.total_amount, Decimal('50.00'))
        self.assertEqual(sale.cashier, self.cashier)

    def test_checkout_multi_item(self):
        payload = {
            "items": [
                {"product_id": self.product_a.id, "quantity": 2},
                {"product_id": self.product_b.id, "quantity": 3}
            ],
            "payment_method": "card"
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 201)

        # FIX: Use helper function
        self.assertEqual(get_total_stock(self.product_a), 98)
        self.assertEqual(get_total_stock(self.product_b), 47)

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

        rx.refresh_from_db()
        self.assertEqual(rx.status, Prescription.Status.DISPENSED)

        sale = Sale.objects.first()
        self.assertEqual(sale.prescription_id, rx.id)

    # =========================================================================
    # GROUP 2: FEFO Allocation
    # =========================================================================

    def test_checkout_fefo_allocation(self):
        batch_expiring_soon = Batch.objects.create(
            product=self.product_a,
            quantity=10,
            expiration_date=date.today() + timedelta(days=10),
            cost_price=Decimal('5.00')
        )
        
        # FIX: Use helper function
        self.assertEqual(get_total_stock(self.product_a), 110)

        payload = {
            "items": [{"product_id": self.product_a.id, "quantity": 15}],
            "payment_method": "cash"
        }

        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 201)

        batch_expiring_soon.refresh_from_db()
        original_batch = self.product_a.batches.exclude(pk=batch_expiring_soon.pk).first()
        original_batch.refresh_from_db()

        self.assertEqual(batch_expiring_soon.quantity, 0)
        self.assertEqual(original_batch.quantity, 95)

    def test_checkout_explicit_batch_id(self):
        """Verify checkout succeeds when forcing a specific batch_id."""
        batch_to_buy = self.product_a.batches.first()

        payload = {
            "items": [{"product_id": self.product_a.id, "quantity": 5, "batch_id": batch_to_buy.id}],
            "payment_method": "cash"
        }

        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 201)

        batch_to_buy.refresh_from_db()
        self.assertEqual(batch_to_buy.quantity, 95) # 100 - 5

    # =========================================================================
    # GROUP 3: Stock Validation
    # =========================================================================

    def test_checkout_insufficient_stock(self):
        payload = {
            "items": [{"product_id": self.product_a.id, "quantity": 999}],
            "payment_method": "cash"
        }
        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(response.status_code, 400)
        # FIX: Adjust error string matching to our new FEFO logic
        self.assertIn('Insufficient stock', str(response.data))

        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(SaleItem.objects.count(), 0)

        # FIX: Use helper function
        self.assertEqual(get_total_stock(self.product_a), 100)

    def test_checkout_partial_stock_fail(self):
        payload = {
            "items": [
                {"product_id": self.product_a.id, "quantity": 10},
                {"product_id": self.product_b.id, "quantity": 999}
            ],
            "payment_method": "cash"
        }
        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(response.status_code, 400)

        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(SaleItem.objects.count(), 0)
        self.assertEqual(StockMovement.objects.filter(movement_type=StockMovement.Reason.SALE).count(), 0)

        # FIX: Use helper function
        self.assertEqual(get_total_stock(self.product_a), 100)
        self.assertEqual(get_total_stock(self.product_b), 50)

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