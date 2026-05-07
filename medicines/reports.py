from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Count, Avg, F, Q
from django.utils import timezone
from datetime import timedelta
from .models import Sale, SaleItem, Medicine, Prescription
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
        
        # Aggregations
        summary = sales.aggregate(
            total_sales=Count('id'),
            total_revenue=Sum('total_amount'),
            avg_transaction=Avg('total_amount')
        )
        
        # Daily breakdown
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
    def top_medicines(self, request):
        """
        Top selling medicines by quantity.
        Usage: /api/reports/top_medicines/?limit=10
        """
        limit = int(request.query_params.get('limit', 10))
        
        top_items = (
            SaleItem.objects
            .values('medicine__id', 'medicine__name')
            .annotate(
                total_quantity=Sum('quantity'),
                total_revenue=Sum(F('quantity') * F('unit_price'))
            )
            .order_by('-total_quantity')[:limit]
        )
        
        return Response({
            'top_medicines': list(top_items)
        })
    
    @action(detail=False, methods=['get'])
    def stock_alerts(self, request):
        """
        Low stock and expiring medicines alerts.
        Usage: /api/reports/stock_alerts/?low_threshold=50&days_ahead=90
        """
        low_threshold = int(request.query_params.get('low_threshold', 50))
        days_ahead = int(request.query_params.get('days_ahead', 90))
        
        expiration_date = timezone.now().date() + timedelta(days=days_ahead)
        
        # Low stock
        low_stock = Medicine.objects.filter(
            stock_quantity__lte=low_threshold
        ).values('id', 'name', 'stock_quantity', 'base_unit')
        
        # Expiring soon
        expiring_soon = Medicine.objects.filter(
            expiration_date__lte=expiration_date,
            expiration_date__gt=timezone.now().date()
        ).values('id', 'name', 'expiration_date', 'stock_quantity')
        
        # Already expired
        expired = Medicine.objects.filter(
            expiration_date__lt=timezone.now().date()
        ).values('id', 'name', 'expiration_date', 'stock_quantity')
        
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
        """
        Prescription workflow statistics.
        """
        stats = (
            Prescription.objects
            .values('status')
            .annotate(count=Count('id'))
            .order_by('status')
        )
        
        # Recent pending prescriptions
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