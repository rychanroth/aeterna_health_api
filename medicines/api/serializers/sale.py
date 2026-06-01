from rest_framework import serializers
from django.db import transaction
from medicines.core.models import Sale, SaleItem, Product, Prescription

class SaleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )

    class Meta:
        model = SaleItem
        fields = [
            'id', 'product_name', 'product_id',
            'quantity', 'unit_price', 'subtotal',
        ]
        read_only_fields = ['id', 'subtotal']
    
    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value
    
    def validate(self, data):
        data = super().validate(data)
        product = data.get('product')

        if product:
            if product.is_expired:
                raise serializers.ValidationError(
                    f"Cannot sell expired products. Expired on {product.expiration_date}"
                )
        return data

class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)
    cashier_name = serializers.SerializerMethodField()
    prescription_id = serializers.PrimaryKeyRelatedField(
        queryset=Prescription.objects.all(),
        source='prescription',
        write_only=True,
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