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
# medicines/web/views/product.py

@login_required_template
@pharmacy_staff_required
def product_create(request):
    token = request.session.get('token')
    errors = {}
    old_input = request.POST.dict() if request.method == 'POST' else {}

    if request.method == 'POST':
        # FIX: Use 'in request.POST' instead of '== "on"'
        old_input['is_active'] = 'is_active' in request.POST
        old_input['requires_prescription'] = 'requires_prescription' in request.POST

        payload = {
            'name': old_input.get('name'),
            'description': old_input.get('description'),
            'base_unit': old_input.get('base_unit'),
            'selling_price': old_input.get('selling_price'),
            'category_id': old_input.get('category_id') or None,
            'product_type_id': old_input.get('product_type_id') or None,
            'requires_prescription': old_input['requires_prescription'],
            'is_active': old_input['is_active'],
        }

        files = {'image': request.FILES['image']} if 'image' in request.FILES else None

        response = api_call('POST', '/api/products/', data=payload, token=token, files=files)
        if response.status_code == 201:
            messages.success(request, 'Product created successfully. You can now add stock via Receive Stock.')
            return redirect('template-product-list')
        elif response.status_code == 400:
            errors = response.json()
        else:
            messages.error(request, 'Failed to create product.')

    categories = fetch_all_api_data('/api/categories/', token)
    product_types = fetch_all_api_data('/api/product-types/', token)

    return render(request, 'products/product_form.html', {
        'edit_mode': False, 'errors': errors, 'product': old_input,
        'categories': categories, 'product_types': product_types,
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
    
    # FIX: Fetch associated active batches for this product to display on detail page
    batches_response = api_call('GET', f'/api/batches/?product={id}&is_active=true', token=token)
    batches = batches_response.json().get('results', []) if batches_response.status_code == 200 else []

    return render(request, 'products/product_detail.html', {
        'product': product,
        'batches': batches  # Pass batches to the template
    })

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
        old_input['is_active'] = 'is_active' in request.POST
        old_input['requires_prescription'] = request.POST.get('requires_prescription') == 'on'

        payload = {
            'name': old_input.get('name'),
            'description': old_input.get('description'),
            'base_unit': old_input.get('base_unit'),
            'selling_price': old_input.get('selling_price'),
            # FIX: Removed 'expiration_date'. Handled by Batch now.
            'category_id': old_input.get('category_id') or None,
            'product_type_id': old_input.get('product_type_id') or None,
            'requires_prescription': old_input['requires_prescription'],
            'is_active': old_input['is_active'],
            # FIX: Removed supplier_ids
        }

        files = {'image': request.FILES['image']} if 'image' in request.FILES else None

        response = api_call('PATCH', f'/api/products/{id}/', data=payload, token=token, files=files)
        if response.status_code == 200:
            messages.success(request, 'Product updated successfully.')
            return redirect('template-product-list')
        elif response.status_code == 400:
            errors = response.json()
            product_data.update(old_input)
        else:
            messages.error(request, 'Failed to update product.')

    categories = fetch_all_api_data('/api/categories/', token)
    product_types = fetch_all_api_data('/api/product-types/', token)

    return render(request, 'products/product_form.html', {
        'edit_mode': True, 'errors': errors, 'product': product_data,
        'categories': categories, 'product_types': product_types,
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