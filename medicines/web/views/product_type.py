from django.shortcuts import render, redirect
from django.contrib import messages
from urllib.parse import urlencode
from medicines.web.api_helper import *
from medicines.web.decorators import *

@login_required_template
@pharmacy_staff_required
def product_type_list(request):
    token = request.session.get('token')
    current_page = request.GET.get('page', 1)
    search_query = request.GET.get('search', '')
    ordering = request.GET.get('ordering', '')

    api_params = {k: v for k, v in {
        'page': current_page,
        'search': search_query,
        'ordering': ordering,
    }.items() if v}

    api_url = f'/api/product-types/?{urlencode(api_params)}'
    response = api_call('GET', api_url, token=token)

    product_types = []
    next_page = prev_page = None
    count = 0

    if response.status_code == 200:
        data = response.json()
        product_types = data.get('results', [])
        count = data.get('count', 0)
        if data.get('next'): next_page = data['next'].split('page=')[-1]
        if data.get('previous'): prev_page = 1 if 'page=' not in data['previous'] else data['previous'].split('page=')[-1]
    else:
        messages.error(request, 'Failed to load product types.')

    return render(request, 'product_types/product_type_list.html', {
        'product_types': product_types,
        'next_page': next_page, 'prev_page': prev_page, 'count': count,
        'current_page': current_page, 'search_query': search_query, 'ordering': ordering,
    })

@login_required_template
@pharmacy_staff_required
def product_type_create(request):
    token = request.session.get('token')
    errors = {}
    old_input = {}

    if request.method == 'POST':
        old_input = request.POST.dict()
        # Handle checkboxes explicitly
        old_input['requires_prescription'] = request.POST.get('requires_prescription') == 'on'
        old_input['requires_expiration'] = request.POST.get('requires_expiration') == 'on'
        old_input['is_active'] = 'is_active' in request.POST

        payload = {
            'name': old_input.get('name'),
            'description': old_input.get('description'),
            'requires_prescription': old_input['requires_prescription'],
            'requires_expiration': old_input['requires_expiration'],
            'is_active': old_input['is_active'],
        }

        files = {'image': request.FILES['image']} if 'image' in request.FILES else None

        response = api_call('POST', '/api/product-types/', data=payload, token=token, files=files)

        if response.status_code == 201:
            messages.success(request, 'Product Type created successfully!')
            return redirect('template-product-type-list')
        else:
            if response.status_code == 400:
                errors = response.json()
            else:
                messages.error(request, 'An unexpected error occurred.')

    return render(request, 'product_types/product_type_form.html', {
        'edit_mode': False,
        'errors': errors,
        'product_type': old_input or {},
    })

@login_required_template
@pharmacy_staff_required
def product_type_detail(request, id):
    token = request.session.get('token')
    
    pt_response = api_call('GET', f'/api/product-types/{id}/', token=token)
    if pt_response.status_code != 200:
        messages.error(request, 'Product Type not found.')
        return redirect('template-product-type-list')
    product_type = pt_response.json()

    # Fetch associated categories (assuming API returns list or paginated results)
    cat_response = api_call('GET', f'/api/product-types/{id}/categories/', token=token)
    categories = cat_response.json() if cat_response.status_code == 200 else []

    root_cat_response = api_call('GET', f'/api/product-types/{id}/root_categories/', token=token)
    root_categories = root_cat_response.json() if root_cat_response.status_code == 200 else []

    return render(request, 'product_types/product_type_detail.html', {
        'product_type': product_type,
        'categories': categories,
        'root_categories': root_categories,
    })

@login_required_template
@pharmacy_staff_required
def product_type_edit(request, id):
    token = request.session.get('token')
    errors = {}

    pt_response = api_call('GET', f'/api/product-types/{id}/', token=token)
    if pt_response.status_code != 200:
        messages.error(request, 'Product Type not found')
        return redirect('template-product-type-list')
    pt_data = pt_response.json()

    if request.method == 'POST':
        old_input = request.POST.dict()
        old_input['requires_prescription'] = request.POST.get('requires_prescription') == 'on'
        old_input['requires_expiration'] = request.POST.get('requires_expiration') == 'on'
        old_input['is_active'] = 'is_active' in request.POST

        payload = {
            'name': old_input.get('name'),
            'description': old_input.get('description'),
            'requires_prescription': old_input['requires_prescription'],
            'requires_expiration': old_input['requires_expiration'],
            'is_active': old_input['is_active'],
        }

        files = {'image': request.FILES['image']} if 'image' in request.FILES else None

        response = api_call('PATCH', f'/api/product-types/{id}/', data=payload, token=token, files=files)

        if response.status_code == 200:
            messages.success(request, 'Product Type updated successfully!')
            return redirect('template-product-type-list')
        else:
            if response.status_code == 400:
                errors = response.json()
                pt_data.update(old_input) # Repopulate form with failed inputs
            else:
                messages.error(request, 'Failed to update product type.')

    return render(request, 'product_types/product_type_form.html', {
        'edit_mode': True,
        'product_type': pt_data,
        'errors': errors,
    })

@login_required_template
@pharmacy_staff_required
def product_type_delete(request, id):
    if request.method == 'POST' and request.POST.get('_method') == 'DELETE':
        token = request.session.get('token')
        response = api_call('DELETE', f'/api/product-types/{id}/', token=token)
        if response.status_code == 204:
            messages.success(request, 'Product Type deleted successfully.')
        else:
            messages.error(request, 'Failed to delete product type. It might have associated products.')
    return redirect('template-product-type-list')