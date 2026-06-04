from rest_framework import serializers
from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from medicines.core.models import Category, ProductType
from .product_type import ProductTypeSerializer

class CategorySerializer(serializers.ModelSerializer):
    # Read-only
    full_path = serializers.ReadOnlyField()
    depth = serializers.IntegerField(read_only=True)
    parent_name = serializers.ReadOnlyField(source='parent.name')
    product_type = ProductTypeSerializer(read_only=True)
    product_type_name = serializers.ReadOnlyField(source='product_type.name')

    children = serializers.SerializerMethodField()
    products_count = serializers.SerializerMethodField()
    total_stock = serializers.SerializerMethodField()
    
    # Write-only
    parent_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source='parent',
        write_only=True,
        allow_null=True,
        required=False
    )
    product_type_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductType.objects.all(),
        source='product_type',
        write_only=True,
        allow_null=True,
        required=False
    )

    class Meta:
        model = Category
        fields = [
            'id', 'name', 'image', 'full_path', 'depth',
            'product_type', 'product_type_id', 'product_type_name',
            'parent', 'parent_name', 'parent_id',
            'children',
            'products_count', 'total_stock',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_children(self, obj):
        children = obj.children.filter(is_active=True)
        return CategorySerializer(children, many=True).data

    @extend_schema_field(serializers.IntegerField())
    def get_products_count(self, obj):
        return obj.get_all_products().count()

    @extend_schema_field(serializers.IntegerField())
    def get_total_stock(self, obj):
        return obj.get_total_stock()

    def validate(self, data):
        data = super().validate(data)
        parent = data.get('parent')
        product_type = data.get('product_type')
        instance = self.instance
        
        if parent and product_type:
            if parent.product_type_id != product_type.id:
                raise serializers.ValidationError({
                    'parent_id': f'Parent must belong to the same ProductType. '
                                f'Parent is in "{parent.product_type.name}", '
                                f'but you selected "{product_type.name}".'
                })
        
        if instance and parent:
            if parent.is_descendant_of(instance) or parent.id == instance.id:
                raise serializers.ValidationError({
                    'parent_id': 'Circular reference detected: '
                                'a category cannot be its own ancestor.'
                })
        
        return data

    def update(self, instance, validated_data):
        new_parent = validated_data.get('parent', instance.parent)
        
        if 'parent' in validated_data and new_parent != instance.parent:
            with transaction.atomic():
                return super().update(instance, validated_data)
        
        return super().update(instance, validated_data)