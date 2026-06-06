from rest_framework import serializers
from medicines.core.models import Product, Category, ProductType
from .category import CategorySerializer
from .product_type import ProductTypeSerializer

class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    product_type = ProductTypeSerializer(read_only=True)

    category_id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), source='category', write_only=True, allow_null=True, required=False)
    product_type_id = serializers.PrimaryKeyRelatedField(queryset=ProductType.objects.all(), source='product_type', write_only=True, allow_null=True, required=False)

    # REMOVED: is_expired, is_low_stock (Replaced by computed logic below)
    effective_requires_prescription = serializers.BooleanField(read_only=True)
    
    # NEW: Computed fields from Batches
    total_stock = serializers.IntegerField(read_only=True)
    nearest_expiration = serializers.DateField(read_only=True, allow_null=True)
    is_expired = serializers.BooleanField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'image', 'description',
            'product_type', 'product_type_id', 'base_unit',
            'category', 'category_id',
            'selling_price', 'total_stock', 'nearest_expiration',
            'requires_prescription', 'effective_requires_prescription',
            'is_active', 'is_expired', 'is_low_stock',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'total_stock', 'nearest_expiration', 'is_expired', 'is_low_stock']

    def validate_selling_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0.")
        return value

    def validate(self, data):
        data = super().validate(data)
        # FIX: Removed the expiration_date validation. 
        # Expiration is now validated at the Batch level, not Product.
        return data