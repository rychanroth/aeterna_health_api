# medicines/web/views/report.py
from django.shortcuts import render
from django.contrib import messages
import datetime
from medicines.web.api_helper import *
from medicines.web.decorators import *

@login_required_template
def reports_dashboard(request):
    token = request.session.get('token')
    
    # Default to current month if no dates provided
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date or not end_date:
        today = datetime.date.today()
        start_date = today.replace(day=1).isoformat()
        end_date = today.isoformat()

    api_params = f'?start_date={start_date}&end_date={end_date}'

    # Fetch Sales Summary & Payment Breakdown
    sales_res = api_call('GET', f'/api/reports/sales_summary/{api_params}', token=token)
    sales_data = {}
    if sales_res.status_code == 200:
        sales_data = sales_res.json()

    # Fetch Top Products for the period
    top_prod_res = api_call('GET', f'/api/reports/top_products/{api_params}&limit=5', token=token)
    top_products = []
    if top_prod_res.status_code == 200:
        top_products = top_prod_res.json().get('top_products', [])

    # Fetch Prescription Stats (All time, as it's a workflow status)
    rx_res = api_call('GET', '/api/reports/prescription_stats/', token=token)
    rx_stats = {}
    if rx_res.status_code == 200:
        rx_stats = rx_res.json()

    return render(request, 'reports/reports_dashboard.html', {
        'start_date': start_date,
        'end_date': end_date,
        'summary': sales_data.get('summary', {}),
        'payment_breakdown': sales_data.get('payment_breakdown', []),
        'daily_breakdown': sales_data.get('daily_breakdown', []),
        'top_products': top_products,
        'rx_stats': rx_stats,
    })