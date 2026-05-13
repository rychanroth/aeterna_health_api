"""
Role-Based Access Control (RBAC) Test Suite
============================================

Tests permission enforcement across all ViewSets.
DO NOT test serializer validation, queryset filtering, or business logic.
ONLY test permission-based access control.

Run with: python manage.py test medicines.tests.test_rbac -v 2
"""

from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from decimal import Decimal
from datetime import date
from medicines.models import (
    User, Supplier, ProductType, Category, Product,
    Doctor, Patient, Prescription, PrescriptionItem,
    Sale, SaleItem, StockMovement
)


class ViewSetRBACTestCase(APITestCase):
    """
    RBAC Test Suite for all ViewSets.
    Tests that permissions correctly allow/deny access based on user role.
    """

    def setUp(self):
        """Create 3 users and minimal test data"""
        # === CREATE 3 USERS ===
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

        # === CREATE MINIMAL TEST DATA ===
        # ProductType (required for Category and Product)
        self.product_type = ProductType.objects.create(
            name='Test Medicine',
            requires_expiration=False,
            requires_prescription=False
        )

        # Category (required for Product)
        self.category = Category.objects.create(
            name='Test Category',
            product_type=self.product_type
        )

        # Supplier (for Product and StockMovement)
        self.supplier = Supplier.objects.create(
            name='Test Supplier',
            phone='1234567890'
        )

        # Product (for Sale and StockMovement)
        self.product = Product.objects.create(
            name='Test Product',
            product_type=self.product_type,
            category=self.category,
            selling_price=Decimal('10.00'),
            stock_quantity=100
        )
        self.product.suppliers.add(self.supplier)

        # Doctor (for Prescription)
        self.doctor = Doctor.objects.create(
            name='Dr. Test',
            license_number='DOC123'
        )

        # Patient (for Prescription)
        self.patient = Patient.objects.create(
            name='Test Patient',
            phone='9876543210'
        )

    # ============================================================
    # GROUP 1: ADMIN-ONLY WRITE VIEWSETS
    # Targets: User, Supplier, ProductType, Category
    # ============================================================

    # --- UserViewSet ---
    def test_user_create_pharmacist_forbidden(self):
        """Pharmacist cannot create users -> 403"""
        self.client.force_authenticate(user=self.pharmacist_user)
        url = reverse('user-list')
        data = {'username': 'newuser', 'role': 'cashier'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_create_cashier_forbidden(self):
        """Cashier cannot create users -> 403"""
        self.client.force_authenticate(user=self.cashier_user)
        url = reverse('user-list')
        data = {'username': 'newuser', 'role': 'cashier'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_create_admin_allowed(self):
        """Admin can create users -> 201"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('user-list')
        data = {'username': 'newuser', 'role': 'cashier', 'password': 'pass123'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # --- SupplierViewSet ---
    def test_supplier_create_pharmacist_forbidden(self):
        """Pharmacist cannot create suppliers -> 403"""
        self.client.force_authenticate(user=self.pharmacist_user)
        url = reverse('supplier-list')
        data = {'name': 'New Supplier', 'phone': '1111111111'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_supplier_create_cashier_forbidden(self):
        """Cashier cannot create suppliers -> 403"""
        self.client.force_authenticate(user=self.cashier_user)
        url = reverse('supplier-list')
        data = {'name': 'New Supplier', 'phone': '1111111111'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_supplier_create_admin_allowed(self):
        """Admin can create suppliers -> 201"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('supplier-list')
        data = {'name': 'New Supplier', 'phone': '1111111111'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # --- ProductTypeViewSet ---
    def test_producttype_create_pharmacist_forbidden(self):
        """Pharmacist cannot create product types -> 403"""
        self.client.force_authenticate(user=self.pharmacist_user)
        url = reverse('product-type-list')  # FIX: Use hyphenated basename
        data = {'name': 'New Type'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_producttype_create_cashier_forbidden(self):
        """Cashier cannot create product types -> 403"""
        self.client.force_authenticate(user=self.cashier_user)
        url = reverse('product-type-list')  # FIX: Use hyphenated basename
        data = {'name': 'New Type'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_producttype_create_admin_allowed(self):
        """Admin can create product types -> 201"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('product-type-list')  # FIX: Use hyphenated basename
        data = {'name': 'New Type'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # --- CategoryViewSet ---
    def test_category_create_pharmacist_forbidden(self):
        """Pharmacist cannot create categories -> 403"""
        self.client.force_authenticate(user=self.pharmacist_user)
        url = reverse('category-list')
        data = {'name': 'New Category', 'product_type': self.product_type.id}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_category_create_cashier_forbidden(self):
        """Cashier cannot create categories -> 403"""
        self.client.force_authenticate(user=self.cashier_user)
        url = reverse('category-list')
        data = {'name': 'New Category', 'product_type': self.product_type.id}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_category_create_admin_allowed(self):
        """Admin can create categories -> 201"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('category-list')
        data = {'name': 'New Category', 'product_type': self.product_type.id}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # ============================================================
    # GROUP 2: ADMIN OR PHARMACIST WRITE VIEWSETS
    # Targets: Product, Doctor, Patient, StockMovement
    # ============================================================

    # --- ProductViewSet ---
    def test_product_create_cashier_forbidden(self):
        """Cashier cannot create products -> 403"""
        self.client.force_authenticate(user=self.cashier_user)
        url = reverse('product-list')
        data = {
            'name': 'New Product',
            'product_type_id': self.product_type.id,
            'category_id': self.category.id,
            'selling_price': '15.00',
            'stock_quantity': 50
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_product_create_pharmacist_allowed(self):
        """Pharmacist can create products -> 201"""
        self.client.force_authenticate(user=self.pharmacist_user)
        url = reverse('product-list')
        data = {
            'name': 'New Product',
            'product_type_id': self.product_type.id,
            'category_id': self.category.id,
            'selling_price': '15.00',
            'stock_quantity': 50
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_product_create_admin_allowed(self):
        """Admin can create products -> 201"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('product-list')
        data = {
            'name': 'Another Product',
            'product_type_id': self.product_type.id,
            'category_id': self.category.id,
            'selling_price': '20.00',
            'stock_quantity': 30
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # --- DoctorViewSet ---
    def test_doctor_create_cashier_forbidden(self):
        """Cashier cannot create doctors -> 403"""
        self.client.force_authenticate(user=self.cashier_user)
        url = reverse('doctor-list')
        data = {'name': 'Dr. New', 'license_number': 'NEW123'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_create_pharmacist_allowed(self):
        """Pharmacist can create doctors -> 201"""
        self.client.force_authenticate(user=self.pharmacist_user)
        url = reverse('doctor-list')
        data = {'name': 'Dr. New', 'license_number': 'NEW123'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_doctor_create_admin_allowed(self):
        """Admin can create doctors -> 201"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('doctor-list')
        data = {'name': 'Dr. Admin', 'license_number': 'ADM123'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # --- PatientViewSet ---
    def test_patient_create_cashier_forbidden(self):
        """Cashier cannot create patients -> 403"""
        self.client.force_authenticate(user=self.cashier_user)
        url = reverse('patient-list')
        data = {'name': 'New Patient', 'phone': '5555555555'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patient_create_pharmacist_allowed(self):
        """Pharmacist can create patients -> 201"""
        self.client.force_authenticate(user=self.pharmacist_user)
        url = reverse('patient-list')
        data = {'name': 'New Patient', 'phone': '5555555555'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_patient_create_admin_allowed(self):
        """Admin can create patients -> 201"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('patient-list')
        data = {'name': 'Admin Patient', 'phone': '6666666666'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # --- StockMovementViewSet ---
    def test_stockmovement_create_cashier_forbidden(self):
        """Cashier cannot create stock movements -> 403"""
        self.client.force_authenticate(user=self.cashier_user)
        url = reverse('stock-movement-list')  # FIX: Use hyphenated basename
        data = {
            'product_id': self.product.id,
            'movement_type': 'purchase',
            'quantity': 50
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_stockmovement_create_pharmacist_allowed(self):
        """Pharmacist can create stock movements -> 201"""
        self.client.force_authenticate(user=self.pharmacist_user)
        url = reverse('stock-movement-list')  # FIX: Use hyphenated basename
        data = {
            'product_id': self.product.id,
            'movement_type': 'purchase',
            'quantity': 50
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_stockmovement_create_admin_allowed(self):
        """Admin can create stock movements -> 201"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('stock-movement-list')  # FIX: Use hyphenated basename
        data = {
            'product_id': self.product.id,
            'movement_type': 'adjustment_in',
            'quantity': 25
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_stockmovement_delete_cashier_forbidden(self):
        """Cashier cannot delete stock movements -> 403"""
        # Create a stock movement as admin
        movement = StockMovement.objects.create(
            product=self.product,
            movement_type=StockMovement.Reason.ADJUSTMENT_IN,
            quantity=10,
            created_by=self.admin_user
        )
        self.client.force_authenticate(user=self.cashier_user)
        url = reverse('stock-movement-detail', args=[movement.id])  # FIX: Use hyphenated basename
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ============================================================
    # GROUP 3: SALE VIEWSET COMPLEX RULES
    # ============================================================

    def test_sale_create_pharmacist_forbidden(self):
        """Pharmacist cannot create sales -> 403"""
        self.client.force_authenticate(user=self.pharmacist_user)
        url = reverse('sale-list')
        data = {
            'items': [{
                'product_id': self.product.id,
                'quantity': 5,
                'unit_price': '10.00'
            }]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sale_create_cashier_allowed(self):
        """Cashier can create sales -> 201"""
        self.client.force_authenticate(user=self.cashier_user)
        url = reverse('sale-list')
        data = {
            'items': [{
                'product_id': self.product.id,
                'quantity': 5,
                'unit_price': '10.00'
            }]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_sale_create_admin_allowed(self):
        """Admin can create sales -> 201"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('sale-list')
        data = {
            'items': [{
                'product_id': self.product.id,
                'quantity': 3,
                'unit_price': '10.00'
            }]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_sale_update_cashier_forbidden(self):
        """Cashier cannot update sales -> 403"""
        # Create sale as admin
        sale = Sale.objects.create(cashier=self.admin_user, total_amount=Decimal('0'))
        self.client.force_authenticate(user=self.cashier_user)
        url = reverse('sale-detail', args=[sale.id])
        data = {'payment_method': 'cash'}
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sale_delete_cashier_forbidden(self):
        """Cashier cannot delete sales -> 403"""
        # Create sale as admin
        sale = Sale.objects.create(cashier=self.admin_user, total_amount=Decimal('0'))
        self.client.force_authenticate(user=self.cashier_user)
        url = reverse('sale-detail', args=[sale.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sale_update_admin_allowed(self):
        """Admin can update sales -> 200"""
        # Create sale
        sale = Sale.objects.create(cashier=self.admin_user, total_amount=Decimal('0'))
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('sale-detail', args=[sale.id])
        data = {'payment_method': 'card'}
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_sale_auto_assign_cashier(self):
        """Sale POST by cashier auto-assigns cashier field"""
        self.client.force_authenticate(user=self.cashier_user)
        url = reverse('sale-list')
        data = {
            'items': [{
                'product_id': self.product.id,
                'quantity': 2,
                'unit_price': '10.00'
            }]
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Verify cashier was auto-assigned
        self.assertEqual(response.data['cashier'], self.cashier_user.id)

    def test_sale_read_scoping_cashier(self):
        """Cashier can only see their own sales"""
        # Create sale as admin
        admin_sale = Sale.objects.create(cashier=self.admin_user, total_amount=Decimal('100.00'))
        # Create sale as cashier
        cashier_sale = Sale.objects.create(cashier=self.cashier_user, total_amount=Decimal('50.00'))

        self.client.force_authenticate(user=self.cashier_user)
        url = reverse('sale-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify only cashier's sale is returned
        sale_ids = [s['id'] for s in (response.data['results'] if 'results' in response.data else response.data)]
        self.assertIn(cashier_sale.id, sale_ids)
        self.assertNotIn(admin_sale.id, sale_ids)

    # ============================================================
    # GROUP 4: PRESCRIPTION VIEWSET CUSTOM ACTIONS
    # ============================================================

    def _create_pending_prescription(self):
        """Helper to create a pending prescription"""
        prescription = Prescription.objects.create(
            doctor=self.doctor,
            patient=self.patient,
            status=Prescription.Status.PENDING,
            prescription_date=date.today()  # FIX: Add required field
        )
        PrescriptionItem.objects.create(
            prescription=prescription,
            product=self.product,
            quantity_prescribed=10
        )
        return prescription

    def test_prescription_verify_cashier_forbidden(self):
        """Cashier cannot verify prescriptions -> 403"""
        prescription = self._create_pending_prescription()
        self.client.force_authenticate(user=self.cashier_user)
        url = reverse('prescription-verify', args=[prescription.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_prescription_verify_pharmacist_allowed(self):
        """Pharmacist can verify prescriptions -> 200"""
        prescription = self._create_pending_prescription()
        self.client.force_authenticate(user=self.pharmacist_user)
        url = reverse('prescription-verify', args=[prescription.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_prescription_verify_sets_verified_by(self):
        """Verify action sets verified_by to pharmacist user"""
        prescription = self._create_pending_prescription()
        self.client.force_authenticate(user=self.pharmacist_user)
        url = reverse('prescription-verify', args=[prescription.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify verified_by was set
        self.assertEqual(response.data['verified_by'], self.pharmacist_user.id)

    def test_prescription_reject_cashier_forbidden(self):
        """Cashier cannot reject prescriptions -> 403"""
        prescription = self._create_pending_prescription()
        self.client.force_authenticate(user=self.cashier_user)
        url = reverse('prescription-reject', args=[prescription.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_prescription_reject_pharmacist_allowed(self):
        """Pharmacist can reject prescriptions -> 200"""
        prescription = self._create_pending_prescription()
        self.client.force_authenticate(user=self.pharmacist_user)
        url = reverse('prescription-reject', args=[prescription.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ============================================================
    # GROUP 5: CATEGORY READ-ONLY CUSTOM ACTIONS
    # ============================================================

    def test_category_roots_cashier_allowed(self):
        """Cashier can view category roots -> 200"""
        self.client.force_authenticate(user=self.cashier_user)
        url = reverse('category-roots')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_category_bulk_move_cashier_forbidden(self):
        """Cashier cannot bulk move categories -> 403"""
        # Create another category to move
        child = Category.objects.create(
            name='Child Category',
            product_type=self.product_type,
            parent=self.category
        )
        self.client.force_authenticate(user=self.cashier_user)
        url = reverse('category-bulk-move')
        data = {
            'category_ids': [child.id],
            'new_parent_id': None
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_category_bulk_move_admin_allowed(self):
        """Admin can bulk move categories -> 200"""
        # Create another category to move
        child = Category.objects.create(
            name='Child Category 2',
            product_type=self.product_type,
            parent=self.category
        )
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('category-bulk-move')
        data = {
            'category_ids': [child.id],
            'new_parent_id': None
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ============================================================
    # ADDITIONAL: READ ACCESS TESTS
    # ============================================================

    def test_product_list_cashier_allowed(self):
        """Cashier can view products -> 200"""
        self.client.force_authenticate(user=self.cashier_user)
        url = reverse('product-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_sale_list_pharmacist_allowed(self):
        """Pharmacist can view sales -> 200"""
        self.client.force_authenticate(user=self.pharmacist_user)
        url = reverse('sale-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_stockmovement_list_cashier_allowed(self):
        """Cashier can view stock movements -> 200"""
        self.client.force_authenticate(user=self.cashier_user)
        url = reverse('stock-movement-list')  # FIX: Use hyphenated basename
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
