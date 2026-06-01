from datetime import timedelta
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from medicines.core.models import Product
from medicines.api.serializers import ProductSerializer
from medicines.api.permissions import IsAdmin, IsPharmacist

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin | IsPharmacist]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = Product.objects.all()
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        category_id = self.request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        product_type_id = self.request.query_params.get('product_type')
        if product_type_id:
            queryset = queryset.filter(product_type_id=product_type_id)
        base_unit = self.request.query_params.get('base_unit')
        if base_unit:
            queryset = queryset.filter(base_unit=base_unit)
        expired = self.request.query_params.get('expired')
        if expired == 'true':
            queryset = queryset.filter(expiration_date__lt=timezone.now().date())
        elif expired == 'false':
            queryset = queryset.filter(expiration_date__gte=timezone.now().date())
        low_stock = self.request.query_params.get('low_stock')
        if low_stock == 'true':
            queryset = queryset.filter(stock_quantity__lt=10) 
        requires_prescription = self.request.query_params.get('requires_prescription')
        if requires_prescription is not None:
            queryset = queryset.filter(requires_prescription=requires_prescription.lower() == 'true')
        type_requires_expiration = self.request.query_params.get('type_requires_expiration')
        if type_requires_expiration is not None:
            queryset = queryset.filter(product_type__requires_expiration=type_requires_expiration.lower() == 'true')
        type_requires_prescription = self.request.query_params.get('type_requires_prescription')
        if type_requires_prescription is not None:
            queryset = queryset.filter(product_type__requires_prescription=type_requires_prescription.lower() == 'true')
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset
    
    def perform_create(self, serializer):
        serializer.save()

    @action(detail=False, methods=['get'])
    def expired(self, request):
        expired = self.queryset.filter(expiration_date__lt=timezone.now().date(), is_active=True)
        serializer = self.get_serializer(expired, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        low_stock = self.queryset.filter(stock_quantity__lt=10, is_active=True)
        serializer = self.get_serializer(low_stock, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        soon = timezone.now().date() + timedelta(days=30)
        expiring = self.queryset.filter(expiration_date__lte=soon, expiration_date__gte=timezone.now().date(), is_active=True)
        serializer = self.get_serializer(expiring, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        product_type_id = request.query_params.get('product_type_id')
        if not product_type_id:
            return Response({"error": "product_type_id is required"}, status=400)
        products = self.get_queryset().filter(product_type_id=product_type_id)
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)