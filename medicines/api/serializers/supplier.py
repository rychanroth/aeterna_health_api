from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from medicines.core.models import Supplier

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ['id', 'name', 'image', 'phone', 'address', 'is_active', 'created_at']
