from .models import *
from .serializers import *
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.permissions import *
from django.contrib.auth import authenticate

@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def login(request):
    """Exchage username/password for auth token"""
    username = request.data.get('username')
    password = request.data.get('password')

    user =  authenticate(username=username, password=password)

    if user:
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.id,
            'username': user.username
        })
    return Response({'error': 'Invalid Credentials'}, status=status.HTTP_401_UNAUTHORIZED)


# ModelViewSet automatically provides list(), create(), retrieve(), update(), partial_update(), destroy()
# When registered with Router, it dynamically generates the URL PATTERNS!
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]

    # === Custom Permissions ===
    def get_permissions(self):
        """Anyone can view, but only authenticated user can add/update/delete"""
        if self.action == 'list' or self.action == 'retrieve':
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    # === Custom Action ===
    # Function name determines the auto-generated url name e.g. /api/categories/roots/
    @action(detail=False, methods=['get'])
    def roots(self, request):
        """Get all root categories (category with no parent)"""
        root_categories = self.queryset.filter(parent__isnull=True)
        serializer = self.get_serializer(root_categories, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def medicines(self, request, pk=None):
        """Get all medicines in this category"""
        category = self.get_object()
        medicines = category.medicines.all()
        serializer = MedicineSerializer(medicines, many=True)
        return Response(serializer.data)

class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated]

class MedicineViewSet(viewsets.ModelViewSet):
    queryset = Medicine.objects.all()
    serializer_class = MedicineSerializer
    permission_classes = [IsAuthenticated]

    # === Custom Permissions ===

    def get_permissions(self):
        # Admin can do all these
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminUser]
        else:
            # Authenticated user could do other than that
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """Filter medicines by search query"""
        queryset = Medicine.objects.all()
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset