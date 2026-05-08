from rest_framework import serializers
from .models import *
from django.db import transaction

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'role', 'phone']
        read_only_fields = ['id']

class CategorySerializer(serializers.ModelSerializer):
    # Read-only
    parent = serializers.StringRelatedField(read_only=True)
    product_type = serializers.StringRelatedField(read_only=True)
    products_count = serializers.SerializerMethodField()
    
    # Write-only
    parent_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source='parent',
        write_only=True,
        allow_null=True,
        required=False
    )
    product_type_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductType.objects.all(),
        source='product_type',
        write_only=True
    )

    class Meta:
        model = Category
        fields = ['id', 'name', 'product_type', 'product_type_id', 'parent', 'parent_id', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_products_count(self, obj):
        return obj.products.count()

class SupplierSerializer(serializers.ModelSerializer):
    products_count = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = ['id', 'name', 'phone', 'address', 'is_active', 'products_count', 'created_at']

    def get_products_count(self, obj):
        return obj.products.count()
    
class ProductTypeSerializer(serializers.ModelSerializer):
    products_count = serializers.SerializerMethodField()
    categories_count = serializers.SerializerMethodField()

    class Meta:
        model = ProductType
        fields = ['id', 'name', 'description',
            'requires_prescription', 'requires_expiration',
            'products_count', 'categories_count',
            'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def get_products_count(self, obj):
        return obj.products.count()
    
    def get_categories_count(self, obj):
        return obj.categories.count()

class ProductSerializer(serializers.ModelSerializer):
    # Nested read-only (GET) for display
    category = CategorySerializer(read_only=True)
    suppliers = SupplierSerializer(many=True, read_only=True)
    product_type = ProductTypeSerializer(read_only=True)

    # Write-only (PUT, POST, PATCH, DELETE) 
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source='category',
        write_only=True,
        allow_null=True,
        required=False
    )
    supplier_ids = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.all(),
        source='suppliers',
        many=True,
        write_only=True,
        required=False
    )
    product_type_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductType.objects.all(),
        source='product_type',
        write_only=True,
        allow_null=True,
        required=False
    )
    is_expired = serializers.ReadOnlyField()
    is_low_stock = serializers.ReadOnlyField()
    effective_requires_prescription = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 
            'product_type', 'product_type_id', 'base_unit',
            'category', 'category_id',
            'suppliers', 'supplier_ids', 'description',
            'selling_price', 'stock_quantity',
            'expiration_date', 'requires_prescription', 'effective_requires_prescription',
            'is_active', 'is_expired', 'is_low_stock',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    # Custom Field Validation
    def validate_selling_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0.")
        return value
    
    def validate(self, data):
        """Validate based on product_type rules"""
        data =  super().validate(data)

        product_type = data.get('product_type') or (self.instance.product_type if self.instance else None)
        expiration_date = data.get('expiration_date')

        # Check expiration requirement based on ProductType
        if product_type and product_type.requires_expiration:
            if not expiration_date:
                raise serializers.ValidationError({
                    'expiration_date': f'Expiration date is required for {product_type.name} products'
                })
            
        return data

class SaleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )

    class Meta:
        model = SaleItem
        fields = [
            'id', 'product_name', 'product_id',
            'quantity', 'unit_price', 'subtotal',
        ]
        read_only_fields = ['id', 'subtotal']
    
    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value
    
    def validate(self, data):
        """Validate product can be sold"""
        data = super().validaet(data)
        product = data.get('product')

        if product:
            if product.is_expired:
                raise serializers.ValidationError(
                    f"Cannot sell expired products. Expired on {product.expiration_date}"
                )
            
            if product.effective_requires_prescription:
                pass
        return data
        

class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)
    cashier_name = serializers.SerializerMethodField()
    prescription_id = serializers.PrimaryKeyRelatedField(
        queryset=Prescription.objects.all(),
        source='prescription',
        write_only=True,
        allow_null=True,
        required=False
    )

    class Meta:
        model = Sale
        fields = [
            'id', 'sale_number', 'cashier', 'cashier_name',
            'prescription', 'prescription_id',
            'items', 'total_amount', 'payment_method',
            'notes', 'created_at',
        ]
        read_only_fields = ['id', 'sale_number', 'total_amount', 'cashier'] 

    def get_cashier_name(self, obj):
        if obj.cashier:
            return obj.cashier.get_full_name() or obj.cashier.username
        return None
    
    # CUSTOM VALIDATION
    def validate(self, data):
        """Validate prescription amounts"""
        items_data = data.get('items', [])
        prescription = data.get('prescription')

        requires_prescription = False
        for item_data in items_data:
            product = item_data.get('product')
            if product and product.requires_prescription:
                requires_prescription = True
                break

        if requires_prescription and not prescription:
            raise serializers.ValidationError(
                "One or more product requires prescription. Please provide prescription."
            )
        
        if prescription:
            if prescription.status != Prescription.Status.VERIFIED:
                raise serializers.ValidationError(
                    f"Prescription must be verified before sale. Current status: {prescription.status}"
                )
            
            # Validate items match prescription
            prescription_products = set(
                item.product_id for item in prescription.items.all()
            )
            sale_products = set(
                item_data.get('product').id for item_data in items_data 
                if item_data.get('product')
            )
            
            # Check if sale items are in prescription
            if not sale_products.issubset(prescription_products):
                raise serializers.ValidationError(
                    "Some products are not in the prescription."
                )
        
        return data
    
    # Custom Create Logic
    @transaction.atomic()
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        
        # Generate sale number
        import datetime
        today = datetime.date.today()
        count = Sale.objects.filter(created_at__date=today).count() + 1
        validated_data['sale_number'] = f"INV-{today.strftime('%Y%m%d')}-{count:04d}"
        
        # Create sale
        sale = Sale.objects.create(**validated_data)
        
        # Create items and deduct stock
        for item_data in items_data:
            SaleItem.objects.create(sale=sale, **item_data)
        
        # Update prescription status if provided
        if sale.prescription:
            sale.prescription.status = Prescription.Status.DISPENSED
            sale.prescription.save(update_fields=['status'])
        
        return sale
    
    @transaction.atomic()
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)

        # Update sale fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update items if provided
        if items_data is not None:
            # Delete existing items
            instance.items.all().delete()
            # Create new items
            for item_data in items_data:
                SaleItem.objects.create(sale=instance, **item_data)

        return instance

class DoctorSerializer(serializers.ModelSerializer):
    prescription_count = serializers.SerializerMethodField()
    class Meta:
        model = Doctor
        fields = [
            'id', 'name', 'license_number', 'phone',
            'clinic_name', 'clinic_address',
            'is_active', 'prescription_count', 'created_at'
        ]
        read_only_fields = []

    def get_prescription_count(self, obj):
        """Count all prescriptions of a doctor"""
        return obj.prescriptions.count()    
    
class PatientSerializer(serializers.ModelSerializer):
    age = serializers.ReadOnlyField()
    prescription_count = serializers.SerializerMethodField()
    class Meta:
        model = Patient
        fields = [
            'id', 'name', 'phone', 'date_of_birth', 'age',
            'gender', 'address', 'allergy_notes',
            'is_active', 'prescription_count', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def get_prescription_count(self, obj):
        """Count all prescriptions of the patient"""
        return obj.prescriptions.count()


class PrescriptionItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )

    class Meta:
        model = PrescriptionItem
        fields = [
            'id', 'product', 'product_name', 'product_id',
            'quantity_prescribed', 'dosage_instructions', 'is_dispensed'
        ]
        read_only_fields = ['id', 'is_dispensed']

class PrescriptionSerializer(serializers.ModelSerializer):
    items = PrescriptionItemSerializer(many=True)
    doctor_name = serializers.ReadOnlyField(source='doctor.name')
    patient_name = serializers.ReadOnlyField(source='patient.name')
    verified_by_name = serializers.SerializerMethodField()
    doctor_id = serializers.PrimaryKeyRelatedField(
        queryset=Doctor.objects.all(),
        source='doctor',
        write_only=True
    )
    patient_id = serializers.PrimaryKeyRelatedField(
        queryset=Patient.objects.all(),
        source='patient',
        write_only=True
    )

    class Meta:
        model = Prescription
        fields = [
            'id', 'prescription_number', 'doctor', 'doctor_name', 'doctor_id',
            'patient', 'patient_name', 'patient_id',
            'prescription_date', 'status',
            'verified_by', 'verified_by_name',
            'items', 'notes', 'created_at'
        ]
        read_only_fields = ['id', 'prescription_number', 'verified_by']

    def get_verified_by_name(self, obj):
        if obj.verified_by:
            return obj.verified_by.get_full_name() or obj.verified_by.username
        return None
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        import datetime
        today = datetime.date.today()
        # Set default prescription_date if not provided
        if 'prescription_date' not in validated_data:
            validated_data['prescription_date'] = today
        
        # Create prescription
        prescription = Prescription.objects.create(**validated_data)
        
        # Create items
        for item_data in items_data:
            PrescriptionItem.objects.create(prescription=prescription, **item_data)
        
        return prescription

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        
        # Update prescription fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update items if provided
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                PrescriptionItem.objects.create(prescription=instance, **item_data)
        
        return instance
    

class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')
    supplier_name = serializers.ReadOnlyField(source='supplier.name')
    sale_number = serializers.ReadOnlyField(source='sale.sale_number')
    created_by_name = serializers.SerializerMethodField()
    is_stock_in = serializers.ReadOnlyField()
    is_stock_out = serializers.ReadOnlyField()
    movement_direction = serializers.ReadOnlyField()
    
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )
    supplier_id = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.all(),
        source='supplier',
        write_only=True,
        allow_null=True,
        required=False
    )
    sale_id = serializers.PrimaryKeyRelatedField(
        queryset=Sale.objects.all(),
        source='sale',
        write_only=True,
        allow_null=True,
        required=False
    )
    class Meta:
        model = StockMovement
        fields = [
            'id', 'product_name', 'product_id',
            'movement_type', 'quantity', 'unit_cost',
            'supplier_name', 'supplier_id',
            'sale_number', 'sale_id',
            'reference', 'notes',
            'is_stock_in', 'is_stock_out', 'movement_direction',
            'created_by', 'created_by_name', 'created_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at']

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username or 'Deleted User'
        return None

    def validate_quantity(self, value):
        """Ensure quantity is positive"""
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value

    def validate(self, data):
        """Validate using model's helper methods"""
        data = super().validate(data)

        product = data.get('product') or (self.instance.product if self.instance else None)
        movement_type = data.get('movement_type')
        quantity = data.get('quantity', 0)
        
        # Check stock for OUT reasons
        if movement_type and quantity:
            out_reasons = [r.value for r in StockMovement.Reason.get_out_reasons()]
            
            if movement_type in out_reasons:
                if product and product.stock_quantity < quantity:
                    raise serializers.ValidationError(
                        f"Insufficient stock. Available: {product.stock_quantity} {product.base_unit} (s)"
                    )
        
        return data

    def create(self, validated_data):
        # Auto-set created_by
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)