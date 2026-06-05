# medicines/api/views/product_type.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from medicines.core.models import ProductType
from medicines.api.serializers import ProductTypeSerializer, CategorySerializer
from medicines.api.permissions import IsAdmin
from medicines.api.filters import ProductTypeFilter

class ProductTypeViewSet(viewsets.ModelViewSet):
    queryset = ProductType.objects.all()
    serializer_class = ProductTypeSerializer
    search_fields = ['name']
    filterset_class = ProductTypeFilter

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=True, methods=['get'])
    def root_categories(self, request, pk):
        """Get all root categories of a producttype"""
        product_type = self.get_object()
        categories = product_type.categories.filter(parent=None, is_active=True)
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def categories(self, request, pk):
        """Get all categories of a producttype"""
        product_type = self.get_object()
        categories = product_type.categories.filter(is_active=True)
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)

    def get_queryset(self):
        queryset = ProductType.objects.all()

        requires_expiration = self.request.query_params.get('requires_expiration')
        if requires_expiration is not None:
            queryset = queryset.filter(requires_expiration=requires_expiration.lower() == 'true')

        requires_prescription = self.request.query_params.get('requires_prescription')
        if requires_prescription is not None:
            queryset = queryset.filter(requires_prescription=requires_prescription.lower() == 'true')

        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset