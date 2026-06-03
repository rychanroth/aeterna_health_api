from rest_framework import viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Sum, Count
from medicines.core.models import Sale
from medicines.api.serializers import SaleSerializer
from medicines.api.permissions import IsAdmin, IsCashier
from drf_spectacular.utils import extend_schema, inline_serializer

class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer
    search_fields = ['sale_number', 'notes']

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAdmin | IsCashier]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = Sale.objects.all()
        if self.request.user.role == 'cashier':
            queryset = queryset.filter(cashier=self.request.user)
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        cashier_id = self.request.query_params.get('cashier')
        if cashier_id:
            queryset = queryset.filter(cashier_id=cashier_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(cashier=self.request.user)

    @action(detail=False, methods=['get'])
    def today(self, request):
        today = timezone.now().date()
        sales = self.queryset.filter(created_at__date=today)
        serializer = self.get_serializer(sales, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_sales(self, request):
        sales = self.queryset.filter(cashier=request.user)
        serializer = self.get_serializer(sales, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        responses=inline_serializer(name='SaleReportResponse', fields={'today': serializers.DictField(), 'this_month': serializers.DictField()})
    )
    @action(detail=False, methods=['get'])
    def report(self, request):
        today = timezone.now().date()
        today_sales = Sale.objects.filter(created_at__date=today)
        today_total = today_sales.aggregate(total=Sum('total_amount'), count=Count('id'))
        month_start = today.replace(day=1)
        month_sales = Sale.objects.filter(created_at__date__gte=month_start)
        month_total = month_sales.aggregate(total=Sum('total_amount'), count=Count('id'))
        return Response({
            'today': {'total_sales': today_total['total'] or 0, 'transaction_count': today_total['count'] or 0},
            'this_month': {'total_sales': month_total['total'] or 0, 'transaction_count': month_total['count'] or 0}
        })