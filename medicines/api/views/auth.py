from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework import status, serializers
from django.contrib.auth import authenticate
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiResponse

@extend_schema(
    tags=['Auth'],
    request=inline_serializer(
        name='LoginRequest',
        fields={
            'username': serializers.CharField(),
            'password': serializers.CharField(),
        }
    ),
    responses={
        200: inline_serializer(
            name='LoginResponse',
            fields={
                'token': serializers.CharField(),
                'user_id': serializers.IntegerField(),
                'username': serializers.CharField(),
            }
        ),
        401: OpenApiResponse(description='Invalid Credentials')
    },
    auth=None
)
@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def login(request):
    """Exchage username/password for auth token"""
    username = request.data.get('username')
    password = request.data.get('password')

    user = authenticate(username=username, password=password)

    if user:
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.id,
            'username': user.username
        })
    return Response({'error': 'Invalid Credentials'}, status=status.HTTP_401_UNAUTHORIZED)