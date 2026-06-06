from rest_framework import serializers
from medicines.core.models import StockMovement, Batch, Supplier, Sale, Product
from django.db import transaction
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
        queryset=Batch.objects.all(), source='batch', write_only=True, required=False, allow_null=True
    )
    supplier_id = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.all(), source='supplier', write_only=True, allow_null=True, required=False
    )
    sale_id = serializers.PrimaryKeyRelatedField(
        queryset=Sale.objects.all(), source='sale', write_only=True, allow_null=True, required=False
    )

    # NEW: Fields for auto-creating a Batch during Purchase
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), write_only=True, required=False, allow_null=True
    )
    expiration_date = serializers.DateField(write_only=True, required=False, allow_null=True)
    cost_price = serializers.DecimalField(max_digits=10, decimal_places=2, write_only=True, required=False, allow_null=True)
    received_date = serializers.DateField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = StockMovement
        fields = [
            'id', 'product_name', 'batch_number', 'batch_id',
            'movement_type', 'quantity',
            'supplier_name', 'supplier_id',
            'sale_number', 'sale_id',
            'reference', 'notes',
            'is_stock_in', 'is_stock_out', 'movement_direction',
            'created_by', 'created_by_name', 'created_at',
            # write-only for auto batch generation
            'product_id', 'expiration_date', 'cost_price', 'received_date'
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
        batch = data.get('batch')
        movement_type = data.get('movement_type')
        quantity = data.get('quantity', 0)

        # If no batch is provided, it MUST be a Purchase to auto-create
        if not batch:
            if movement_type != StockMovement.Reason.PURCHASE:
                raise serializers.ValidationError({
                    'batch_id': 'Batch is required for non-purchase movements.'
                })
            if not data.get('product_id'):
                raise serializers.ValidationError({
                    'product_id': 'Product ID is required to auto-create a batch for purchases.'
                })
        
        # If batch IS provided, validate stock out limits
        if batch and quantity:
            out_reasons = [r.value for r in StockMovement.Reason.get_out_reasons()]
            if movement_type in out_reasons:
                if batch.quantity < quantity:
                    raise serializers.ValidationError(
                        f"Insufficient stock in Batch {batch.batch_number}. Available: {batch.quantity}"
                    )
        return data

    def create(self, validated_data):
        # Pop the auto-batch fields before passing to super()
        product = validated_data.pop('product_id', None)
        expiration_date = validated_data.pop('expiration_date', None)
        cost_price = validated_data.pop('cost_price', None)
        received_date = validated_data.pop('received_date', None)
        
        batch = validated_data.get('batch')
        movement_type = validated_data.get('movement_type')

        with transaction.atomic():
            # AUTO-CREATE BATCH LOGIC
            if not batch and movement_type == StockMovement.Reason.PURCHASE and product:
                batch = Batch.objects.create(
                    product=product,
                    quantity=0,  # Starts at 0; StockMovement.save() will increment it
                    expiration_date=expiration_date,
                    cost_price=cost_price,
                    received_date=received_date or datetime.date.today(),
                    supplier=validated_data.get('supplier')
                )
                validated_data['batch'] = batch

            validated_data['created_by'] = self.context['request'].user
            return super().create(validated_data)