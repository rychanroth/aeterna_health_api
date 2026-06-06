# medicines/api/views/product.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Sum, Min, Q, F, Value, IntegerField
from django.db.models.functions import Coalesce
from datetime import timedelta
from medicines.core.models import Product
from medicines.api.serializers import ProductSerializer
from medicines.api.permissions import IsAdmin, IsPharmacist
from medicines.api.filters import ProductFilter

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    search_fields = ['name', 'description']
    filterset_class = ProductFilter
    ordering_fields = ['name', 'selling_price', 'total_stock', 'nearest_expiration', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        # FIX: Use select_related for FKs to prevent N+1 queries during pagination
        return Product.objects.select_related('category', 'product_type').annotate(
            total_stock=Coalesce(Sum('batches__quantity', filter=Q(batches__is_active=True)), Value(0, output_field=IntegerField())),
            nearest_expiration=Min('batches__expiration_date', filter=Q(batches__is_active=True))
        )

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