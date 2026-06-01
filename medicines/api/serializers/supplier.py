from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from medicines.core.models import Supplier

class SupplierSerializer(serializers.ModelSerializer):
    products_count = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = ['id', 'name', 'image', 'phone', 'address', 'is_active', 'products_count', 'created_at']

    @extend_schema_field(serializers.IntegerField())
    def get_products_count(self, obj):
        return obj.products.count()