from rest_framework import serializers
from medicines.core.models import User

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['id', 'image', 'username', 'first_name', 'last_name', 'role', 'phone', 'password', 'is_active']
        read_only_fields = ['id']

        
    def create(self, validated_data):
        # Extract password before creating the user instance
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        
        # Hash the password securely
        if password:
            user.set_password(password)
            
        user.save()
        return user

    def update(self, instance, validated_data):
        # Extract password if provided
        password = validated_data.pop('password', None)
        
        # Update other fields
        instance = super().update(instance, validated_data)
        
        # Hash and update password if a new one was provided
        if password:
            instance.set_password(password)
            instance.save()
            
        return instance