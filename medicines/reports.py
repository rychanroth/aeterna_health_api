from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Count, Avg, F, Q
from django.utils import timezone
from datetime import timedelta
from .models import *
from django.db.models.functions import TruncDate, TruncMonth


class ReportViewSet(viewsets.ViewSet):
    """Analytics and reporting endpoints"""

    
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
            sales = sales.filter(created_at__gte=start_date)
        if end_date:
            sales = sales.filter(created_at__lte=end_date)

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
    
    @action(detail=False, methods=['get'])
    def top_products(self, request):
        """
        Top selling products by quantity.
        Usage: /api/reports/top_products/?limit=10
        """
        limit = int(request.query_params.get('limit', 10))

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

    @action(detail=False, methods=['get'])
    def stock_alerts(self, request):
        """
        Low stock and expiring products alerts.
        Usage: /api/reports/stock_alerts/?low_threshold=50&days_ahead=90
        """
        low_threshold = int(request.query_params.get('low_threshold', 50))
        days_ahead = int(request.query_params.get('days_ahead', 90))

        expiration_date = timezone.now().date() + timedelta(days=days_ahead)

        low_stock = Product.objects.filter(
            stock_quantity__lte=low_threshold
        ).values('id', 'name', 'stock_quantity', 'base_unit', 'product_type__name')

        expiring_soon = Product.objects.filter(
            expiration_date__lte=expiration_date,
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

    @action(detail=False, methods=['get'])
    def prescription_stats(self, request):
        """Prescription workflow statistics."""
        stats = (
            Prescription.objects
            .values('status')
            .annotate(count=Count('id'))
            .order_by('status')
        )

        pending_recent = Prescription.objects.filter(
            status='pending'
        ).order_by('-created_at')[:10].values(
            'id', 'prescription_number', 'created_at',
            'doctor__name', 'patient__name'
        )

        return Response({
            'status_breakdown': list(stats),
            'recent_pending': list(pending_recent)
        })

    @action(detail=False, methods=['get'])
    def monthly_revenue(self, request):
        """
        Monthly revenue trend.
        Usage: /api/reports/monthly_revenue/?year=2024
        """
        year = request.query_params.get('year', timezone.now().year)

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