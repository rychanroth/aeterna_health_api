from django.shortcuts import render
from django.contrib import messages
from urllib.parse import urlencode
from medicines.web.api_helper import *
from medicines.web.decorators import *
from django.utils.dateparse import parse_datetime

@login_required_template
def stock_movement_list(request):
    token = request.session.get('token')
    
    # 1. Capture filter parameters
    current_page = request.GET.get('page', 1)
    direction = request.GET.get('direction', '') # 'in' or 'out'
    product_id = request.GET.get('product', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    # 2. Build API parameters (omit empty values)
    api_params = {k: v for k, v in {
        'page': current_page,
        'direction': direction,
        'product': product_id,
        'start_date': start_date,
        'end_date': end_date,
    }.items() if v}

    api_url = f'/api/stock-movements/?{urlencode(api_params)}'
    response = api_call('GET', api_url, token=token)

    movements = []
    next_page = prev_page = None
    count = 0

    if response.status_code == 200:
        data = response.json()
        movements = data.get('results', [])

        for mov in movements:
            if mov.get('created_at'):
                mov['created_at'] = parse_datetime(mov['created_at'])

        count = data.get('count', 0)
        if data.get('next'): next_page = data['next'].split('page=')[-1]
        if data.get('previous'): prev_page = 1 if 'page=' not in data['previous'] else data['previous'].split('page=')[-1]
    else:
        messages.error(request, 'Failed to load stock movements.')

    # 3. Fetch products for the filter dropdown
    prod_response = api_call('GET', '/api/products/?page_size=100', token=token)
    products = prod_response.json().get('results', []) if prod_response.status_code == 200 else []

    return render(request, 'stock_movements/stock_movement_list.html', {
        'movements': movements,
        'next_page': next_page, 'prev_page': prev_page, 'count': count,
        'current_page': current_page,
        # Pass filter states back to preserve form selection
        'direction': direction, 
        'product_id': product_id,
        'start_date': start_date,
        'end_date': end_date,
        'products': products,
    })