# medicines/web/views/sale.py
from django.shortcuts import render
from django.contrib import messages
from urllib.parse import urlencode
from django.utils.dateparse import parse_datetime
from medicines.web.api_helper import *
from medicines.web.decorators import *
import json

def _parse_sale_dates(sales):
    """Helper to parse ISO 8601 date strings into Python datetime objects."""
    for sale in sales:
        if sale.get('created_at'):
            sale['created_at'] = parse_datetime(sale['created_at'])
    return sales

@login_required_template
def sale_list(request):
    token = request.session.get('token')
    current_page = request.GET.get('page', 1)
    search_query = request.GET.get('search', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    quick_filter = request.GET.get('filter', '') # 'today' or 'my_sales'

    # Determine which API endpoint to hit based on the quick filter
    if quick_filter == 'today':
        api_url = '/api/sales/today/'
    elif quick_filter == 'my_sales':
        api_url = '/api/sales/my_sales/'
    else:
        api_params = {k: v for k, v in {
            'page': current_page, 'search': search_query,
            'start_date': start_date, 'end_date': end_date
        }.items() if v}
        api_url = f'/api/sales/?{urlencode(api_params)}'

    response = api_call('GET', api_url, token=token)
    
    sales = []
    next_page = prev_page = None
    count = 0

    if response.status_code == 200:
        data = response.json()
        
        # Custom actions return flat lists, main endpoint returns paginated dict
        if isinstance(data, list):
            sales = _parse_sale_dates(data)
            count = len(sales)
        else:
            sales = _parse_sale_dates(data.get('results', []))
            count = data.get('count', 0)
            if data.get('next'): next_page = data['next'].split('page=')[-1]
            if data.get('previous'): prev_page = 1 if 'page=' not in data['previous'] else data['previous'].split('page=')[-1]
    else:
        messages.error(request, 'Failed to load sales history.')

    return render(request, 'sales/sale_list.html', {
        'sales': sales, 'count': count,
        'next_page': next_page, 'prev_page': prev_page, 'current_page': current_page,
        'search_query': search_query, 'start_date': start_date, 'end_date': end_date,
        'quick_filter': quick_filter,
    })

@login_required_template
def sale_detail(request, id):
    token = request.session.get('token')
    response = api_call('GET', f'/api/sales/{id}/', token=token)
    
    if response.status_code == 404:
        messages.error(request, 'Sale record not found.')
        return redirect('template-sale-list')
    if response.status_code != 200:
        messages.error(request, 'Failed to load sale details.')
        return redirect('template-sale-list')
        
    sale = response.json()
    # Parse the ISO 8601 date string for template rendering
    if sale.get('created_at'):
        sale['created_at'] = parse_datetime(sale['created_at'])
        
    return render(request, 'sales/sale_detail.html', {'sale': sale})

@login_required_template
def sale_create(request):
    token = request.session.get('token')
    errors = {}
    old_input = request.POST.dict() if request.method == 'POST' else {}

    if request.method == 'POST':
        product_ids = request.POST.getlist('product_id[]')
        quantities = request.POST.getlist('quantity[]')
        unit_prices = request.POST.getlist('unit_price[]')

        items = []
        for i in range(len(product_ids)):
            if product_ids[i]:
                items.append({
                    'product_id': int(product_ids[i]),
                    'quantity': int(quantities[i]),
                    'unit_price': unit_prices[i]
                })

        payload = {
            'payment_method': old_input.get('payment_method', 'cash'),
            'notes': old_input.get('notes', ''),
            'items': items
        }

        response = api_call('POST', '/api/sales/', data=payload, token=token)
        
        if response.status_code == 201:
            messages.success(request, 'Sale completed successfully!')
            sale_id = response.json().get('id')
            return redirect('template-sale-detail', id=sale_id)
        elif response.status_code == 400:
            errors = response.json()
            # Check if error is due to Rx product without prescription
            if 'One or more products require a prescription' in str(errors):
                messages.error(request, 'For Rx product, please go to the Prescription Dispense page instead.')
            else:
                messages.error(request, 'Failed to process sale. Check form errors.')
        else:
            messages.error(request, 'An unexpected error occurred.')

    prod_response = api_call('GET', '/api/products/?page_size=100', token=token)
    products = prod_response.json().get('results', []) if prod_response.status_code == 200 else []

    return render(request, 'sales/sale_form.html', {
        'errors': errors, 'old_input': old_input, 'products': products,
    })