from rest_framework import serializers
from django.db import transaction
from medicines.core.models import Prescription, PrescriptionItem, Product, Doctor, Patient, Batch

class PrescriptionItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')
    batch_number = serializers.ReadOnlyField(source='batch.batch_number')
    
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )
    
    # NEW: Batch assignment (for dispensing)
    batch_id = serializers.PrimaryKeyRelatedField(
        queryset=Batch.objects.all(),
        source='batch',
        write_only=True,
        allow_null=True,
        required=False # Not required when just writing the Rx
    )

    class Meta:
        model = PrescriptionItem
        fields = [
            'id', 'product', 'product_name', 'product_id',
            'batch_number', 'batch_id',
            'quantity_prescribed', 'dosage_instructions', 'is_dispensed'
        ]
        read_only_fields = ['id', 'is_dispensed', 'product', 'product_name', 'batch_number']

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
            'id', 'prescription_number', 'doctor_name', 'doctor_id',
            'patient_name', 'patient_id',
            'prescription_date', 'status',
            'verified_by', 'verified_by_name',
            'items', 'notes', 'created_at'
        ]
        read_only_fields = ['id', 'prescription_number', 'verified_by']

    def get_verified_by_name(self, obj):
        if obj.verified_by:
            return obj.verified_by.get_full_name() or obj.verified_by.username
        return None
    
    @transaction.atomic # CRITICAL: Prevents orphaned prescriptions if item creation fails
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        import datetime
        today = datetime.date.today()
        if 'prescription_date' not in validated_data:
            validated_data['prescription_date'] = today
        
        prescription = Prescription.objects.create(**validated_data)
        
        for item_data in items_data:
            PrescriptionItem.objects.create(prescription=prescription, **item_data)
        
        return prescription

    @transaction.atomic # CRITICAL: Prevents partial updates
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                PrescriptionItem.objects.create(prescription=instance, **item_data)
        
        return instance