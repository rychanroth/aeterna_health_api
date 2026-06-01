from rest_framework import viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from medicines.core.models import Category, Product
from medicines.api.serializers import CategorySerializer, ProductSerializer
from medicines.api.permissions import IsAdmin
from drf_spectacular.utils import extend_schema, inline_serializer

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    search_fields = ['name', 'product_type__name']

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'roots', 'products', 'tree', 'descendants', 'ancestors']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['get'])
    def roots(self, request):
        queryset = self.get_queryset().filter(parent__isnull=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def tree(self, request):
        product_type_id = request.query_params.get('product_type')
        if not product_type_id:
            return Response({'error': 'product_type parameter is required'}, status=400)
        roots = Category.objects.filter(product_type_id=product_type_id, parent__isnull=True, is_active=True)
        serializer = self.get_serializer(roots, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def descendants(self, request, pk=None):
        category = self.get_object()
        descendants = category.get_descendants()
        serializer = self.get_serializer(descendants, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def ancestors(self, request, pk=None):
        category = self.get_object()
        ancestors = category.get_ancestors()
        serializer = self.get_serializer(ancestors, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        category = self.get_object()
        products = category.get_all_products().filter(is_active=True)
        page = self.paginate_queryset(products)
        if page is not None:
            serializer = ProductSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)

    @extend_schema(
        responses={200: inline_serializer(name='CategoryStockSummary', fields={'category': serializers.CharField(), 'full_path': serializers.CharField(), 'total_products': serializers.IntegerField(), 'total_stock': serializers.IntegerField(), 'total_value': serializers.FloatField()})}
    )
    @action(detail=True, methods=['get'])
    def stock_summary(self, request, pk=None):
        category = self.get_object()
        return Response({
            'category': category.name,
            'full_path': category.full_path,
            'total_products': category.get_all_products().count(),
            'total_stock': category.get_total_stock(),
            'total_value': category.get_total_value(),
        })

    @extend_schema(
        request=inline_serializer(name='BulkMoveRequest', fields={'category_ids': serializers.ListField(child=serializers.IntegerField()), 'new_parent_id': serializers.IntegerField(required=False, allow_null=True)}),
        responses={200: inline_serializer(name='BulkMoveResponse', fields={'moved': serializers.ListField(child=serializers.IntegerField()), 'errors': serializers.ListField(child=serializers.DictField())})}
    )
    @action(detail=False, methods=['post'])
    def bulk_move(self, request):
        category_ids = request.data.get('category_ids', [])
        new_parent_id = request.data.get('new_parent_id')
        
        if not category_ids:
            return Response({'error': 'category_ids is required'}, status=400)

        new_parent = None
        if new_parent_id:
            try:
                new_parent = Category.objects.get(id=new_parent_id)
            except Category.DoesNotExist:
                return Response({'error': 'New parent category not found'}, status=404)

        with transaction.atomic():
            moved = []
            errors = []
            for cat_id in category_ids:
                try:
                    category = Category.objects.get(id=cat_id)
                    if new_parent and category.product_type_id != new_parent.product_type_id:
                        errors.append({'category_id': cat_id, 'error': 'ProductType mismatch'})
                        continue
                    if new_parent and new_parent.is_descendant_of(category):
                        errors.append({'category_id': cat_id, 'error': 'Would create circular reference'})
                        continue
                    category.parent = new_parent
                    category.save()
                    moved.append(cat_id)
                except Category.DoesNotExist:
                    errors.append({'category_id': cat_id, 'error': 'Category not found'})

        return Response({'moved': moved, 'errors': errors})
    
    def get_queryset(self):
        queryset = Category.objects.all()
        product_type_id = self.request.query_params.get('product_type')
        if product_type_id:
            queryset = queryset.filter(product_type_id=product_type_id)
        depth = self.request.query_params.get('depth')
        if depth:
            category_ids = [c.id for c in Category.objects.all() if c.depth == int(depth)]
            queryset = queryset.filter(id__in=category_ids)
        parent_id = self.request.query_params.get('parent')
        if parent_id:
            if parent_id == 'null':
                queryset = queryset.filter(parent__isnull=True)
            else:
                queryset = queryset.filter(parent_id=parent_id)
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset