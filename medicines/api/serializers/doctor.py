from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from medicines.core.models import Doctor

class DoctorSerializer(serializers.ModelSerializer):
    prescription_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Doctor
        fields = [
            'id', 'name', 'image', 'license_number', 'phone',
            'clinic_name', 'clinic_address',
            'is_active', 'prescription_count', 'created_at'
        ]

    @extend_schema_field(serializers.IntegerField())
    def get_prescription_count(self, obj):
        return obj.prescriptions.count()