from django.shortcuts import render, redirect
from django.contrib import messages
from medicines.web.api_helper import *
from medicines.web.decorators import * 

@login_required_template
def home(request):
    role = request.session.get('role')
    username = request.session.get('username')
    
    context = {'role': role, 'username': username}

    # CASHIER GUARD: Defer POS screen for later
    if role == 'cashier':
        return render(request, 'cashier_placeholder.html', context)
    
    token = request.session.get('token')
    
    # 1. Fetch Stock Alerts (Admin & Pharmacist both care about this)
    alerts_response = api_call('GET', '/api/reports/stock_alerts/', token=token)
    if alerts_response.status_code == 200:
        context['alerts'] = alerts_response.json()
        
    # 2. Fetch Prescription Stats (Mostly for Pharmacist)
    rx_response = api_call('GET', '/api/reports/prescription_stats/', token=token)
    if rx_response.status_code == 200:
        context['rx_stats'] = rx_response.json()
        
    # 3. Fetch Sales Summary (Mostly for Admin)
    if role == 'admin':
        sales_response = api_call('GET', '/api/reports/sales_summary/', token=token)
        if sales_response.status_code == 200:
            context['sales'] = sales_response.json()

    return render(request, 'dashboard.html', context)