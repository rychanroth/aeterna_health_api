# medicines/web/views/sale.py
from django.shortcuts import render
from django.contrib import messages
from urllib.parse import urlencode
from django.utils.dateparse import parse_datetime
from medicines.web.api_helper import *
from medicines.web.decorators import *

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

def sale_detail(request, id):
    pass