"""
Development Database Seeding Command
=====================================

Usage:
    python manage.py seed_dev          # Idempotent seed (safe to run multiple times)
    python manage.py seed_dev --reset  # Wipes DB clean before seeding
"""

from decimal import Decimal
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import transaction
from django.contrib.auth import get_user_model

from medicines.core.models import (
    ProductType, Category, Supplier, Product, Batch, StockMovement,
    Doctor, Patient, Prescription, Sale, SaleItem
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds the database with development and QA data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Wipe the database clean before seeding (uses flush)',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write(self.style.WARNING('Resetting database...'))
            call_command('flush', interactive=False)
            self.stdout.write(self.style.SUCCESS('Database wiped clean.'))

        with transaction.atomic():
            self._seed_users()
            self._seed_product_types_and_categories()
            self._seed_suppliers()
            self._seed_products()
            self._seed_medical_records()
            self._seed_prescriptions()
            self._seed_sales_history()

        self.stdout.write(self.style.SUCCESS('\n✅ Dev database seeded successfully!'))

    # =========================================================================
    # SEED METHODS
    # =========================================================================

    def _seed_users(self):
        self.stdout.write('Seeding Users...')
        self.admin, _ = User.objects.get_or_create(
            username='admin', defaults={'role': 'admin', 'is_staff': True, 'is_superuser': True}
        )
        self.admin.set_password('pass123')
        self.admin.save()

        self.pharmacist, _ = User.objects.get_or_create(
            username='pharmacist', defaults={'role': 'pharmacist', 'is_staff': True}
        )
        self.pharmacist.set_password('pass123')
        self.pharmacist.save()

        self.cashier, _ = User.objects.get_or_create(
            username='cashier', defaults={'role': 'cashier', 'is_staff': True}
        )
        self.cashier.set_password('pass123')
        self.cashier.save()

    def _seed_product_types_and_categories(self):
        self.stdout.write('Seeding Product Types & Categories...')

        # Medicine Hierarchy
        self.med_type, _ = ProductType.objects.get_or_create(
            name='Medicine',
            defaults={'requires_expiration': True, 'requires_prescription': True}
        )

        self.med_cat_root, _ = Category.objects.get_or_create(
            name='Medications', product_type=self.med_type, defaults={'parent': None}
        )
        self.med_cat_anti, _ = Category.objects.get_or_create(
            name='Antibiotics', product_type=self.med_type, defaults={'parent': self.med_cat_root}
        )
        self.med_cat_pain, _ = Category.objects.get_or_create(
            name='Pain Relief', product_type=self.med_type, defaults={'parent': self.med_cat_root}
        )

        # Equipment Hierarchy
        self.equip_type, _ = ProductType.objects.get_or_create(
            name='Equipment',
            defaults={'requires_expiration': False, 'requires_prescription': False}
        )
        self.equip_cat_root, _ = Category.objects.get_or_create(
            name='Medical Devices', product_type=self.equip_type, defaults={'parent': None}
        )
        self.equip_cat_diag, _ = Category.objects.get_or_create(
            name='Diagnostic', product_type=self.equip_type, defaults={'parent': self.equip_cat_root}
        )

    def _seed_suppliers(self):
        self.stdout.write('Seeding Suppliers...')
        self.supplier_a, _ = Supplier.objects.get_or_create(
            name='PharmaCorp', defaults={'phone': '111-111-1111'}
        )
        self.supplier_b, _ = Supplier.objects.get_or_create(
            name='MedSupply Co', defaults={'phone': '222-222-2222'}
        )

    def _seed_products(self):
        self.stdout.write('Seeding Products & Stock...')

        # Medicines
        self.prod_amox = self._create_product_with_stock('Amoxicillin 500mg', self.med_cat_anti, self.med_type, self.supplier_a, Decimal('12.50'), 100, True)
        self.prod_ibuprofen = self._create_product_with_stock('Ibuprofen 200mg', self.med_cat_pain, self.med_type, self.supplier_a, Decimal('8.00'), 150, True)

        # Equipment
        self.prod_thermometer = self._create_product_with_stock('Digital Thermometer', self.equip_cat_diag, self.equip_type, self.supplier_b, Decimal('25.00'), 40, False)

    def _seed_medical_records(self):
        self.stdout.write('Seeding Doctors & Patients...')
        self.doctor, _ = Doctor.objects.get_or_create(
            license_number='SMI123', defaults={'name': 'Dr. Smith'}
        )
        self.patient, _ = Patient.objects.get_or_create(
            name='John Doe', defaults={'phone': '555-000-0000'}
        )

    def _seed_prescriptions(self):
        self.stdout.write('Seeding Prescriptions...')
        # Pending RX
        Prescription.objects.get_or_create(
            prescription_number='RX-SEED-PEND-001',
            defaults={
                'doctor': self.doctor,
                'patient': self.patient,
                'prescription_date': date.today(),
                'status': Prescription.Status.PENDING
            }
        )
        # Verified RX (Ready for checkout test)
        self.verified_rx, _ = Prescription.objects.get_or_create(
            prescription_number='RX-SEED-VERF-001',
            defaults={
                'doctor': self.doctor,
                'patient': self.patient,
                'prescription_date': date.today() - timedelta(days=1),
                'status': Prescription.Status.VERIFIED
            }
        )

    def _seed_sales_history(self):
        self.stdout.write('Seeding Historical Sales...')
        # Only create sales if none exist to prevent massive duplicate data on re-runs
        if Sale.objects.count() == 0:
            # FIX: Fetch the batches associated with the products
            batch_ibuprofen = self.prod_ibuprofen.batches.first()
            batch_thermometer = self.prod_thermometer.batches.first()

            sale1 = Sale.objects.create(cashier=self.cashier, payment_method=Sale.PaymentMethod.CASH)
            SaleItem.objects.create(sale=sale1, batch=batch_ibuprofen, quantity=2, unit_price=self.prod_ibuprofen.selling_price)

            sale2 = Sale.objects.create(cashier=self.admin, payment_method=Sale.PaymentMethod.CARD)
            SaleItem.objects.create(sale=sale2, batch=batch_thermometer, quantity=1, unit_price=self.prod_thermometer.selling_price)

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _create_product_with_stock(self, name, category, p_type, supplier, price, stock_qty, requires_rx):
        product, _ = Product.objects.get_or_create(
            name=name,
            defaults={
                'category': category,
                'product_type': p_type,
                'selling_price': price,
                # REMOVED: 'stock_quantity', 'expiration_date'
                'requires_prescription': requires_rx,
            }
        )
        product.suppliers.add(supplier)

        # FIX: Create a Batch to hold the stock
        cost_price = price * Decimal('0.6')  # Simulate 60% margin
        batch, _ = Batch.objects.get_or_create(
            product=product,
            batch_number=f"BAT-SEED-{product.id}", # Deterministic batch number for idempotency
            defaults={
                'quantity': 0, # Start at 0, movement will increment
                'cost_price': cost_price,
                'supplier': supplier,
                'expiration_date': date.today() + timedelta(days=365) if p_type.requires_expiration else None
            }
        )

        # FIX: Use a unique reference so stock movements aren't duplicated on re-runs
        reference_id = f"SEED-STOCK-{batch.id}"
        StockMovement.objects.get_or_create(
            batch=batch, # FIX: Target batch, not product
            reference=reference_id,
            defaults={
                'movement_type': StockMovement.Reason.PURCHASE,
                'quantity': stock_qty,
                'supplier': supplier,
                # REMOVED: 'unit_cost' (Tracked at Batch level now)
                'created_by': self.admin
            }
        )
        product.refresh_from_db()

        return product