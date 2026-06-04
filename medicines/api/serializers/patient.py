from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from medicines.core.models import Patient

class PatientSerializer(serializers.ModelSerializer):
    age = serializers.IntegerField(read_only=True)
    prescription_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Patient
        fields = [
            'id', 'name', 'image', 'phone', 'date_of_birth', 'age',
            'gender', 'address', 'allergy_notes',
            'is_active', 'prescription_count', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    @extend_schema_field(serializers.IntegerField())
    def get_prescription_count(self, obj):
        return obj.prescriptions.count()