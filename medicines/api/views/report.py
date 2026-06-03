from rest_framework import viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, Avg, F, Q, Case, When, Value, DecimalField
from django.utils import timezone
from django.db.models.functions import TruncDate, TruncMonth, Coalesce
from datetime import timedelta
from medicines.core.models import Sale, SaleItem, Product, Prescription
from drf_spectacular.utils import extend_schema, inline_serializer

def safe_int(value, default):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

class ReportViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    # 1. NEW: Unified Dashboard Endpoint (Speeds up home page load)
    @extend_schema(responses=inline_serializer(name='DashboardSummaryResponse', fields={
        'today_sales': serializers.DictField(), 
        'pending_rx': serializers.IntegerField(),
        'low_stock_alerts': serializers.IntegerField(),
        'expiring_soon_alerts': serializers.IntegerField()
    }))
    @action(detail=False, methods=['get'])
    def dashboard_summary(self, request):
        today = timezone.now().date()
        
        # Today's Sales
        today_sales_qs = Sale.objects.filter(created_at__date=today)
        today_sales = today_sales_qs.aggregate(
            total_revenue=Coalesce(Sum('total_amount'), Value(0, output_field=DecimalField())),
            total_transactions=Count('id')
        )
        
        # Alerts
        pending_rx = Prescription.objects.filter(status=Prescription.Status.PENDING).count()
        low_stock = Product.objects.filter(stock_quantity__lt=10, is_active=True).count()
        expiring_soon = Product.objects.filter(
            expiration_date__lte=timezone.now().date() + timedelta(days=30), 
            expiration_date__gt=timezone.now().date(), 
            is_active=True
        ).count()

        return Response({
            'today_sales': {
                'total_revenue': today_sales['total_revenue'],
                'total_transactions': today_sales['total_transactions']
            },
            'pending_rx': pending_rx,
            'low_stock_alerts': low_stock,
            'expiring_soon_alerts': expiring_soon
        })

    # 2. ENHANCED: Added Payment Method Breakdown
    @extend_schema(responses=inline_serializer(name='SalesSummaryResponse', fields={'summary': serializers.DictField(), 'daily_breakdown': serializers.ListField(child=serializers.DictField()), 'payment_breakdown': serializers.ListField(child=serializers.DictField())}))
    @action(detail=False, methods=['get'])
    def sales_summary(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        sales = Sale.objects.all()
        if start_date:
            sales = sales.filter(created_at__date__gte=start_date)
        if end_date:
            sales = sales.filter(created_at__date__lte=end_date)
            
        summary = sales.aggregate(total_sales=Count('id'), total_revenue=Sum('total_amount'), avg_transaction=Avg('total_amount'))
        daily_sales = sales.annotate(date=TruncDate('created_at')).values('date').annotate(sales_count=Count('id'), revenue=Sum('total_amount')).order_by('date')
        
        # NEW: Payment Method Breakdown for reconciliation
        payment_breakdown = sales.values('payment_method').annotate(
            count=Count('id'), 
            total=Sum('total_amount')
        ).order_by('payment_method')

        return Response({
            'summary': {'total_sales': summary['total_sales'] or 0, 'total_revenue': summary['total_revenue'] or 0, 'average_transaction': round(summary['avg_transaction'] or 0, 2)},
            'daily_breakdown': list(daily_sales),
            'payment_breakdown': list(payment_breakdown)
        })

    # 3. ENHANCED: Added Date Filtering to Top Products
    @extend_schema(responses=inline_serializer(name='TopProductsResponse', fields={'top_products': serializers.ListField(child=serializers.DictField())}))
    @action(detail=False, methods=['get'])
    def top_products(self, request):
        limit = safe_int(request.query_params.get('limit'), 10)
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        items = SaleItem.objects.all()
        if start_date:
            items = items.filter(sale__created_at__date__gte=start_date)
        if end_date:
            items = items.filter(sale__created_at__date__lte=end_date)

        top_items = items.values('product__id', 'product__name', 'product__product_type__name').annotate(total_quantity=Sum('quantity'), total_revenue=Sum(F('quantity') * F('unit_price'))).order_by('-total_quantity')[:limit]
        return Response({'top_products': list(top_items)})

    # 4. FIX: Aligned low_threshold default to 10
    @extend_schema(responses=inline_serializer(name='StockAlertsResponse', fields={'low_stock': serializers.ListField(child=serializers.DictField()), 'expiring_soon': serializers.ListField(child=serializers.DictField()), 'expired': serializers.ListField(child=serializers.DictField()), 'thresholds': serializers.DictField()}))
    @action(detail=False, methods=['get'])
    def stock_alerts(self, request):
        low_threshold = safe_int(request.query_params.get('low_threshold'), 10) # Changed from 50 to 10
        days_ahead = safe_int(request.query_params.get('days_ahead'), 90)
        expiry_cutoff_date = timezone.now().date() + timedelta(days=days_ahead)
        low_stock = Product.objects.filter(stock_quantity__lte=low_threshold, is_active=True).values('id', 'name', 'stock_quantity', 'base_unit', 'product_type__name')
        expiring_soon = Product.objects.filter(expiration_date__lte=expiry_cutoff_date, expiration_date__gt=timezone.now().date(), is_active=True).values('id', 'name', 'expiration_date', 'stock_quantity', 'product_type__name')
        expired = Product.objects.filter(expiration_date__lt=timezone.now().date(), is_active=True).values('id', 'name', 'expiration_date', 'stock_quantity', 'product_type__name')
        return Response({'low_stock': list(low_stock), 'expiring_soon': list(expiring_soon), 'expired': list(expired), 'thresholds': {'low_stock': low_threshold, 'expiry_days': days_ahead}})

    # ... prescription_stats, monthly_revenue, product_type_breakdown remain exactly the same ...