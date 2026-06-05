# medicines/api/serializers/batch.py
from rest_framework import serializers
from medicines.core.models import Batch, Product, Supplier
from rest_framework.permissions import *

class BatchSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')
    supplier_name = serializers.ReadOnlyField(source='supplier.name')
    is_expired = serializers.BooleanField(read_only=True)
    
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )
    supplier_id = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.all(), source='supplier', write_only=True, allow_null=True, required=False
    )

    class Meta:
        model = Batch
        fields = [
            'id', 'batch_number', 'product', 'product_id', 'product_name',
            'quantity', 'expiration_date', 'cost_price', 'received_date',
            'supplier', 'supplier_id', 'supplier_name',
            'is_expired', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'batch_number', 'created_at']
