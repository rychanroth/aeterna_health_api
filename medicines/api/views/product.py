# medicines/api/views/product.py
from datetime import timedelta
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Sum, Min, Count, Q, Value, IntegerField, BooleanField, Case, When
from django.db.models.functions import Coalesce
from medicines.core.models import Product
from medicines.api.serializers import ProductSerializer
from medicines.api.permissions import IsAdmin, IsPharmacist
from medicines.api.filters import ProductFilter

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    search_fields = ['name', 'description', 'category__name']
    filterset_class = ProductFilter
    ordering_fields = ['name', 'selling_price', 'total_stock', 'nearest_expiration', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        today = timezone.now().date()
        
        # Standard Annotations with .distinct() to ensure paginator works perfectly
        return Product.objects.select_related('category', 'product_type').annotate(
            # 1. Stock and Expiry Aggregations
            total_stock=Coalesce(
                Sum('batches__quantity', filter=Q(batches__is_active=True)), 
                Value(0, output_field=IntegerField())
            ),
            nearest_expiration=Min('batches__expiration_date', filter=Q(batches__is_active=True)),
            
            # 2. Computed Boolean Aggregations (Prevents N+1 queries on model properties)
            is_low_stock=Case(
                When(total_stock__lt=10, then=Value(True)),
                default=Value(False),
                output_field=BooleanField()
            ),
            # is_expired = Has active batches, but ZERO active batches expiring today or later
            has_active_batches=Count('batches', filter=Q(batches__is_active=True)),
            has_valid_batches=Count('batches', filter=Q(batches__is_active=True, batches__expiration_date__gte=today)),
            is_expired=Case(
                When(has_active_batches__gt=0, has_valid_batches=0, then=Value(True)),
                default=Value(False),
                output_field=BooleanField()
            )
        ).distinct() 

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