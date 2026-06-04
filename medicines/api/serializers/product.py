from rest_framework import serializers
from medicines.core.models import Product, Category, Supplier, ProductType
from .category import CategorySerializer
from .supplier import SupplierSerializer
from .product_type import ProductTypeSerializer

class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    suppliers = SupplierSerializer(many=True, read_only=True)
    product_type = ProductTypeSerializer(read_only=True)

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
    is_expired = serializers.BooleanField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    effective_requires_prescription = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'image', 
            'product_type', 'product_type_id', 'base_unit',
            'category', 'category_id',
            'suppliers', 'supplier_ids', 'description',
            'selling_price', 'stock_quantity',
            'expiration_date', 'requires_prescription', 'effective_requires_prescription',
            'is_active', 'is_expired', 'is_low_stock',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def validate_selling_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0.")
        return value
    
    def validate(self, data):
        data = super().validate(data)
        product_type = data.get('product_type') or (self.instance.product_type if self.instance else None)
        expiration_date = data.get('expiration_date')

        if product_type and product_type.requires_expiration:
            if not expiration_date:
                raise serializers.ValidationError({
                    'expiration_date': f'Expiration date is required for {product_type.name} products'
                })
        return data