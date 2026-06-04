# medicines/web/views/product.py
from django.shortcuts import render, redirect
from django.contrib import messages
from urllib.parse import urlencode
from medicines.web.api_helper import *
from medicines.web.decorators import *
from medicines.core.models import Product

@login_required_template
def product_list(request):
    token = request.session.get('token')
    current_page = request.GET.get('page', 1)
    search_query = request.GET.get('search', '')
    low_stock = request.GET.get('low_stock', '')
    expired = request.GET.get('expired', '')

    api_params = {k: v for k, v in {
        'page': current_page, 'search': search_query,
        'low_stock': low_stock, 'expired': expired
    }.items() if v}

    api_url = f'/api/products/?{urlencode(api_params)}'
    response = api_call('GET', api_url, token=token)

    products, next_page, prev_page, count = [], None, None, 0
    if response.status_code == 200:
        data = response.json()
        products = data.get('results', [])
        count = data.get('count', 0)
        if data.get('next'): next_page = data['next'].split('page=')[-1]
        if data.get('previous'): prev_page = 1 if 'page=' not in data['previous'] else data['previous'].split('page=')[-1]
    else:
        messages.error(request, 'Failed to load products.')

    return render(request, 'products/product_list.html', {
        'products': products, 'count': count,
        'next_page': next_page, 'prev_page': prev_page, 'current_page': current_page,
        'search_query': search_query, 'low_stock': low_stock, 'expired': expired,
    })

@login_required_template
@pharmacy_staff_required
def product_create(request):
    token = request.session.get('token')
    errors = {}
    old_input = request.POST.dict() if request.method == 'POST' else {}

    if request.method == 'POST':
        old_input['is_active'] = request.POST.get('is_active') == 'on'
        old_input['requires_prescription'] = request.POST.get('requires_prescription') == 'on'

        payload = {
            'name': old_input.get('name'),
            'description': old_input.get('description'),
            'base_unit': old_input.get('base_unit'),
            'selling_price': old_input.get('selling_price'),
            'stock_quantity': old_input.get('stock_quantity'),
            'expiration_date': old_input.get('expiration_date') or None,
            'category_id': old_input.get('category_id') or None,
            'product_type_id': old_input.get('product_type_id') or None,
            'requires_prescription': old_input['requires_prescription'],
            'is_active': old_input['is_active'],
            # M2M: Convert list of string IDs to list of integers
            'supplier_ids': [int(sid) for sid in request.POST.getlist('supplier_ids') if sid],
        }

        files = {'image': request.FILES['image']} if 'image' in request.FILES else None

        response = api_call('POST', '/api/products/', data=payload, token=token, files=files)
        if response.status_code == 201:
            messages.success(request, 'Product created successfully.')
            return redirect('template-product-list')
        elif response.status_code == 400:
            errors = response.json()
        else:
            messages.error(request, 'Failed to create product.')

    # Fetch dropdown data
    cats_res = api_call('GET', '/api/categories/?page_size=50', token=token)
    categories = cats_res.json().get('results', []) if cats_res.status_code == 200 else []

    pt_res = api_call('GET', '/api/product-types/?page_size=50', token=token)
    product_types = pt_res.json().get('results', []) if pt_res.status_code == 200 else []

    supp_res = api_call('GET', '/api/suppliers/?page_size=50', token=token)
    suppliers = supp_res.json().get('results', []) if supp_res.status_code == 200 else []

    return render(request, 'products/product_form.html', {
        'edit_mode': False, 'errors': errors, 'product': old_input,
        'categories': categories, 'product_types': product_types, 'suppliers': suppliers,
        'base_units': Product.BaseUnit.choices,
    })

@login_required_template
def product_detail(request, id):
    token = request.session.get('token')
    response = api_call('GET', f'/api/products/{id}/', token=token)
    if response.status_code != 200:
        messages.error(request, 'Product not found.')
        return redirect('template-product-list')
    
    product = response.json()
    return render(request, 'products/product_detail.html', {'product': product})

@login_required_template
@pharmacy_staff_required
def product_edit(request, id):
    token = request.session.get('token')
    errors = {}

    response = api_call('GET', f'/api/products/{id}/', token=token)
    if response.status_code != 200:
        messages.error(request, 'Product not found.')
        return redirect('template-product-list')
    product_data = response.json()

    if request.method == 'POST':
        old_input = request.POST.dict()
        old_input['is_active'] = request.POST.get('is_active') == 'on'
        old_input['requires_prescription'] = request.POST.get('requires_prescription') == 'on'

        payload = {
            'name': old_input.get('name'),
            'description': old_input.get('description'),
            'base_unit': old_input.get('base_unit'),
            'selling_price': old_input.get('selling_price'),
            'expiration_date': old_input.get('expiration_date') or None,
            'category_id': old_input.get('category_id') or None,
            'product_type_id': old_input.get('product_type_id') or None,
            'requires_prescription': old_input['requires_prescription'],
            'is_active': old_input['is_active'],
            'supplier_ids': [int(sid) for sid in request.POST.getlist('supplier_ids') if sid],
        }

        files = {'image': request.FILES['image']} if 'image' in request.FILES else None

        response = api_call('PATCH', f'/api/products/{id}/', data=payload, token=token, files=files)
        if response.status_code == 200:
            messages.success(request, 'Product updated successfully.')
            return redirect('template-product-list')
        elif response.status_code == 400:
            errors = response.json()
            # Flatten IDs for template repopulation
            product_data.update(old_input)
            product_data['supplier_ids'] = payload['supplier_ids']
        else:
            messages.error(request, 'Failed to update product.')

    # Fetch dropdown data
    cats_res = api_call('GET', '/api/categories/?page_size=50', token=token)
    categories = cats_res.json().get('results', []) if cats_res.status_code == 200 else []

    pt_res = api_call('GET', '/api/product-types/?page_size=50', token=token)
    product_types = pt_res.json().get('results', []) if pt_res.status_code == 200 else []

    supp_res = api_call('GET', '/api/suppliers/?page_size=50', token=token)
    suppliers = supp_res.json().get('results', []) if supp_res.status_code == 200 else []

    return render(request, 'products/product_form.html', {
        'edit_mode': True, 'errors': errors, 'product': product_data,
        'categories': categories, 'product_types': product_types, 'suppliers': suppliers,
        'base_units': Product.BaseUnit.choices,
    })

@login_required_template
@pharmacy_staff_required
def product_delete(request, id):
    if request.method == 'POST' and request.POST.get('_method') == 'DELETE':
        token = request.session.get('token')
        response = api_call('DELETE', f'/api/products/{id}/', token=token)
        if response.status_code == 204:
            messages.success(request, 'Product deleted.')
        else:
            messages.error(request, 'Failed to delete product.')
    return redirect('template-product-list')