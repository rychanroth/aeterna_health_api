from rest_framework import viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum
from medicines.core.models import StockMovement
from medicines.api.serializers import StockMovementSerializer
from medicines.api.permissions import IsAdmin, IsPharmacist
from medicines.api.filters import StockMovementFilter
from drf_spectacular.utils import extend_schema, inline_serializer

class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = StockMovement.objects.select_related('batch__product', 'supplier', 'sale').all()
    serializer_class = StockMovementSerializer
    search_fields = ['batch__product__name', 'batch__batch_number', 'supplier__name', 'reference']
    filterset_class = StockMovementFilter

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAdmin | IsPharmacist]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['get'])
    def stock_in(self, request):
        in_reasons = [r.value for r in StockMovement.Reason.get_in_reasons()]
        movements = self.get_queryset().filter(movement_type__in=in_reasons)
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
        queryset = self.get_queryset()
        in_reasons = [r.value for r in StockMovement.Reason.get_in_reasons()]
        out_reasons = [r.value for r in StockMovement.Reason.get_out_reasons()]
        total_in = queryset.filter(movement_type__in=in_reasons).aggregate(total=Sum('quantity'))['total'] or 0
        total_out = queryset.filter(movement_type__in=out_reasons).aggregate(total=Sum('quantity'))['total'] or 0
        return Response({'total_in': total_in, 'total_out': total_out, 'net_change': total_in - total_out})