from rest_framework import serializers
from .models import *

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'role', 'phone']
        read_only_fields = ['id']

class CategorySerializer(serializers.ModelSerializer):
    # Read-only
    parent = serializers.StringRelatedField(read_only=True)
    
    # Write-only
    parent_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source='parent',
        write_only=True,
        allow_null=True,
        required=False
    )

    class Meta:
        model = Category
        fields = ['id', 'name', 'parent', 'parent_id']

class SupplierSerializer(serializers.ModelSerializer):
    medicines_count = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = ['id', 'name', 'phone', 'address', 'is_active', 'medicines_count', 'created_at']

    def get_medicines_count(self, obj):
        return obj.medicines.count()

class MedicineSerializer(serializers.ModelSerializer):
    # Nested read-only (GET) for display
    category = CategorySerializer(read_only=True)
    suppliers = SupplierSerializer(many=True, read_only=True)

    # Write-only (PUT, POST, PATCH, DELETE) 
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source='category',
        write_only=True
    )
    supplier_ids = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.all(),
        source='suppliers',
        many=True,
        write_only=True,
        required=True
    )
    is_expired = serializers.ReadOnlyField()
    is_low_stock = serializers.ReadOnlyField()

    class Meta:
        model = Medicine
        fields = [
            'id', 'name', 'category', 'category_id',
            'suppliers', 'supplier_ids',
            'selling_price', 'stock_quantity',
            'expiration_date', 'requires_prescription',
            'is_active', 'is_expired', 'is_low_stock',
            'created_at'
        ]

    # Custom Field Validation
    def validate_selling_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0.")
        return value
    
    def validate_stock_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Stock cannot be negative.")
        return value

class SaleItemSerializer(serializers.ModelSerializer):
    medicine_name = serializers.ReadOnlyField(source='medicine.name')
    medicine_id = serializers.PrimaryKeyRelatedField(
        queryset=Medicine.objects.all(),
        source='medicine',
        write_only=True
    )

    class Meta:
        model = SaleItem
        fields = [
            'id', 'medicine_name', 'medicine_id',
            'quantity', 'unit_price', 'subtotal',
        ]
        read_only_fields = ['id', 'subtotal']

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
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')

        # Create sale
        sale = Sale.objects.create(**validated_data)

        # Create items
        for item_data in items_data:
            SaleItem.objects.create(sale=sale, **item_data)

        return sale
    
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
    medicine_name = serializers.ReadOnlyField(source='medicine.name')
    medicine_id = serializers.PrimaryKeyRelatedField(
        queryset=Medicine.objects.all(),
        source='medicine',
        write_only=True
    )

    class Meta:
        model = PrescriptionItem
        fields = [
            'id', 'medicine', 'medicine_name', 'medicine_id',
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