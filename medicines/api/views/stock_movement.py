import datetime
from django.utils import timezone
from rest_framework import viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from medicines.core.models import StockMovement
from medicines.api.serializers import StockMovementSerializer
from medicines.api.permissions import IsAdmin, IsPharmacist
from drf_spectacular.utils import extend_schema, inline_serializer

class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = StockMovement.objects.all()
    serializer_class = StockMovementSerializer
    search_fields = ['product__name', 'supplier', 'reference']

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAdmin | IsPharmacist]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = StockMovement.objects.all()
        product_id = self.request.query_params.get('product')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        movement_type = self.request.query_params.get('movement_type')
        if movement_type:
            queryset = queryset.filter(movement_type=movement_type)
        direction = self.request.query_params.get('direction')
        if direction == 'in':
            in_reasons = [r.value for r in StockMovement.Reason.get_in_reasons()]
            queryset = queryset.filter(movement_type__in=in_reasons)
        elif direction == 'out':
            out_reasons = [r.value for r in StockMovement.Reason.get_out_reasons()]
            queryset = queryset.filter(movement_type__in=out_reasons)
        supplier_id = self.request.query_params.get('supplier')
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)
        sale_id = self.request.query_params.get('sale')
        if sale_id:
            queryset = queryset.filter(sale_id=sale_id)
            
        # FIX: Robust date filtering
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            try:
                start_dt = timezone.make_aware(datetime.datetime.strptime(start_date, '%Y-%m-%d'))
                queryset = queryset.filter(created_at__gte=start_dt)
            except ValueError:
                pass # Ignore invalid date format
        if end_date:
            try:
                # Use __lt the NEXT day to include all times on the end_date
                end_dt = timezone.make_aware(datetime.datetime.strptime(end_date, '%Y-%m-%d') + datetime.timedelta(days=1))
                queryset = queryset.filter(created_at__lt=end_dt)
            except ValueError:
                pass

        return queryset

    @action(detail=False, methods=['get'])
    def stock_in(self, request):
        in_reasons = [r.value for r in StockMovement.Reason.get_in_reasons()]
        movements = self.get_queryset().filter(movement_type__in=in_reasons) # Use get_queryset to respect filters
        serializer = self.get_serializer(movements, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stock_out(self, request):
        out_reasons = [r.value for r in StockMovement.Reason.get_out_reasons()]
        movements = self.get_queryset().filter(movement_type__in=out_reasons)
        serializer = self.get_serializer(movements, many=True)
        return Response(serializer.data)

    @extend_schema(
        responses=inline_serializer(name='StockMovementSummaryResponse', fields={'total_in': serializers.IntegerField(), 'total_out': serializers.IntegerField(), 'net_change': serializers.IntegerField()})
    )
    @action(detail=False, methods=['get'])
    def summary(self, request):
        from django.db.models import Sum
        queryset = self.get_queryset() # Re-use get_queryset to apply all filters automatically!
        
        in_reasons = [r.value for r in StockMovement.Reason.get_in_reasons()]
        out_reasons = [r.value for r in StockMovement.Reason.get_out_reasons()]
        total_in = queryset.filter(movement_type__in=in_reasons).aggregate(total=Sum('quantity'))['total'] or 0
        total_out = queryset.filter(movement_type__in=out_reasons).aggregate(total=Sum('quantity'))['total'] or 0
        return Response({'total_in': total_in, 'total_out': total_out, 'net_change': total_in - total_out})

    @action(detail=False, methods=['get'])
    def stock_in(self, request):
        in_reasons = [r.value for r in StockMovement.Reason.get_in_reasons()]
        movements = self.queryset.filter(movement_type__in=in_reasons)
        serializer = self.get_serializer(movements, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stock_out(self, request):
        out_reasons = [r.value for r in StockMovement.Reason.get_out_reasons()]
        movements = self.queryset.filter(movement_type__in=out_reasons)
        serializer = self.get_serializer(movements, many=True)
        return Response(serializer.data)

    @extend_schema(
        responses=inline_serializer(name='StockMovementSummaryResponse', fields={'total_in': serializers.IntegerField(), 'total_out': serializers.IntegerField(), 'net_change': serializers.IntegerField()})
    )
    @action(detail=False, methods=['get'])
    def summary(self, request):
        from django.db.models import Sum
        product_id = request.query_params.get('product')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        queryset = StockMovement.objects.all()
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        in_reasons = [r.value for r in StockMovement.Reason.get_in_reasons()]
        out_reasons = [r.value for r in StockMovement.Reason.get_out_reasons()]
        total_in = queryset.filter(movement_type__in=in_reasons).aggregate(total=Sum('quantity'))['total'] or 0
        total_out = queryset.filter(movement_type__in=out_reasons).aggregate(total=Sum('quantity'))['total'] or 0
        return Response({'total_in': total_in, 'total_out': total_out, 'net_change': total_in - total_out})