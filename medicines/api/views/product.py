from datetime import timedelta
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Sum, Min, Q, F, Case, When, BooleanField
from medicines.core.models import Product
from medicines.api.serializers import ProductSerializer
from medicines.api.permissions import IsAdmin, IsPharmacist

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    search_fields = ['name', 'description']

    def get_queryset(self):
        queryset = Product.objects.all()
        
        # Annotate computed fields for DB-level filtering/sorting
        queryset = queryset.annotate(
            total_stock=Sum('batches__quantity', filter=Q(batches__is_active=True)),
            nearest_expiration=Min('batches__expiration_date', filter=Q(batches__is_active=True))
        )

        # Filters
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
            
        category_id = self.request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
            
        expired = self.request.query_params.get('expired')
        if expired == 'true':
            queryset = queryset.filter(nearest_expiration__lt=timezone.now().date())
        elif expired == 'false':
            queryset = queryset.filter(nearest_expiration__gte=timezone.now().date())
            
        low_stock = self.request.query_params.get('low_stock')
        if low_stock == 'true':
            queryset = queryset.filter(total_stock__lt=10)
            
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
            
        return queryset

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin | IsPharmacist]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        qs = self.get_queryset().filter(total_stock__lt=10, is_active=True)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        soon = timezone.now().date() + timedelta(days=30)
        qs = self.get_queryset().filter(
            nearest_expiration__lte=soon, 
            nearest_expiration__gte=timezone.now().date(), 
            is_active=True
        )
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)