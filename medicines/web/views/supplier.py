from django.shortcuts import render, redirect
from django.contrib import messages
from urllib.parse import urlencode
from medicines.web.api_helper import *
from medicines.web.decorators import *

@login_required_template
@admin_required
def supplier_list(request):
    token = request.session.get('token')
    current_page = request.GET.get('page', 1)
    search_query = request.GET.get('search', '')
    ordering = request.GET.get('ordering', '')

    api_params = {k: v for k, v in {
        'page': current_page,
        'search': search_query,
        'ordering': ordering,
    }.items() if v}

    api_url = f'/api/suppliers/?{urlencode(api_params)}'
    response = api_call('GET', api_url, token=token)

    suppliers = []
    next_page = prev_page = None
    count = 0

    if response.status_code == 200:
        data = response.json()
        suppliers = data.get('results', [])
        count = data.get('count', 0)
        if data.get('next'): next_page = data['next'].split('page=')[-1]
        if data.get('previous'): prev_page = 1 if 'page=' not in data['previous'] else data['previous'].split('page=')[-1]
    else:
        messages.error(request, 'Failed to load suppliers.')

    return render(request, 'suppliers/supplier_list.html', {
        'suppliers': suppliers,
        'next_page': next_page, 'prev_page': prev_page, 'count': count,
        'current_page': current_page, 'search_query': search_query, 'ordering': ordering,
    })

@login_required_template
@admin_required
def supplier_create(request):
    token = request.session.get('token')
    errors = {}
    old_input = {}

    if request.method == 'POST':
        old_input = request.POST.dict()
        old_input['is_active'] = request.POST.get('is_active') == 'on'

        payload = {
            'name': old_input.get('name'),
            'phone': old_input.get('phone'),
            'address': old_input.get('address'),
            'is_active': old_input['is_active'],
        }

        files = {'image': request.FILES['image']} if 'image' in request.FILES else None

        response = api_call('POST', '/api/suppliers/', data=payload, token=token, files=files)

        if response.status_code == 201:
            messages.success(request, 'Supplier created successfully!')
            return redirect('template-supplier-list')
        else:
            if response.status_code == 400:
                errors = response.json()
            else:
                messages.error(request, 'An unexpected error occurred.')

    return render(request, 'suppliers/supplier_form.html', {
        'edit_mode': False,
        'errors': errors,
        'supplier': old_input or {},
    })

@login_required_template
@admin_required
def supplier_detail(request, id):
    token = request.session.get('token')
    
    response = api_call('GET', f'/api/suppliers/{id}/', token=token)
    if response.status_code != 200:
        messages.error(request, 'Supplier not found.')
        return redirect('template-supplier-list')
    
    supplier = response.json()

    return render(request, 'suppliers/supplier_detail.html', {
        'supplier': supplier,
    })

@login_required_template
@admin_required
def supplier_edit(request, id):
    token = request.session.get('token')
    errors = {}

    response = api_call('GET', f'/api/suppliers/{id}/', token=token)
    if response.status_code != 200:
        messages.error(request, 'Supplier not found')
        return redirect('template-supplier-list')
    supplier_data = response.json()

    if request.method == 'POST':
        old_input = request.POST.dict()
        old_input['is_active'] = request.POST.get('is_active') == 'on'

        payload = {
            'name': old_input.get('name'),
            'phone': old_input.get('phone'),
            'address': old_input.get('address'),
            'is_active': old_input['is_active'],
        }

        files = {'image': request.FILES['image']} if 'image' in request.FILES else None

        response = api_call('PATCH', f'/api/suppliers/{id}/', data=payload, token=token, files=files)

        if response.status_code == 200:
            messages.success(request, 'Supplier updated successfully!')
            return redirect('template-supplier-list')
        else:
            if response.status_code == 400:
                errors = response.json()
                supplier_data.update(old_input)
            else:
                messages.error(request, 'Failed to update supplier.')

    return render(request, 'suppliers/supplier_form.html', {
        'edit_mode': True,
        'supplier': supplier_data,
        'errors': errors,
    })

@login_required_template
@admin_required
def supplier_delete(request, id):
    if request.method == 'POST' and request.POST.get('_method') == 'DELETE':
        token = request.session.get('token')
        response = api_call('DELETE', f'/api/suppliers/{id}/', token=token)
        if response.status_code == 204:
            messages.success(request, 'Supplier deleted successfully.')
        else:
            messages.error(request, 'Failed to delete supplier. It might have associated products.')
    return redirect('template-supplier-list')