from rest_framework import serializers
from .models import *

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']

class SupplierSerializer(serializers.ModelSerializer):

    class Meta:
        model = Supplier
        fields = ['id', 'name', 'phone', 'address']

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

    class Meta:
        model = Medicine
        fields = '__all__'

    # Custom Field Validation
    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0.")
        return value
    
    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Stock cannot be negative.")
        return value
