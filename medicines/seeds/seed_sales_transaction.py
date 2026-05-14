"""
Sales Transaciton Data Seeding Script
======================

Seeds exact data required by test_sale_transaction and test_rbac.
Run this before executing the test suite.

Usage:
    python manage.py shell < seed_qa_data.py
    # OR
    python manage.py shell
    >>> exec(open('seed_qa_data.py').read())
"""

from django.db import transaction
from decimal import Decimal
from datetime import date, timedelta
from django.contrib.auth import get_user_model

from medicines.models import (
    ProductType, Category, Supplier, Product,
    Doctor, Patient, Prescription, PrescriptionItem,
    Sale, SaleItem, StockMovement
)

User = get_user_model()


def seed_sales_transaction_data():
    """
    Seeds exact data required by test_sale_transaction and test_rbac.
    Run this before executing the test suite.
    """
    with transaction.atomic():
        print("Seeding QA Data...")
        
        # =====================================================================
        # STEP 1: USERS (Required by RBAC Tests)
        # =====================================================================
        print("  [1/4] Creating Users...")
        
        # RBAC test users (from test_rbac.py setUp)
        admin_user, _ = User.objects.get_or_create(
            username='admin',
            defaults={
                'role': 'admin',
            }
        )
        admin_user.set_password('pass123')
        admin_user.save()
        
        pharmacist_user, _ = User.objects.get_or_create(
            username='pharmacist',
            defaults={
                'role': 'pharmacist',
            }
        )
        pharmacist_user.set_password('pass123')
        pharmacist_user.save()
        
        cashier_user, _ = User.objects.get_or_create(
            username='cashier',
            defaults={
                'role': 'cashier',
            }
        )
        cashier_user.set_password('pass123')
        cashier_user.save()
        
        # Sale transaction test user (from test_sale_transaction.py setUp)
        test_cashier, _ = User.objects.get_or_create(
            username='test_cashier',
            defaults={
                'is_staff': True,
            }
        )
        test_cashier.set_password('testpass123')
        test_cashier.save()
        
        print(f"      - admin_user (id={admin_user.id}, role={admin_user.role})")
        print(f"      - pharmacist_user (id={pharmacist_user.id}, role={pharmacist_user.role})")
        print(f"      - cashier_user (id={cashier_user.id}, role={cashier_user.role})")
        print(f"      - test_cashier (id={test_cashier.id})")
        
        # =====================================================================
        # STEP 2: BASE PRODUCTS & STOCK (Required by Sale Transaction Tests)
        # =====================================================================
        print("  [2/4] Creating ProductTypes, Categories, Suppliers, Products...")
        
        # === ProductTypes ===
        # From test_rbac.py
        rbac_product_type, _ = ProductType.objects.get_or_create(
            name='Test Medicine',
            defaults={
                'requires_expiration': False,
                'requires_prescription': False,
            }
        )
        
        # From test_sale_transaction.py
        medicine_type, _ = ProductType.objects.get_or_create(
            name='Medicine',
            defaults={
                'requires_expiration': True,
                'requires_prescription': True,
            }
        )
        
        equipment_type, _ = ProductType.objects.get_or_create(
            name='Equipment',
            defaults={
                'requires_expiration': False,
                'requires_prescription': False,
            }
        )
        
        # === Categories ===
        # From test_rbac.py
        rbac_category, _ = Category.objects.get_or_create(
            name='Test Category',
            product_type=rbac_product_type,
        )
        
        # From test_sale_transaction.py
        medicine_category, _ = Category.objects.get_or_create(
            name='Test Medicine Category',
            product_type=medicine_type,
        )
        
        equipment_category, _ = Category.objects.get_or_create(
            name='Test Equipment Category',
            product_type=equipment_type,
        )
        
        # === Suppliers ===
        # From test_rbac.py
        rbac_supplier, _ = Supplier.objects.get_or_create(
            name='Test Supplier',
            phone='1234567890',
        )
        
        # From test_sale_transaction.py (slightly different phone)
        sale_supplier, _ = Supplier.objects.get_or_create(
            name='Test Supplier',
            phone='+1-555-0000',
        )
        
        # === Products ===
        # From test_rbac.py (stock_quantity=100 in setUp)
        rbac_product, _ = Product.objects.get_or_create(
            name='Test Product',
            product_type=rbac_product_type,
            category=rbac_category,
            defaults={
                'selling_price': Decimal('10.00'),
                'stock_quantity': 0,  # Will be set via StockMovement
            }
        )
        rbac_product.suppliers.add(rbac_supplier)
        
        # Set stock via StockMovement (proper business flow)
        if rbac_product.stock_quantity < 100:
            StockMovement.objects.get_or_create(
                product=rbac_product,
                movement_type=StockMovement.Reason.PURCHASE,
                quantity=100,
                suppliers=rbac_supplier,
                defaults={
                    'created_by': admin_user,
                }
            )
            rbac_product.refresh_from_db()
        
        # From test_sale_transaction.py (stock_quantity=100 via StockMovement)
        product_a, _ = Product.objects.get_or_create(
            name='Test Product A',
            product_type=equipment_type,
            category=equipment_category,
            defaults={
                'base_unit': 'piece',
                'selling_price': Decimal('10.00'),
                'stock_quantity': 0,  # Will be set via StockMovement
            }
        )
        product_a.suppliers.add(sale_supplier)
        
        # Set stock via StockMovement (matches test setUp)
        if product_a.stock_quantity < 100:
            StockMovement.objects.get_or_create(
                product=product_a,
                movement_type=StockMovement.Reason.PURCHASE,
                quantity=100,
                suppliers=sale_supplier,
                defaults={
                    'unit_cost': Decimal('6.00'),
                    'created_by': test_cashier,
                }
            )
            product_a.refresh_from_db()
        
        print(f"      - rbac_product: 'Test Product' (stock={rbac_product.stock_quantity})")
        print(f"      - product_a: 'Test Product A' (stock={product_a.stock_quantity})")
        
        # =====================================================================
        # STEP 3: DUMMY TARGETS FOR RBAC MUTATIONS
        # =====================================================================
        print("  [3/4] Creating Dummy RBAC Mutation Targets...")
        
        # Doctor (for Prescription tests - test_rbac.py line 80-83)
        doctor, _ = Doctor.objects.get_or_create(
            license_number='DOC123',
            defaults={
                'name': 'Dr. Test',
            }
        )
        
        # Patient (for Prescription tests - test_rbac.py line 86-89)
        patient, _ = Patient.objects.get_or_create(
            phone='9876543210',
            defaults={
                'name': 'Test Patient',
            }
        )
        
        # Prescription (for verify/reject action tests - created fresh in tests)
        # The tests create prescriptions in helper methods, but we create one here
        # for any test that might need an existing prescription
        prescription, created = Prescription.objects.get_or_create(
            doctor=doctor,
            patient=patient,
            status=Prescription.Status.PENDING,
            prescription_date=date.today(),
        )
        if created:
            PrescriptionItem.objects.get_or_create(
                prescription=prescription,
                product=rbac_product,
                defaults={
                    'quantity_prescribed': 10,
                }
            )
        
        print(f"      - doctor: 'Dr. Test' (license={doctor.license_number})")
        print(f"      - patient: 'Test Patient' (phone={patient.phone})")
        print(f"      - prescription: id={prescription.id}, status={prescription.status}")
        
        # =====================================================================
        # STEP 4: HISTORICAL SALES (For Sale Read Scoping Tests)
        # =====================================================================
        print("  [4/4] Creating Historical Sales for Read Scoping Tests...")
        
        # From test_sale_read_scoping_cashier (test_rbac.py lines 436-451)
        # Admin's sale (should NOT be visible to cashier)
        admin_sale, _ = Sale.objects.get_or_create(
            cashier=admin_user,
            defaults={
                # total_amount auto-calculated, but test expects 100.00
            }
        )
        # Add an item to set the total
        if admin_sale.items.count() == 0:
            SaleItem.objects.create(
                sale=admin_sale,
                product=rbac_product,
                quantity=10,
                unit_price=Decimal('10.00'),
            )
            admin_sale.refresh_from_db()
        
        # Cashier's sale (SHOULD be visible to cashier)
        cashier_sale, _ = Sale.objects.get_or_create(
            cashier=cashier_user,
            defaults={
                # total_amount auto-calculated, but test expects 50.00
            }
        )
        # Add an item to set the total
        if cashier_sale.items.count() == 0:
            SaleItem.objects.create(
                sale=cashier_sale,
                product=rbac_product,
                quantity=5,
                unit_price=Decimal('10.00'),
            )
            cashier_sale.refresh_from_db()
        
        # Additional sales for update/delete permission tests
        # (created inline in tests, but having extras doesn't hurt)
        sale_for_update_test, _ = Sale.objects.get_or_create(
            cashier=admin_user,
        )
        sale_for_delete_test, _ = Sale.objects.get_or_create(
            cashier=admin_user,
        )
        
        print(f"      - admin_sale: id={admin_sale.id}, total={admin_sale.total_amount}")
        print(f"      - cashier_sale: id={cashier_sale.id}, total={cashier_sale.total_amount}")
        print(f"      - sale_for_update_test: id={sale_for_update_test.id}")
        print(f"      - sale_for_delete_test: id={sale_for_delete_test.id}")
        
        # =====================================================================
        # SUMMARY
        # =====================================================================
        print("")
        print("=" * 60)
        print("QA Data Seeding Complete.")
        print("=" * 60)
        print("")
        print("Summary:")
        print(f"  Users:         {User.objects.count()}")
        print(f"  ProductTypes:  {ProductType.objects.count()}")
        print(f"  Categories:    {Category.objects.count()}")
        print(f"  Suppliers:     {Supplier.objects.count()}")
        print(f"  Products:      {Product.objects.count()}")
        print(f"  Doctors:       {Doctor.objects.count()}")
        print(f"  Patients:      {Patient.objects.count()}")
        print(f"  Prescriptions: {Prescription.objects.count()}")
        print(f"  Sales:         {Sale.objects.count()}")
        print(f"  SaleItems:     {SaleItem.objects.count()}")
        print(f"  StockMovements: {StockMovement.objects.count()}")
        print("")
        print("Data prepared for:")
        print("  - test_rbac.py (RBAC permission tests)")
        print("  - test_sale_transaction.py (Sale/SaleItem/StockMovement flow)")
        print("")


# Execute the seeding function
if __name__ == '__main__':
    seed_sales_transaction_data()
