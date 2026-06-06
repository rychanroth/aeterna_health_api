from rest_framework import serializers
from django.db import transaction
from medicines.core.models import Sale, SaleItem, Product, Prescription, Batch

class SaleItemSerializer(serializers.ModelSerializer):
    # Read-only expansions for display
    product_name = serializers.ReadOnlyField(source='product.name')
    batch_number = serializers.ReadOnlyField(source='batch.batch_number')
    
    # Write-only relational IDs
    # We now target the Batch, not the Product directly
    batch_id = serializers.PrimaryKeyRelatedField(
        queryset=Batch.objects.all(),
        source='batch',
        write_only=True
    )

    class Meta:
        model = SaleItem
        fields = [
            'id', 'product_name', 'batch_number', 'batch_id',
            'quantity', 'unit_price', 'subtotal',
        ]
        read_only_fields = ['id', 'subtotal', 'product_name', 'batch_number'] # product_name derived in create

    def get_cashier_name(self, obj):
        if obj.cashier:
            return obj.cashier.get_full_name() or obj.cashier.username
        return None

    def validate(self, data):
        data = super().validate(data)
        items_data = data.get('items', [])
        prescription = data.get('prescription')

        requires_prescription = False
        rx_sale_products = set()

        # FIX: Resolve the product from the batch to check prescription requirements
        for item_data in items_data:
            batch = item_data.get('batch')
            if batch:
                product = batch.product
                if product and product.effective_requires_prescription:
                    requires_prescription = True
                    rx_sale_products.add(product.id)

        if requires_prescription and not prescription:
            raise serializers.ValidationError(
                "One or more products require a prescription. Please provide a prescription."
            )

        if prescription:
            if prescription.status != Prescription.Status.VERIFIED:
                raise serializers.ValidationError(
                    f"Prescription must be verified before sale. Current status: {prescription.status}"
                )

            prescription_products = set(
                item.product_id for item in prescription.items.all() if item.product_id
            )

            if not rx_sale_products.issubset(prescription_products):
                raise serializers.ValidationError(
                    "Some products requiring a prescription are not in the provided prescription."
                )

        return data

    def create(self, validated_data):
        # Denormalization: Auto-fill the product from the selected batch
        batch = validated_data.get('batch')
        if batch and 'product' not in validated_data:
            validated_data['product'] = batch.product
            
        return super().create(validated_data)

class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)
    cashier_name = serializers.SerializerMethodField()
    # draw out from prescription field object, and bi-directional
    prescription_id = serializers.IntegerField(
        allow_null=True, 
        required=False
    )

    class Meta:
        model = Sale
        fields = [
            'id', 'sale_number', 'cashier', 'cashier_name',
            'prescription', 'prescription_id',
            'items', 'total_amount', 'payment_method',
            'notes', 'created_at',
        ]
        read_only_fields = ['id', 'sale_number', 'total_amount', 'cashier'] 

    def get_cashier_name(self, obj):
        if obj.cashier:
            return obj.cashier.get_full_name() or obj.cashier.username
        return None
    
    def validate(self, data):
        items_data = data.get('items', [])
        prescription = data.get('prescription')

        requires_prescription = False
        for item_data in items_data:
            product = item_data.get('product')
            if product and product.effective_requires_prescription:
                requires_prescription = True
                break

        if requires_prescription and not prescription:
            raise serializers.ValidationError(
                "One or more products require a prescription. Please provide a prescription."
            )
        
        if prescription:
            if prescription.status != Prescription.Status.VERIFIED:
                raise serializers.ValidationError(
                    f"Prescription must be verified before sale. Current status: {prescription.status}"
                )
            
            prescription_products = set(
                item.product_id for item in prescription.items.all() if item.product_id
            )
            rx_sale_products = set(
                item_data.get('product').id for item_data in items_data 
                if item_data.get('product') and item_data.get('product').effective_requires_prescription
            )
            
            if not rx_sale_products.issubset(prescription_products):
                raise serializers.ValidationError(
                    "Some products requiring a prescription are not in the provided prescription."
                )
        
        return data
    
    @transaction.atomic()
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        sale = Sale.objects.create(**validated_data)
        
        for item_data in items_data:
            SaleItem.objects.create(sale=sale, **item_data)
        
        if sale.prescription:
            sale.prescription.status = Prescription.Status.DISPENSED
            sale.prescription.save(update_fields=['status'])
        
        return sale
    
    @transaction.atomic()
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                SaleItem.objects.create(sale=instance, **item_data)

        return instance