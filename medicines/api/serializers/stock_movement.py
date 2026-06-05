from rest_framework import serializers
from medicines.core.models import StockMovement, Batch, Supplier, Sale
class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='batch.product.name')
    batch_number = serializers.ReadOnlyField(source='batch.batch_number')
    supplier_name = serializers.ReadOnlyField(source='supplier.name')
    sale_number = serializers.ReadOnlyField(source='sale.sale_number')
    created_by_name = serializers.SerializerMethodField()
    is_stock_in = serializers.BooleanField(read_only=True)
    is_stock_out = serializers.BooleanField(read_only=True)
    movement_direction = serializers.ReadOnlyField()
    
    # NEW: Target Batch, not Product
    batch_id = serializers.PrimaryKeyRelatedField(
        queryset=Batch.objects.all(),
        source='batch',
        write_only=True
    )
    supplier_id = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.all(), source='supplier', write_only=True, allow_null=True, required=False
    )
    sale_id = serializers.PrimaryKeyRelatedField(
        queryset=Sale.objects.all(), source='sale', write_only=True, allow_null=True, required=False
    )
    
    class Meta:
        model = StockMovement
        fields = [
            'id', 'product_name', 'batch_number', 'batch_id',
            'movement_type', 'quantity',
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

        # FIX: Target the Batch, not the Product
        batch = data.get('batch')
        movement_type = data.get('movement_type')
        quantity = data.get('quantity', 0)

        if movement_type and quantity:
            out_reasons = [r.value for r in StockMovement.Reason.get_out_reasons()]

            if movement_type in out_reasons:
                if batch and batch.quantity < quantity:
                    raise serializers.ValidationError(
                        f"Insufficient stock in Batch {batch.batch_number}. Available: {batch.quantity}"
                    )

        return data

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)