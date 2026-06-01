from medicines.core.models import ProductType, Category, Supplier, Product, StockMovement
from decimal import Decimal
from datetime import date, timedelta


def seed_recursive_data():
    """
    Seed data with proper business flow:
    1. Create ProductTypes
    2. Create Categories (recursive)
    3. Create Suppliers
    4. Create Products (stock_quantity = 0)
    5. Create StockMovements (purchase) to add stock
    """
    
    today = date.today()
    
    # ============================================
    # STEP 1: Create ProductTypes
    # ============================================
    
    print("\n" + "="*70)
    print("STEP 1: Creating ProductTypes...")
    print("="*70)
    
    product_types = {
        'Medicine': ProductType.objects.get_or_create(
            name='Medicine',
            defaults={
                'description': 'Pharmaceutical drugs and medications',
                'requires_expiration': True,
                'requires_prescription': True,
            }
        )[0],
        'Medical Equipment': ProductType.objects.get_or_create(
            name='Medical Equipment',
            defaults={
                'description': 'Medical devices and supplies',
                'requires_expiration': False,
                'requires_prescription': False,
            }
        )[0],
    }
    
    print(f"✓ ProductTypes: {ProductType.objects.count()}")
    
    # ============================================
    # STEP 2: Create Hierarchical Categories
    # ============================================
    
    print("\n" + "="*70)
    print("STEP 2: Creating Categories (Recursive)...")
    print("="*70)
    
    category_tree = {
        'Medicine': {
            'Cardiovascular': {
                'Antihypertensives': {
                    'ACE Inhibitors': {},
                    'Beta Blockers': {},
                    'Calcium Channel Blockers': {},
                },
                'Anticoagulants': {
                    'Warfarin Derivatives': {},
                    'Direct Oral Anticoagulants': {},
                },
                'Statins': {},
            },
            'Central Nervous System': {
                'Analgesics': {
                    'Opioids': {},
                    'NSAIDs': {},
                },
                'Antidepressants': {
                    'SSRIs': {},
                    'SNRIs': {},
                },
                'Anticonvulsants': {},
            },
            'Anti-Infective': {
                'Antibiotics': {
                    'Penicillins': {},
                    'Cephalosporins': {},
                    'Fluoroquinolones': {},
                },
                'Antivirals': {
                    'HIV Antiretrovirals': {},
                    'Influenza Agents': {},
                },
                'Antifungals': {},
            },
            'Respiratory': {
                'Bronchodilators': {
                    'Short-Acting': {},
                    'Long-Acting': {},
                },
                'Corticosteroids': {
                    'Inhaled': {},
                    'Systemic': {},
                },
            },
            'Gastrointestinal': {
                'Antacids': {
                    'Calcium Carbonate': {},
                    'Magnesium-Based': {},
                },
                'Proton Pump Inhibitors': {},
                'H2 Blockers': {},
            },
        },
        'Medical Equipment': {
            'Diagnostic Tools': {
                'Blood Pressure Monitors': {},
                'Glucose Meters': {},
                'Thermometers': {},
            },
            'Wound Care': {
                'Dressings': {
                    'Gauze': {},
                    'Hydrocolloid': {},
                },
                'Bandages': {},
            },
            'Mobility Aids': {
                'Walking Aids': {},
                'Wheelchairs': {},
            },
        },
    }
    
    categories = {}
    
    def create_categories_recursive(tree, product_type, parent=None, path=''):
        """Recursively create categories from nested dict"""
        for name, children in tree.items():
            full_path = f"{path} > {name}" if path else name
            category, created = Category.objects.get_or_create(
                name=name,
                product_type=product_type,
                parent=parent
            )
            categories[full_path] = category
            print(f"  {'✓' if created else '○'} {category.full_path} (Depth: {category.depth})")
            if children:
                create_categories_recursive(children, product_type, category, full_path)
    
    for type_name, tree in category_tree.items():
        create_categories_recursive(tree, product_types[type_name])
    
    print(f"\n✓ Total Categories: {Category.objects.count()}")
    
    # ============================================
    # STEP 3: Create Suppliers
    # ============================================
    
    print("\n" + "="*70)
    print("STEP 3: Creating Suppliers...")
    print("="*70)
    
    suppliers = {
        'PharmaCorp': Supplier.objects.get_or_create(
            name='PharmaCorp International',
            defaults={'phone': '+1-555-0100', 'address': '100 Medical Drive, Boston, MA'}
        )[0],
        'MedEquip': Supplier.objects.get_or_create(
            name='MedEquip Solutions',
            defaults={'phone': '+1-555-0200', 'address': '200 Equipment Lane, Chicago, IL'}
        )[0],
        'GlobalMeds': Supplier.objects.get_or_create(
            name='GlobalMeds Distribution',
            defaults={'phone': '+1-555-0300', 'address': '300 Pharma Boulevard, New York, NY'}
        )[0],
    }
    
    print(f"✓ Suppliers: {Supplier.objects.count()}")
    
    # ============================================
    # STEP 4: Create Products (stock_quantity = 0)
    # ============================================
    
    print("\n" + "="*70)
    print("STEP 4: Creating Products (initial stock = 0)...")
    print("="*70)
    
    # Products data - NO buying_price (it's stored in StockMovement.unit_cost)
    products_data = [
        # ===== CARDIOVASCULAR - ACE Inhibitors =====
        {
            'name': 'Lisinopril 10mg',
            'category_path': 'Cardiovascular > Antihypertensives > ACE Inhibitors',
            'base_unit': 'tablet',
            'selling_price': Decimal('8.50'),
            'description': 'ACE inhibitor for hypertension and heart failure',
            'expiration_date': today + timedelta(days=730),
            'requires_prescription': True,
            'supplier': 'PharmaCorp',
            'purchase_quantity': 500,
            'unit_cost': Decimal('5.00'),
        },
        {
            'name': 'Enalapril 5mg',
            'category_path': 'Cardiovascular > Antihypertensives > ACE Inhibitors',
            'base_unit': 'tablet',
            'selling_price': Decimal('6.00'),
            'description': 'ACE inhibitor for high blood pressure',
            'expiration_date': today + timedelta(days=600),
            'requires_prescription': True,
            'supplier': 'PharmaCorp',
            'purchase_quantity': 300,
            'unit_cost': Decimal('3.50'),
        },
        {
            'name': 'Ramipril 2.5mg',
            'category_path': 'Cardiovascular > Antihypertensives > ACE Inhibitors',
            'base_unit': 'tablet',
            'selling_price': Decimal('7.00'),
            'description': 'ACE inhibitor for cardiovascular protection',
            'expiration_date': today + timedelta(days=550),
            'requires_prescription': True,
            'supplier': 'GlobalMeds',
            'purchase_quantity': 250,
            'unit_cost': Decimal('4.00'),
        },
        
        # ===== CARDIOVASCULAR - Beta Blockers =====
        {
            'name': 'Metoprolol 50mg',
            'category_path': 'Cardiovascular > Antihypertensives > Beta Blockers',
            'base_unit': 'tablet',
            'selling_price': Decimal('7.50'),
            'description': 'Beta blocker for hypertension and angina',
            'expiration_date': today + timedelta(days=550),
            'requires_prescription': True,
            'supplier': 'PharmaCorp',
            'purchase_quantity': 400,
            'unit_cost': Decimal('4.50'),
        },
        {
            'name': 'Atenolol 25mg',
            'category_path': 'Cardiovascular > Antihypertensives > Beta Blockers',
            'base_unit': 'tablet',
            'selling_price': Decimal('5.50'),
            'description': 'Cardioselective beta blocker',
            'expiration_date': today + timedelta(days=480),
            'requires_prescription': True,
            'supplier': 'GlobalMeds',
            'purchase_quantity': 350,
            'unit_cost': Decimal('3.00'),
        },
        
        # ===== CARDIOVASCULAR - Anticoagulants =====
        {
            'name': 'Warfarin 5mg',
            'category_path': 'Cardiovascular > Anticoagulants',
            'base_unit': 'tablet',
            'selling_price': Decimal('12.00'),
            'description': 'Oral anticoagulant for blood clot prevention',
            'expiration_date': today + timedelta(days=365),
            'requires_prescription': True,
            'supplier': 'PharmaCorp',
            'purchase_quantity': 200,
            'unit_cost': Decimal('8.00'),
        },
        
        # ===== CNS - Opioids =====
        {
            'name': 'Codeine 30mg',
            'category_path': 'Central Nervous System > Analgesics > Opioids',
            'base_unit': 'tablet',
            'selling_price': Decimal('15.00'),
            'description': 'Opioid analgesic for moderate pain',
            'expiration_date': today + timedelta(days=400),
            'requires_prescription': True,
            'supplier': 'PharmaCorp',
            'purchase_quantity': 150,
            'unit_cost': Decimal('10.00'),
        },
        
        # ===== CNS - NSAIDs =====
        {
            'name': 'Ibuprofen 400mg',
            'category_path': 'Central Nervous System > Analgesics > NSAIDs',
            'base_unit': 'tablet',
            'selling_price': Decimal('5.00'),
            'description': 'NSAID for pain and inflammation (OTC)',
            'expiration_date': today + timedelta(days=730),
            'requires_prescription': False,
            'supplier': 'PharmaCorp',
            'purchase_quantity': 1000,
            'unit_cost': Decimal('2.00'),
        },
        {
            'name': 'Naproxen 250mg',
            'category_path': 'Central Nervous System > Analgesics > NSAIDs',
            'base_unit': 'tablet',
            'selling_price': Decimal('6.50'),
            'description': 'Long-acting NSAID for arthritis pain',
            'expiration_date': today + timedelta(days=600),
            'requires_prescription': False,
            'supplier': 'GlobalMeds',
            'purchase_quantity': 400,
            'unit_cost': Decimal('3.50'),
        },
        
        # ===== CNS - SSRIs =====
        {
            'name': 'Sertraline 50mg',
            'category_path': 'Central Nervous System > Antidepressants > SSRIs',
            'base_unit': 'tablet',
            'selling_price': Decimal('18.00'),
            'description': 'SSRI antidepressant for depression and anxiety',
            'expiration_date': today + timedelta(days=500),
            'requires_prescription': True,
            'supplier': 'PharmaCorp',
            'purchase_quantity': 250,
            'unit_cost': Decimal('12.00'),
        },
        
        # ===== ANTI-INFECTIVE - Penicillins =====
        {
            'name': 'Amoxicillin 500mg',
            'category_path': 'Anti-Infective > Antibiotics > Penicillins',
            'base_unit': 'capsule',
            'selling_price': Decimal('10.00'),
            'description': 'Broad-spectrum penicillin antibiotic',
            'expiration_date': today + timedelta(days=365),
            'requires_prescription': True,
            'supplier': 'PharmaCorp',
            'purchase_quantity': 600,
            'unit_cost': Decimal('6.00'),
        },
        
        # ===== ANTI-INFECTIVE - Cephalosporins =====
        {
            'name': 'Cephalexin 250mg',
            'category_path': 'Anti-Infective > Antibiotics > Cephalosporins',
            'base_unit': 'capsule',
            'selling_price': Decimal('14.00'),
            'description': 'First-generation cephalosporin antibiotic',
            'expiration_date': today + timedelta(days=450),
            'requires_prescription': True,
            'supplier': 'PharmaCorp',
            'purchase_quantity': 350,
            'unit_cost': Decimal('9.00'),
        },
        
        # ===== RESPIRATORY - Short-Acting =====
        {
            'name': 'Albuterol Inhaler 90mcg',
            'category_path': 'Respiratory > Bronchodilators > Short-Acting',
            'base_unit': 'piece',
            'selling_price': Decimal('25.00'),
            'description': 'Rescue inhaler for acute asthma symptoms',
            'expiration_date': today + timedelta(days=365),
            'requires_prescription': True,
            'supplier': 'PharmaCorp',
            'purchase_quantity': 100,
            'unit_cost': Decimal('15.00'),
        },
        
        # ===== RESPIRATORY - Inhaled Corticosteroids =====
        {
            'name': 'Fluticasone Inhaler 110mcg',
            'category_path': 'Respiratory > Corticosteroids > Inhaled',
            'base_unit': 'piece',
            'selling_price': Decimal('45.00'),
            'description': 'Inhaled corticosteroid for asthma maintenance',
            'expiration_date': today + timedelta(days=400),
            'requires_prescription': True,
            'supplier': 'GlobalMeds',
            'purchase_quantity': 80,
            'unit_cost': Decimal('30.00'),
        },
        
        # ===== GI - Antacids =====
        {
            'name': 'Calcium Carbonate 500mg',
            'category_path': 'Gastrointestinal > Antacids > Calcium Carbonate',
            'base_unit': 'tablet',
            'selling_price': Decimal('4.00'),
            'description': 'Antacid for heartburn relief (OTC)',
            'expiration_date': today + timedelta(days=730),
            'requires_prescription': False,
            'supplier': 'PharmaCorp',
            'purchase_quantity': 800,
            'unit_cost': Decimal('1.50'),
        },
        
        # ===== EQUIPMENT - BP Monitors =====
        {
            'name': 'Digital Blood Pressure Monitor',
            'category_path': 'Diagnostic Tools > Blood Pressure Monitors',
            'base_unit': 'piece',
            'selling_price': Decimal('75.00'),
            'description': 'Automatic digital BP monitor for home use',
            'expiration_date': None,
            'requires_prescription': False,
            'supplier': 'MedEquip',
            'purchase_quantity': 30,
            'unit_cost': Decimal('45.00'),
        },
        
        # ===== EQUIPMENT - Glucose Meters =====
        {
            'name': 'Blood Glucose Monitor Kit',
            'category_path': 'Diagnostic Tools > Glucose Meters',
            'base_unit': 'set',
            'selling_price': Decimal('45.00'),
            'description': 'Complete glucose monitoring kit with strips',
            'expiration_date': None,
            'requires_prescription': False,
            'supplier': 'MedEquip',
            'purchase_quantity': 50,
            'unit_cost': Decimal('25.00'),
        },
        
        # ===== EQUIPMENT - Gauze =====
        {
            'name': 'Sterile Gauze Pads 4x4 (100pk)',
            'category_path': 'Wound Care > Dressings > Gauze',
            'base_unit': 'pack',
            'selling_price': Decimal('8.00'),
            'description': 'Sterile gauze pads for wound dressing',
            'expiration_date': today + timedelta(days=1095),
            'requires_prescription': False,
            'supplier': 'MedEquip',
            'purchase_quantity': 200,
            'unit_cost': Decimal('4.00'),
        },
    ]
    
    # Create products with stock_quantity = 0
    created_products = []
    for prod_data in products_data:
        category_path = prod_data.pop('category_path')
        supplier_name = prod_data.pop('supplier')
        purchase_quantity = prod_data.pop('purchase_quantity')
        unit_cost = prod_data.pop('unit_cost')
        
        category = categories[category_path]
        
        # Create product with stock = 0
        product, created = Product.objects.get_or_create(
            name=prod_data['name'],
            defaults={
                'product_type': category.product_type,
                'category': category,
                'stock_quantity': 0,
                **prod_data
            }
        )
        product.suppliers.add(suppliers[supplier_name])
        
        created_products.append({
            'product': product,
            'supplier': suppliers[supplier_name],
            'quantity': purchase_quantity,
            'unit_cost': unit_cost,
            'created': created,
        })
        
        print(f"  {'✓' if created else '○'} {product.name} (stock: 0)")
    
    print(f"\n✓ Total Products: {Product.objects.count()}")
    
    # ============================================
    # STEP 5: Create StockMovements (Purchase)
    # ============================================
    
    print("\n" + "="*70)
    print("STEP 5: Creating StockMovements (Purchase - Stock IN)...")
    print("="*70)
    
    for item in created_products:
        movement, created = StockMovement.objects.get_or_create(
            product=item['product'],
            movement_type=StockMovement.Reason.PURCHASE,
            quantity=item['quantity'],
            defaults={
                'suppliers': item['supplier'],
                'unit_cost': item['unit_cost'],
                'notes': f"Initial stock for {item['product'].name}",
            }
        )
        
        item['product'].refresh_from_db()
        print(f"  {'✓' if created else '○'} {item['product'].name}")
        print(f"      Stock: 0 → {item['product'].stock_quantity} via Purchase (unit_cost: ${item['unit_cost']})")
    
    print(f"\n✓ Total StockMovements: {StockMovement.objects.count()}")
    
    # ============================================
    # SUMMARY
    # ============================================
    
    print("\n" + "="*70)
    print("SEED DATA COMPLETE!")
    print("="*70)
    print(f"ProductTypes:     {ProductType.objects.count()}")
    print(f"Categories:       {Category.objects.count()}")
    print(f"Suppliers:        {Supplier.objects.count()}")
    print(f"Products:         {Product.objects.count()}")
    print(f"StockMovements:   {StockMovement.objects.count()}")
    
    # Stock summary
    total_stock = sum(p.stock_quantity for p in Product.objects.all())
    total_value = sum(p.stock_quantity * p.selling_price for p in Product.objects.all())
    print(f"\nTotal Units: {total_stock}")
    print(f"Total Value: ${total_value:,.2f}")


# Run when imported
seed_recursive_data()