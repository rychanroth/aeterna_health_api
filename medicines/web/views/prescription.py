from django.shortcuts import render, redirect
from django.contrib import messages
from urllib.parse import urlencode
from django.utils.dateparse import parse_datetime
from medicines.web.api_helper import *
from medicines.web.decorators import *

def _parse_prescription_dates(prescriptions):
    for rx in prescriptions:
        if rx.get('created_at'):
            rx['created_at'] = parse_datetime(rx['created_at'])
    return prescriptions

@login_required_template
def prescription_list(request):
    token = request.session.get('token')
    current_page = request.GET.get('page', 1)
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    api_params = {k: v for k, v in {
        'page': current_page, 'search': search_query, 'status': status_filter
    }.items() if v}

    # Determine if we hit a custom action endpoint or the main list
    if status_filter == 'pending':
        api_url = f'/api/prescriptions/pending/?{urlencode(api_params)}'
    elif status_filter == 'verified':
        api_url = f'/api/prescriptions/verified/?{urlencode(api_params)}'
    else:
        api_url = f'/api/prescriptions/?{urlencode(api_params)}'

    response = api_call('GET', api_url, token=token)
    
    prescriptions, next_page, prev_page, count = [], None, None, 0
    if response.status_code == 200:
        data = response.json()
        # Custom actions return flat lists, main endpoint returns paginated dict
        if isinstance(data, list):
            prescriptions = _parse_prescription_dates(data)
            count = len(prescriptions)
        else:
            prescriptions = _parse_prescription_dates(data.get('results', []))
            count = data.get('count', 0)
            if data.get('next'): next_page = data['next'].split('page=')[-1]
            if data.get('previous'): prev_page = 1 if 'page=' not in data['previous'] else data['previous'].split('page=')[-1]
    else:
        messages.error(request, 'Failed to load prescriptions.')

    return render(request, 'prescriptions/prescription_list.html', {
        'prescriptions': prescriptions, 'count': count,
        'next_page': next_page, 'prev_page': prev_page, 'current_page': current_page,
        'search_query': search_query, 'status_filter': status_filter,
    })

@login_required_template
def prescription_detail(request, id):
    token = request.session.get('token')
    response = api_call('GET', f'/api/prescriptions/{id}/', token=token)
    if response.status_code != 200:
        messages.error(request, 'Prescription not found.')
        return redirect('template-prescription-list')
    
    prescription = _parse_prescription_dates([response.json()])[0]
    return render(request, 'prescriptions/prescription_detail.html', {'prescription': prescription})

@login_required_template
def prescription_verify(request, id):
    if request.method == 'POST':
        token = request.session.get('token')
        response = api_call('POST', f'/api/prescriptions/{id}/verify/', token=token)
        if response.status_code == 200:
            messages.success(request, 'Prescription verified successfully.')
        else:
            err_msg = response.json().get('error', 'Failed to verify prescription.')
            messages.error(request, err_msg)
    return redirect('template-prescription-detail', id=id)

@login_required_template
def prescription_reject(request, id):
    if request.method == 'POST':
        token = request.session.get('token')
        response = api_call('POST', f'/api/prescriptions/{id}/reject/', token=token)
        if response.status_code == 200:
            messages.success(request, 'Prescription rejected.')
        else:
            err_msg = response.json().get('error', 'Failed to reject prescription.')
            messages.error(request, err_msg)
    return redirect('template-prescription-detail', id=id)

@login_required_template
def prescription_create(request):
    token = request.session.get('token')
    errors = {}
    old_input = request.POST.dict() if request.method == 'POST' else {}

    if request.method == 'POST':
        # Assemble the nested items payload from parallel arrays
        product_ids = request.POST.getlist('product_id[]')
        quantities = request.POST.getlist('quantity_prescribed[]')
        dosages = request.POST.getlist('dosage_instructions[]')

        items = []
        for i in range(len(product_ids)):
            if product_ids[i]: # Only add if a product was selected
                items.append({
                    'product_id': int(product_ids[i]),
                    'quantity_prescribed': int(quantities[i]),
                    'dosage_instructions': dosages[i]
                })

        payload = {
            'doctor_id': old_input.get('doctor_id') or None,
            'patient_id': old_input.get('patient_id') or None,
            'prescription_date': old_input.get('prescription_date'),
            'notes': old_input.get('notes', ''),
            'items': items
        }

        response = api_call('POST', '/api/prescriptions/', data=payload, token=token)
        if response.status_code == 201:
            messages.success(request, 'Prescription created successfully.')
            return redirect('template-prescription-list')
        elif response.status_code == 400:
            errors = response.json()
            messages.error(request, 'Failed to create prescription. Check form errors.')
        else:
            messages.error(request, 'An unexpected error occurred.')

    # Fetch dropdown data
    doctors_res = api_call('GET', '/api/doctors/?page_size=50', token=token)
    doctors = doctors_res.json().get('results', []) if doctors_res.status_code == 200 else []

    patients_res = api_call('GET', '/api/patients/?page_size=50', token=token)
    patients = patients_res.json().get('results', []) if patients_res.status_code == 200 else []

    products_res = api_call('GET', '/api/products/?page_size=100', token=token)
    products = products_res.json().get('results', []) if products_res.status_code == 200 else []

    return render(request, 'prescriptions/prescription_form.html', {
        'errors': errors, 'old_input': old_input,
        'doctors': doctors, 'patients': patients, 'products': products,
    })