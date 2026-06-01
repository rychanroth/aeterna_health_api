from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, Avg, F, Q
from django.utils import timezone
from datetime import timedelta
from medicines.core.models import *
from django.db.models.functions import TruncDate, TruncMonth
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiResponse
from rest_framework import serializers


def safe_int(value, default):
    """Conventional workaround to prevent 500 errors from bad query parameters"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


class ReportViewSet(viewsets.ViewSet):
    """Analytics and reporting endpoints"""
    
    # FIX: Reports contain sensitive business data; restrict to authenticated users
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=inline_serializer(
            name='SalesSummaryResponse',
            fields={
                'summary': serializers.DictField(),
                'daily_breakdown': serializers.ListField(child=serializers.DictField())
            }
        )
    )
    @action(detail=False, methods=['get'])
    def sales_summary(self, request):
        """
        Sales summary with date filtering.
        Usage: /api/reports/sales_summary/?start_date=2024-01-01&end_date=2024-01-31
        """
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        sales = Sale.objects.all()

        if start_date:
            sales = sales.filter(created_at__date__gte=start_date)
        # FIX: Use __date__lte to include the entirety of the end date (previously cut off at 00:00:00)
        if end_date:
            sales = sales.filter(created_at__date__lte=end_date)

        summary = sales.aggregate(
            total_sales=Count('id'),
            total_revenue=Sum('total_amount'),
            avg_transaction=Avg('total_amount')
        )

        daily_sales = (
            sales
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(
                sales_count=Count('id'),
                revenue=Sum('total_amount')
            )
            .order_by('date')
        )

        return Response({
            'summary': {
                'total_sales': summary['total_sales'] or 0,
                'total_revenue': summary['total_revenue'] or 0,
                'average_transaction': round(summary['avg_transaction'] or 0, 2)
            },
            'daily_breakdown': list(daily_sales)
        })

    @extend_schema(
        responses=inline_serializer(
            name='TopProductsResponse',
            fields={
                'top_products': serializers.ListField(child=serializers.DictField())
            }
        )
    )
    @action(detail=False, methods=['get'])
    def top_products(self, request):
        """
        Top selling products by quantity.
        Usage: /api/reports/top_products/?limit=10
        """
        # FIX: Use safe_int to prevent ValueError crash if user passes ?limit=abc
        limit = safe_int(request.query_params.get('limit'), 10)

        top_items = (
            SaleItem.objects
            .values('product__id', 'product__name', 'product__product_type__name')
            .annotate(
                total_quantity=Sum('quantity'),
                total_revenue=Sum(F('quantity') * F('unit_price'))
            )
            .order_by('-total_quantity')[:limit]
        )

        return Response({
            'top_products': list(top_items)
        })

    @extend_schema(
        responses=inline_serializer(
            name='StockAlertsResponse',
            fields={
                'low_stock': serializers.ListField(child=serializers.DictField()),
                'expiring_soon': serializers.ListField(child=serializers.DictField()),
                'expired': serializers.ListField(child=serializers.DictField()),
                'thresholds': serializers.DictField(),
            }
        )
    )
    @action(detail=False, methods=['get'])
    def stock_alerts(self, request):
        """
        Low stock and expiring products alerts.
        Usage: /api/reports/stock_alerts/?low_threshold=50&days_ahead=90
        """
        # FIX: Use safe_int to prevent crash on bad inputs
        low_threshold = safe_int(request.query_params.get('low_threshold'), 50)
        days_ahead = safe_int(request.query_params.get('days_ahead'), 90)

        # FIX: Renamed variable to prevent shadowing the Django model field 'expiration_date'
        expiry_cutoff_date = timezone.now().date() + timedelta(days=days_ahead)

        low_stock = Product.objects.filter(
            stock_quantity__lte=low_threshold
        ).values('id', 'name', 'stock_quantity', 'base_unit', 'product_type__name')

        expiring_soon = Product.objects.filter(
            expiration_date__lte=expiry_cutoff_date,
            expiration_date__gt=timezone.now().date()
        ).values('id', 'name', 'expiration_date', 'stock_quantity', 'product_type__name')

        expired = Product.objects.filter(
            expiration_date__lt=timezone.now().date()
        ).values('id', 'name', 'expiration_date', 'stock_quantity', 'product_type__name')

        return Response({
            'low_stock': list(low_stock),
            'expiring_soon': list(expiring_soon),
            'expired': list(expired),
            'thresholds': {
                'low_stock': low_threshold,
                'expiry_days': days_ahead
            }
        })

    @extend_schema(
        responses=inline_serializer(
            name='PrescriptionStatsResponse',
            fields={
                'status_breakdown': serializers.ListField(child=serializers.DictField()),
                'recent_pending': serializers.ListField(child=serializers.DictField()),
            }
        )
    )
    @action(detail=False, methods=['get'])
    def prescription_stats(self, request):
        """Prescription workflow statistics."""
        stats = (
            Prescription.objects
            .values('status')
            .annotate(count=Count('id'))
            .order_by('status')
        )

        # Minor convention: Use the model's constant instead of hardcoded string
        pending_recent = Prescription.objects.filter(
            status=Prescription.Status.PENDING
        ).order_by('-created_at')[:10].values(
            'id', 'prescription_number', 'created_at',
            'doctor__name', 'patient__name'
        )

        return Response({
            'status_breakdown': list(stats),
            'recent_pending': list(pending_recent)
        })

    @extend_schema(
        responses=inline_serializer(
            name='MonthlyRevenueResponse',
            fields={
                'year': serializers.IntegerField(),
                'monthly_data': serializers.ListField(child=serializers.DictField())
            }
        )
    )    
    @action(detail=False, methods=['get'])
    def monthly_revenue(self, request):
        """
        Monthly revenue trend.
        Usage: /api/reports/monthly_revenue/?year=2024
        """
        # FIX: Use safe_int to prevent crash if user passes ?year=abc
        year = safe_int(request.query_params.get('year'), timezone.now().year)

        monthly = (
            Sale.objects
            .filter(created_at__year=year)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(
                sales_count=Count('id'),
                revenue=Sum('total_amount')
            )
            .order_by('month')
        )

        return Response({
            'year': year,
            'monthly_data': list(monthly)
        })

    @extend_schema(
        responses=inline_serializer(
            name='ProductTypeBreakdownResponse',
            fields={
                'inventory_by_type': serializers.ListField(child=serializers.DictField()),
                'sales_by_type': serializers.ListField(child=serializers.DictField()),
            }
        )
    )
    @action(detail=False, methods=['get'])
    def product_type_breakdown(self, request):
        """
        Product breakdown by type with stock and sales metrics.
        Usage: /api/reports/product_type_breakdown/
        """
        # Products by type
        by_type = (
            Product.objects
            .filter(is_active=True)
            .values('product_type__id', 'product_type__name')
            .annotate(
                product_count=Count('id'),
                total_stock=Sum('stock_quantity'),
                total_value=Sum(F('stock_quantity') * F('selling_price')),
                low_stock_count=Count('id', filter=Q(stock_quantity__lt=10)),
                expired_count=Count('id', filter=Q(expiration_date__lt=timezone.now().date()))
            )
            .order_by('product_type__name')
        )

        # Sales by product type
        sales_by_type = (
            SaleItem.objects
            .values('product__product_type__id', 'product__product_type__name')
            .annotate(
                items_sold=Sum('quantity'),
                revenue=Sum('subtotal')
            )
            .order_by('-revenue')
        )

        return Response({
            'inventory_by_type': list(by_type),
            'sales_by_type': list(sales_by_type)
        })