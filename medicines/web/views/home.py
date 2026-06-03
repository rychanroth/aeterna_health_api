# medicines/web/views/home.py
from django.shortcuts import render
from medicines.web.api_helper import *
from medicines.web.decorators import *

@login_required_template
def home(request):
    role = request.session.get('role')
    username = request.session.get('username')
    token = request.session.get('token')
    context = {'role': role, 'username': username}

    if role == 'cashier':
        return render(request, 'cashier_placeholder.html', context)

    # FAST: Single API call for all KPIs
    response = api_call('GET', '/api/reports/dashboard_summary/', token=token)
    if response.status_code == 200:
        context['dashboard'] = response.json()
    else:
        from django.contrib import messages
        messages.error(request, 'Failed to load dashboard data.')

    return render(request, 'dashboard.html', context)