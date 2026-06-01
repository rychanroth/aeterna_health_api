"""
Prescription Workflow QA Data Seeding Script
=============================================

Seeds exact data required by test_prescription_workflow_and_remaining.py.
Run this before executing the test suite for manual testing or demo purposes.

Usage:
    python manage.py shell < seed_prescription_workflow_qa_data.py
    # OR
    python manage.py shell
    >>> exec(open('seed_prescription_workflow_qa_data.py').read())

Note: For automated tests, Django's APITestCase creates isolated test databases.
    This script is for manual testing, demos, or seeding a development database.
"""

from django.db import transaction
from datetime import date, timedelta
from django.utils import timezone
from decimal import Decimal

from medicines.core.models import (
    User, Supplier, ProductType, Category, Product,
    Doctor, Patient, Prescription, PrescriptionItem,
    Sale, SaleItem, StockMovement
)


def seed_prescription_workflow_data():
    """
    Seeds exact data required by test_prescription_workflow_and_remaining.py.
    Run this before executing the test suite.
    """
    with transaction.atomic():
        print("Seeding Prescription Workflow QA Data...")
        
        today = date.today()
        
        # =====================================================================
        # STEP 1: USERS
        # =====================================================================
        print("  [1/6] Creating Users...")
        
        admin_user, _ = User.objects.get_or_create(
            username='admin',
            defaults={'role': 'admin'}
        )
        admin_user.set_password('pass123')
        admin_user.save()
        
        pharmacist_user, _ = User.objects.get_or_create(
            username='pharmacist',
            defaults={'role': 'pharmacist'}
        )
        pharmacist_user.set_password('pass123')
        pharmacist_user.save()
        
        cashier_user, _ = User.objects.get_or_create(
            username='cashier',
            defaults={'role': 'cashier'}
        )
        cashier_user.set_password('pass123')
        cashier_user.save()
        
        print(f"      - admin_user (id={admin_user.id}, role={admin_user.role})")
        print(f"      - pharmacist_user (id={pharmacist_user.id}, role={pharmacist_user.role})")
        print(f"      - cashier_user (id={cashier_user.id}, role={cashier_user.role})")
        
        # =====================================================================
        # STEP 2: PRODUCT TYPES & CATEGORIES
        # =====================================================================
        print("  [2/6] Creating ProductTypes & Categories...")
        
        # Medicine type: requires_expiration=True, requires_prescription=True
        medicine_type, _ = ProductType.objects.get_or_create(
            name='Medicine',
            defaults={
                'requires_expiration': True,
                'requires_prescription': True,
            }
        )
        
        # Equipment type: no special requirements
        equipment_type, _ = ProductType.objects.get_or_create(
            name='Equipment',
            defaults={
                'requires_expiration': False,
                'requires_prescription': False,
            }
        )
        
        # Categories linked to types
        medicine_category, _ = Category.objects.get_or_create(
            name='Test Medicine Category',
            product_type=medicine_type,
        )
        
        equipment_category, _ = Category.objects.get_or_create(
            name='Test Equipment Category',
            product_type=equipment_type,
        )
        
        print(f"      - Medicine (req_expiration=True, req_prescription=True)")
        print(f"      - Equipment (req_expiration=False, req_prescription=False)")
        print(f"      - Test Medicine Category")
        print(f"      - Test Equipment Category")
        
        # =====================================================================
        # STEP 3: SUPPLIER
        # =====================================================================
        print("  [3/6] Creating Supplier...")
        
        supplier, _ = Supplier.objects.get_or_create(
            name='Test Supplier',
            phone='+1-555-0000'
        )
        
        print(f"      - Test Supplier (id={supplier.id})")
        
        # =====================================================================
        # STEP 4: PRODUCTS (Critical for Serializer Tests)
        # =====================================================================
        print("  [4/6] Creating Products...")
        
        # --- Product A: Medicine type, NOT expired, stock=100, requires prescription ---
        product_a, _ = Product.objects.get_or_create(
            name='Lisinopril 10mg',
            defaults={
                'product_type': medicine_type,
                'category': medicine_category,
                'base_unit': 'tablet',
                'selling_price': Decimal('10.00'),
                'stock_quantity': 0,  # Will be set via StockMovement
                'expiration_date': today + timedelta(days=365),  # Future
            }
        )
        product_a.suppliers.add(supplier)
        
        # --- Product B: Medicine type, EXPIRED, stock=50 ---
        product_b, _ = Product.objects.get_or_create(
            name='Expired Amoxicillin',
            defaults={
                'product_type': medicine_type,
                'category': medicine_category,
                'base_unit': 'capsule',
                'selling_price': Decimal('8.00'),
                'stock_quantity': 0,  # Will be set via StockMovement
                'expiration_date': today - timedelta(days=30),  # EXPIRED
            }
        )
        product_b.suppliers.add(supplier)
        
        # --- Product C: Equipment type, no prescription required, stock=200 ---
        product_c, _ = Product.objects.get_or_create(
            name='Bandages',
            defaults={
                'product_type': equipment_type,
                'category': equipment_category,
                'base_unit': 'roll',
                'selling_price': Decimal('5.00'),
                'stock_quantity': 0,  # Will be set via StockMovement
                'expiration_date': None,
            }
        )
        product_c.suppliers.add(supplier)
        
        # --- Product D: Medicine type for multi-item Rx tests, stock=150 ---
        product_d, _ = Product.objects.get_or_create(
            name='Metformin 500mg',
            defaults={
                'product_type': medicine_type,
                'category': medicine_category,
                'base_unit': 'tablet',
                'selling_price': Decimal('12.00'),
                'stock_quantity': 0,  # Will be set via StockMovement
                'expiration_date': today + timedelta(days=180),
            }
        )
        product_d.suppliers.add(supplier)
        
        # --- Low Stock Product (for /products/low_stock/ test) ---
        low_stock_product, _ = Product.objects.get_or_create(
            name='Low Stock Item',
            defaults={
                'product_type': equipment_type,
                'category': equipment_category,
                'base_unit': 'piece',
                'selling_price': Decimal('3.00'),
                'stock_quantity': 0,  # Will be set via StockMovement
            }
        )
        low_stock_product.suppliers.add(supplier)
        
        # --- Expiring Soon Product (for /products/expiring_soon/ test) ---
        expiring_soon_product, _ = Product.objects.get_or_create(
            name='Expiring Soon Item',
            defaults={
                'product_type': medicine_type,
                'category': medicine_category,
                'base_unit': 'tablet',
                'selling_price': Decimal('7.00'),
                'stock_quantity': 0,  # Will be set via StockMovement
                'expiration_date': today + timedelta(days=15),  # Within 30 days
            }
        )
        expiring_soon_product.suppliers.add(supplier)
        
        # --- Value Test Product (for stock_summary bug test) ---
        value_test_product, _ = Product.objects.get_or_create(
            name='Value Test Product',
            defaults={
                'product_type': equipment_type,
                'category': equipment_category,
                'base_unit': 'piece',
                'selling_price': Decimal('5.00'),
                'stock_quantity': 0,  # Will be set via StockMovement
            }
        )
        value_test_product.suppliers.add(supplier)
        
        # --- Category for stock_summary test ---
        value_category, _ = Category.objects.get_or_create(
            name='Test Value Category',
            product_type=equipment_type,
        )
        value_test_product.category = value_category
        value_test_product.save()
        
        print(f"      - Lisinopril 10mg (stock=100, NOT expired, requires Rx)")
        print(f"      - Expired Amoxicillin (stock=50, EXPIRED, requires Rx)")
        print(f"      - Bandages (stock=200, OTC)")
        print(f"      - Metformin 500mg (stock=150, requires Rx)")
        print(f"      - Low Stock Item (stock=5, for low_stock test)")
        print(f"      - Expiring Soon Item (expires in 15 days)")
        print(f"      - Value Test Product (stock=10, price=5.00)")
        
        # =====================================================================
        # STEP 5: APPLY STOCK VIA STOCKMOVEMENTS (Business Rule)
        # =====================================================================
        print("  [5/6] Applying Stock via StockMovements...")
        
        # Helper function to add stock
        def add_stock(product, quantity, user=admin_user, supp=supplier):
            existing_stock = product.stock_quantity
            needed = quantity - existing_stock
            if needed > 0:
                StockMovement.objects.create(
                    product=product,
                    movement_type=StockMovement.Reason.PURCHASE,
                    quantity=needed,
                    suppliers=supp,
                    created_by=user
                )
                product.refresh_from_db()
        
        add_stock(product_a, 100)
        add_stock(product_b, 50)
        add_stock(product_c, 200)
        add_stock(product_d, 150)
        add_stock(low_stock_product, 5)  # < 10 for low_stock test
        add_stock(expiring_soon_product, 30)
        add_stock(value_test_product, 10)  # 10 * 5.00 = 50.00 total value
        
        print(f"      - Lisinopril 10mg: stock={product_a.stock_quantity}")
        print(f"      - Expired Amoxicillin: stock={product_b.stock_quantity}")
        print(f"      - Bandages: stock={product_c.stock_quantity}")
        print(f"      - Metformin 500mg: stock={product_d.stock_quantity}")
        print(f"      - Low Stock Item: stock={low_stock_product.stock_quantity}")
        print(f"      - Expiring Soon Item: stock={expiring_soon_product.stock_quantity}")
        print(f"      - Value Test Product: stock={value_test_product.stock_quantity}")
        
        # =====================================================================
        # STEP 6: DOCTOR & PATIENTS
        # =====================================================================
        print("  [6/6] Creating Doctor & Patients...")
        
        # Doctor for prescriptions
        doctor, _ = Doctor.objects.get_or_create(
            license_number='DOC123',
            defaults={'name': 'Dr. Test'}
        )
        
        # Main test patient
        patient, _ = Patient.objects.get_or_create(
            phone='555-1234',
            defaults={'name': 'Test Patient'}
        )
        
        # Patient for age calculation test (exactly 25 years ago)
        age_test_patient, _ = Patient.objects.get_or_create(
            phone='333-3333',
            defaults={
                'name': 'Age Test Patient',
                'date_of_birth': today.replace(year=today.year - 25)
            }
        )
        
        # Patient for birthday-not-yet test (DOB 25 years ago but birthday hasn't happened this year)
        future_date = today + timedelta(days=30)
        dob_pending = future_date.replace(year=today.year - 25)
        birthday_pending_patient, _ = Patient.objects.get_or_create(
            phone='444-4444',
            defaults={
                'name': 'Birthday Pending Patient',
                'date_of_birth': dob_pending
            }
        )
        
        # Patient WITH allergies (for with_allergies test)
        patient_with_allergies, _ = Patient.objects.get_or_create(
            phone='111-1111',
            defaults={
                'name': 'Allergic Patient',
                'allergy_notes': 'Penicillin allergy'
            }
        )
        
        # Patient WITHOUT allergies (for with_allergies test)
        patient_without_allergies, _ = Patient.objects.get_or_create(
            phone='222-2222',
            defaults={
                'name': 'Non-Allergic Patient',
                'allergy_notes': ''  # Empty
            }
        )
        
        print(f"      - Dr. Test (license={doctor.license_number})")
        print(f"      - Test Patient (phone={patient.phone})")
        print(f"      - Age Test Patient (DOB 25 years ago, age={age_test_patient.age})")
        print(f"      - Allergic Patient (allergy_notes='Penicillin allergy')")
        print(f"      - Non-Allergic Patient (allergy_notes='')")
        
        # =====================================================================
        # STEP 7: PRESCRIPTIONS (State Machine)
        # =====================================================================
        print("  [7/7] Creating Prescriptions...")
        
        # PENDING prescription with Product A
        pending_prescription, created = Prescription.objects.get_or_create(
            doctor=doctor,
            patient=patient,
            status=Prescription.Status.PENDING,
            prescription_date=today,
        )
        if created:
            PrescriptionItem.objects.create(
                prescription=pending_prescription,
                product=product_a,
                quantity_prescribed=20
            )
        
        # VERIFIED prescription with Product A (for successful sale test)
        verified_prescription, created = Prescription.objects.get_or_create(
            doctor=doctor,
            patient=patient,
            status=Prescription.Status.VERIFIED,
            prescription_date=today,
            verified_by=pharmacist_user,
        )
        if created:
            PrescriptionItem.objects.create(
                prescription=verified_prescription,
                product=product_a,
                quantity_prescribed=30
            )
        
        # VERIFIED prescription for expired product test
        expired_rx_prescription, created = Prescription.objects.get_or_create(
            doctor=doctor,
            patient=patient,
            status=Prescription.Status.VERIFIED,
            prescription_date=today,
            verified_by=pharmacist_user,
        )
        if created:
            PrescriptionItem.objects.create(
                prescription=expired_rx_prescription,
                product=product_b,  # Expired product
                quantity_prescribed=20
            )
        
        print(f"      - PENDING prescription (id={pending_prescription.id})")
        print(f"      - VERIFIED prescription for Lisinopril (id={verified_prescription.id})")
        print(f"      - VERIFIED prescription for Expired Amoxicillin (id={expired_rx_prescription.id})")
        
        # =====================================================================
        # SUMMARY
        # =====================================================================
        print("")
        print("=" * 60)
        print("Prescription Workflow QA Data Seeding Complete.")
        print("=" * 60)
        print("")
        print("Summary:")
        print(f"  Users:          {User.objects.count()}")
        print(f"  ProductTypes:   {ProductType.objects.count()}")
        print(f"  Categories:     {Category.objects.count()}")
        print(f"  Suppliers:      {Supplier.objects.count()}")
        print(f"  Products:       {Product.objects.count()}")
        print(f"  Doctors:        {Doctor.objects.count()}")
        print(f"  Patients:       {Patient.objects.count()}")
        print(f"  Prescriptions:  {Prescription.objects.count()}")
        print(f"  StockMovements: {StockMovement.objects.count()}")
        print("")
        print("Data prepared for:")
        print("  - test_prescription_workflow_and_remaining.py")
        print("")
        print("Key Test Data:")
        print(f"  - PENDING Rx ID: {pending_prescription.id} (for unverified Rx test)")
        print(f"  - VERIFIED Rx ID: {verified_prescription.id} (for successful sale test)")
        print(f"  - EXPIRED Rx ID: {expired_rx_prescription.id} (for expired product test)")
        print(f"  - Allergic Patient ID: {patient_with_allergies.id}")
        print(f"  - Age Test Patient ID: {age_test_patient.id} (age={age_test_patient.age})")
        print("")



seed_prescription_workflow_data()
