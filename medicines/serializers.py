from rest_framework import serializers
from .models import *

class CategorySerializer(serializers.Serializer):
    class Meta:
        model = Category
        fields = '__all__'

class MedicineSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True) # Nested Serializer for GET
    category_id = serializers.PrimaryKeyRelatedField( # cat_id for PUT, POST, PATCH, DELETE
        queryset=Category.objects.all(),
        source='category',
        write_only=True
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
