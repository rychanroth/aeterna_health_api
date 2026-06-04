from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from medicines.core.models import ProductType

class ProductTypeSerializer(serializers.ModelSerializer):
    products_count = serializers.SerializerMethodField()
    categories_count = serializers.SerializerMethodField()

    class Meta:
        model = ProductType
        fields = ['id', 'name', 'image', 'description',
            'requires_prescription', 'requires_expiration',
            'products_count', 'categories_count',
            'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    @extend_schema_field(serializers.IntegerField())
    def get_products_count(self, obj):
        return obj.products.count()
    
    @extend_schema_field(serializers.IntegerField())
    def get_categories_count(self, obj):
        return obj.categories.count()