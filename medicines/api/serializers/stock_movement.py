from rest_framework import serializers
from medicines.core.models import StockMovement, Product, Supplier, Sale

class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')
    supplier_name = serializers.ReadOnlyField(source='suppliers.name')
    sale_number = serializers.ReadOnlyField(source='sale.sale_number')
    created_by_name = serializers.SerializerMethodField()
    is_stock_in = serializers.BooleanField(read_only=True)
    is_stock_out = serializers.BooleanField(read_only=True)
    movement_direction = serializers.ReadOnlyField()
    
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )
    supplier_id = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.all(),
        source='suppliers',
        write_only=True,
        allow_null=True,
        required=False
    )
    sale_id = serializers.PrimaryKeyRelatedField(
        queryset=Sale.objects.all(),
        source='sale',
        write_only=True,
        allow_null=True,
        required=False
    )
    
    class Meta:
        model = StockMovement
        fields = [
            'id', 'product_name', 'product_id',
            'movement_type', 'quantity', 'unit_cost',
            'supplier_name', 'supplier_id',
            'sale_number', 'sale_id',
            'reference', 'notes',
            'is_stock_in', 'is_stock_out', 'movement_direction',
            'created_by', 'created_by_name', 'created_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at']

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username or 'Deleted User'
        return None

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value

    def validate(self, data):
        data = super().validate(data)

        product = data.get('product') or (self.instance.product if self.instance else None)
        movement_type = data.get('movement_type')
        quantity = data.get('quantity', 0)
        
        if movement_type and quantity:
            out_reasons = [r.value for r in StockMovement.Reason.get_out_reasons()]
            
            if movement_type in out_reasons:
                if product and product.stock_quantity < quantity:
                    raise serializers.ValidationError(
                        f"Insufficient stock. Available: {product.stock_quantity} {product.base_unit} (s)"
                    )
        
        return data

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)