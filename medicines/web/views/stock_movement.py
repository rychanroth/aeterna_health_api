# medicines/web/views/stock_movement.py
from django.shortcuts import render
from django.contrib import messages
from urllib.parse import urlencode
from django.utils.dateparse import parse_datetime
from medicines.web.api_helper import *
from medicines.web.decorators import *
import json

def _parse_movement_dates(movements):
    """Helper to parse ISO 8601 date strings into Python datetime objects for templates."""
    for mov in movements:
        if mov.get('created_at'):
            mov['created_at'] = parse_datetime(mov['created_at'])
    return movements

@login_required_template
def stock_movement_list(request):
    token = request.session.get('token')
    
    # 1. Capture filter parameters
    current_page = request.GET.get('page', 1)
    search_query = request.GET.get('search', '')
    direction = request.GET.get('direction', '')
    product_id = request.GET.get('product', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    # NEW: Capture batch status
    batch_is_active = request.GET.get('batch_is_active', '')

    # 2. Build API parameters
    api_params = {k: v for k, v in {
        'page': current_page,
        'search': search_query,
        'direction': direction,
        'product': product_id,
        'start_date': start_date,
        'end_date': end_date,
        'batch_is_active': batch_is_active, # NEW: Include in API call
    }.items() if v}

    api_url = f'/api/stock-movements/?{urlencode(api_params)}'
    response = api_call('GET', api_url, token=token)

    movements = []
    next_page = prev_page = None
    count = 0

    if response.status_code == 200:
        data = response.json()
        movements = _parse_movement_dates(data.get('results', []))
        count = data.get('count', 0)
        if data.get('next'): next_page = data['next'].split('page=')[-1]
        if data.get('previous'): prev_page = 1 if 'page=' not in data['previous'] else data['previous'].split('page=')[-1]
    else:
        messages.error(request, 'Failed to load stock movements.')

    # Fetch products for the filter dropdown
    prod_response = api_call('GET', '/api/products/?page_size=500', token=token)
    products = prod_response.json().get('results', []) if prod_response.status_code == 200 else []

    return render(request, 'stock_movements/stock_movement_list.html', {
        'movements': movements,
        'next_page': next_page, 
        'prev_page': prev_page, 
        'count': count,
        'current_page': current_page, 
        'search_query': search_query,
        'direction': direction, 
        'product_id': product_id,
        'start_date': start_date, 
        'end_date': end_date,
        'batch_is_active': batch_is_active, # NEW: Pass back to template
        'products_json': json.dumps(products),
    })


@login_required_template
@pharmacy_staff_required
def stock_movement_create(request):
    token = request.session.get('token')
    errors = {}
    old_input = request.POST.dict() if request.method == 'POST' else {}

    if request.method == 'POST':
        movement_type = old_input.get('movement_type')
        payload = {
            'movement_type': movement_type,
            'quantity': old_input.get('quantity'),
            'reference': old_input.get('reference', ''),
            'notes': old_input.get('notes', ''),
        }

        if movement_type == 'purchase':
            payload.update({
                'product_id': old_input.get('product_id') or None,
                'supplier_id': old_input.get('supplier_id') or None,
                'cost_price': old_input.get('cost_price') or None,
                'expiration_date': old_input.get('expiration_date') or None,
                'received_date': old_input.get('received_date') or None,
            })
        else:
            payload['batch_id'] = old_input.get('batch_id') or None
            if movement_type == 'return_supplier':
                payload['supplier_id'] = old_input.get('supplier_id') or None

        response = api_call('POST', '/api/stock-movements/', data=payload, token=token)
        
        if response.status_code == 201:
            messages.success(request, 'Stock movement recorded successfully.')
            return redirect('template-stock-movement-list')
        elif response.status_code == 400:
            errors = response.json()
            messages.error(request, 'Failed to record movement. Check form errors.')
        else:
            messages.error(request, f'Unexpected error (Status {response.status_code}).')

    # 1. Fetch Products and Suppliers
    products = fetch_all_api_data('/api/products/', token)
    suppliers = fetch_all_api_data('/api/suppliers/', token)

    # 2. FIX: Pre-load ALL active batches and group them by Product ID
    active_batches_data = fetch_all_api_data('/api/batches/?is_active=true&ordering=expiration_date', token)
    
    batches_by_product = {}
    for b in active_batches_data:
        # Ensure product ID is a string for Alpine.js dictionary lookup
        prod_id = str(b.get('product'))
        if prod_id not in batches_by_product:
            batches_by_product[prod_id] = []
        batches_by_product[prod_id].append(b)

    return render(request, 'stock_movements/stock_movement_form.html', {
        'errors': errors,
        'old_input': old_input,
        'products': products,
        'suppliers': suppliers,
        'batches_by_product': batches_by_product, # Pass the grouped dictionary
    })


@login_required_template
@pharmacy_staff_required
def stock_movement_detail(request, id):
    token = request.session.get('token')
    response = api_call('GET', f'/api/stock-movements/{id}/', token=token)
    
    if response.status_code == 404:
        messages.error(request, 'Stock movement record not found.')
        return redirect('template-stock-movement-list')
    if response.status_code != 200:
        messages.error(request, 'Failed to load stock movement details.')
        return redirect('template-stock-movement-list')
        
    movement = response.json()
    movement = _parse_movement_dates([movement])[0] # Parse dates using helper

    return render(request, 'stock_movements/stock_movement_detail.html', {
        'movement': movement
    })


@login_required_template
def stock_movement_summary(request):
    token = request.session.get('token')
    
    # Summary supports date and product filtering
    product_id = request.GET.get('product', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    api_params = {k: v for k, v in {
        'product': product_id, 'start_date': start_date, 'end_date': end_date
    }.items() if v}

    api_url = f'/api/stock-movements/summary/?{urlencode(api_params)}'
    response = api_call('GET', api_url, token=token)
    
    summary_data = {'total_in': 0, 'total_out': 0, 'net_change': 0}
    if response.status_code == 200:
        summary_data = response.json()

    # Fetch products for filter dropdown
    prod_response = api_call('GET', '/api/products/?page_size=100', token=token)
    products = prod_response.json().get('results', []) if prod_response.status_code == 200 else []

    return render(request, 'stock_movements/stock_movement_summary.html', {
        'summary': summary_data,
        'products': products,
        'product_id': product_id,
        'start_date': start_date,
        'end_date': end_date
    })
    