from rest_framework import serializers
from medicines.core.models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'image', 'username', 'first_name', 'last_name', 'role', 'phone']
        read_only_fields = ['id']