from rest_framework import serializers
from .models import *

class MedicineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medicine
        fields = ['id', 'name', 'description', 'price', 'stock', 'created_at']
