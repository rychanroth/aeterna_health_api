# medicines/web/views/patient.py
from django.shortcuts import render, redirect
from django.contrib import messages
from urllib.parse import urlencode
from medicines.web.api_helper import *
from medicines.web.decorators import *

@login_required_template
@pharmacy_staff_required
def patient_list(request):
    token = request.session.get('token')
    current_page = request.GET.get('page', 1)
    search_query = request.GET.get('search', '')
    ordering = request.GET.get('ordering', '')
    allergy_filter = request.GET.get('allergies', '')

    api_params = {k: v for k, v in {
        'page': current_page, 'search': search_query, 'ordering': ordering
    }.items() if v}

    # FIX: Use the django-filter parameter instead of the deleted custom action endpoint
    if allergy_filter == 'true':
        api_params['with_allergies'] = 'true'

    api_url = f'/api/patients/?{urlencode(api_params)}'
    response = api_call('GET', api_url, token=token)

    patients, next_page, prev_page, count = [], None, None, 0
    if response.status_code == 200:
        data = response.json()
        patients = data.get('results', [])
        count = data.get('count', 0)
        if data.get('next'): next_page = data['next'].split('page=')[-1]
        if data.get('previous'): prev_page = 1 if 'page=' not in data['previous'] else data['previous'].split('page=')[-1]
    else:
        messages.error(request, 'Failed to load patients.')

    return render(request, 'patients/patient_list.html', {
        'patients': patients, 'next_page': next_page, 'prev_page': prev_page,
        'count': count, 'current_page': current_page, 'search_query': search_query,
        'ordering': ordering, 'allergy_filter': allergy_filter
    })

@login_required_template
@pharmacy_staff_required
def patient_create(request):
    token = request.session.get('token')
    errors, old_input = {}, {}

    if request.method == 'POST':
        old_input = request.POST.dict()
        old_input['is_active'] = request.POST.get('is_active') == 'on'
        
        payload = {
            'name': old_input.get('name'), 'phone': old_input.get('phone'),
            'date_of_birth': old_input.get('date_of_birth'), 'gender': old_input.get('gender'),
            'address': old_input.get('address'), 'allergy_notes': old_input.get('allergy_notes'),
            'is_active': old_input['is_active']
        }
        files = {'image': request.FILES['image']} if 'image' in request.FILES else None
        
        response = api_call('POST', '/api/patients/', data=payload, token=token, files=files)
        if response.status_code == 201:
            messages.success(request, 'Patient created successfully!')
            return redirect('template-patient-list')
        elif response.status_code == 400: errors = response.json()
        else: messages.error(request, 'An unexpected error occurred.')

    return render(request, 'patients/patient_form.html', {
        'edit_mode': False, 'errors': errors, 'patient': old_input or {}
    })

@login_required_template
@pharmacy_staff_required
def patient_detail(request, id):
    token = request.session.get('token')
    response = api_call('GET', f'/api/patients/{id}/', token=token)
    if response.status_code != 200:
        messages.error(request, 'Patient not found.')
        return redirect('template-patient-list')
    return render(request, 'patients/patient_detail.html', {'patient': response.json()})

@login_required_template
@pharmacy_staff_required
def patient_edit(request, id):
    token = request.session.get('token')
    errors = {}
    response = api_call('GET', f'/api/patients/{id}/', token=token)
    if response.status_code != 200:
        messages.error(request, 'Patient not found')
        return redirect('template-patient-list')
    patient_data = response.json()

    if request.method == 'POST':
        old_input = request.POST.dict()
        old_input['is_active'] = request.POST.get('is_active') == 'on'
        payload = {
            'name': old_input.get('name'), 'phone': old_input.get('phone'),
            'date_of_birth': old_input.get('date_of_birth'), 'gender': old_input.get('gender'),
            'address': old_input.get('address'), 'allergy_notes': old_input.get('allergy_notes'),
            'is_active': old_input['is_active']
        }
        files = {'image': request.FILES['image']} if 'image' in request.FILES else None
        
        response = api_call('PATCH', f'/api/patients/{id}/', data=payload, token=token, files=files)
        if response.status_code == 200:
            messages.success(request, 'Patient updated successfully!')
            return redirect('template-patient-list')
        elif response.status_code == 400:
            errors = response.json()
            patient_data.update(old_input)
        else: messages.error(request, 'Failed to update patient.')

    return render(request, 'patients/patient_form.html', {
        'edit_mode': True, 'patient': patient_data, 'errors': errors
    })

@login_required_template
@pharmacy_staff_required
def patient_delete(request, id):
    if request.method == 'POST' and request.POST.get('_method') == 'DELETE':
        token = request.session.get('token')
        response = api_call('DELETE', f'/api/patients/{id}/', token=token)
        if response.status_code == 204: messages.success(request, 'Patient deleted.')
        else: messages.error(request, 'Failed to delete patient.')
    return redirect('template-patient-list')