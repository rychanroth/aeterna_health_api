# medicines/web/views/batch.py
from django.shortcuts import render, redirect
from django.contrib import messages
from urllib.parse import urlencode
from medicines.web.api_helper import *
from medicines.web.decorators import *
from django.utils.dateparse import parse_datetime

@login_required_template
@pharmacy_staff_required
def batch_list(request):
    token = request.session.get('token')
    
    # Capture filter parameters
    current_page = request.GET.get('page', 1)
    search_query = request.GET.get('search', '')
    is_active = request.GET.get('is_active', '')
    is_expired = request.GET.get('is_expired', '')
    expiring_soon = request.GET.get('expiring_soon', '')
    ordering = request.GET.get('ordering', 'expiration_date') # Default to FEFO

    # Build API parameters dictionary, removing empty values
    api_params = {k: v for k, v in {
        'page': current_page,
        'search': search_query,
        'is_active': is_active,
        'is_expired': is_expired,
        'expiring_soon': expiring_soon,
        'ordering': ordering,
    }.items() if v}

    api_url = f'/api/batches/?{urlencode(api_params)}'
    response = api_call('GET', api_url, token=token)

    batches, next_page, prev_page, count = [], None, None, 0
    if response.status_code == 200:
        data = response.json()
        batches = data.get('results', [])
        count = data.get('count', 0)
        if data.get('next'): next_page = data['next'].split('page=')[-1]
        if data.get('previous'): prev_page = 1 if 'page=' not in data['previous'] else data['previous'].split('page=')[-1]
    else:
        messages.error(request, 'Failed to load inventory batches.')

    return render(request, 'batches/batch_list.html', {
        'batches': batches,
        'count': count,
        'next_page': next_page,
        'prev_page': prev_page,
        'current_page': current_page,
        'search_query': search_query,
        'is_active': is_active,
        'is_expired': is_expired,
        'expiring_soon': expiring_soon,
        'ordering': ordering, # Pass to template
    })

@pharmacy_staff_required
def batch_detail(request, id):
    token = request.session.get('token')
    
    # 1. Fetch the Batch data
    batch_response = api_call('GET', f'/api/batches/{id}/', token=token)
    if batch_response.status_code != 200:
        messages.error(request, 'Batch not found.')
        return redirect('template-batch-list')
    batch = batch_response.json()

    # 2. Fetch the Stock Movements for this specific Batch
    current_page = request.GET.get('page', 1)
    api_url = f'/api/stock-movements/?batch={id}&page={current_page}&ordering=-created_at'
    movements_response = api_call('GET', api_url, token=token)

    movements, next_page, prev_page, count = [], None, None, 0
    if movements_response.status_code == 200:
        data = movements_response.json()
        movements = data.get('results', [])
        count = data.get('count', 0)

    return render(request, 'batches/batch_detail.html', {
        'batch': batch,
        'movements': movements,
        'count': count,
        'next_page': next_page,
        'prev_page': prev_page,
        'current_page': current_page,
    })