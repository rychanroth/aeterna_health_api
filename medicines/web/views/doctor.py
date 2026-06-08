from django.shortcuts import render, redirect
from django.contrib import messages
from urllib.parse import urlencode
from medicines.web.api_helper import *
from medicines.web.decorators import *

@login_required_template
@pharmacy_staff_required
def doctor_list(request):
    token = request.session.get('token')
    current_page = request.GET.get('page', 1)
    search_query = request.GET.get('search', '')
    ordering = request.GET.get('ordering', '')

    api_params = {k: v for k, v in {
        'page': current_page, 'search': search_query, 'ordering': ordering
    }.items() if v}

    response = api_call('GET', f'/api/doctors/?{urlencode(api_params)}', token=token)
    
    doctors, next_page, prev_page, count = [], None, None, 0
    if response.status_code == 200:
        data = response.json()
        doctors = data.get('results', [])
        count = data.get('count', 0)
        if data.get('next'): next_page = data['next'].split('page=')[-1]
        if data.get('previous'): prev_page = 1 if 'page=' not in data['previous'] else data['previous'].split('page=')[-1]
    else:
        messages.error(request, 'Failed to load doctors.')

    return render(request, 'doctors/doctor_list.html', {
        'doctors': doctors, 'next_page': next_page, 'prev_page': prev_page, 
        'count': count, 'current_page': current_page, 'search_query': search_query, 'ordering': ordering
    })

@login_required_template
@pharmacy_staff_required
def doctor_create(request):
    token = request.session.get('token')
    errors, old_input = {}, {}

    if request.method == 'POST':
        old_input = request.POST.dict()
        old_input['is_active'] = 'is_active' in request.POST
        
        payload = {
            'name': old_input.get('name'), 'license_number': old_input.get('license_number'),
            'phone': old_input.get('phone'), 'clinic_name': old_input.get('clinic_name'),
            'clinic_address': old_input.get('clinic_address'), 'is_active': old_input['is_active']
        }
        files = {'image': request.FILES['image']} if 'image' in request.FILES else None
        
        response = api_call('POST', '/api/doctors/', data=payload, token=token, files=files)
        if response.status_code == 201:
            messages.success(request, 'Doctor created successfully!')
            return redirect('template-doctor-list')
        elif response.status_code == 400: errors = response.json()
        else: messages.error(request, 'An unexpected error occurred.')

    return render(request, 'doctors/doctor_form.html', {
        'edit_mode': False, 'errors': errors, 'doctor': old_input or {}
    })

@login_required_template
@pharmacy_staff_required
def doctor_detail(request, id):
    token = request.session.get('token')
    response = api_call('GET', f'/api/doctors/{id}/', token=token)
    if response.status_code != 200:
        messages.error(request, 'Doctor not found.')
        return redirect('template-doctor-list')
    return render(request, 'doctors/doctor_detail.html', {'doctor': response.json()})

@login_required_template
@pharmacy_staff_required
def doctor_edit(request, id):
    token = request.session.get('token')
    errors = {}
    response = api_call('GET', f'/api/doctors/{id}/', token=token)
    if response.status_code != 200:
        messages.error(request, 'Doctor not found')
        return redirect('template-doctor-list')
    doctor_data = response.json()

    if request.method == 'POST':
        old_input = request.POST.dict()
        old_input['is_active'] = 'is_active' in request.POST
        payload = {
            'name': old_input.get('name'), 'license_number': old_input.get('license_number'),
            'phone': old_input.get('phone'), 'clinic_name': old_input.get('clinic_name'),
            'clinic_address': old_input.get('clinic_address'), 'is_active': old_input['is_active']
        }
        files = {'image': request.FILES['image']} if 'image' in request.FILES else None
        
        response = api_call('PATCH', f'/api/doctors/{id}/', data=payload, token=token, files=files)
        if response.status_code == 200:
            messages.success(request, 'Doctor updated successfully!')
            return redirect('template-doctor-list')
        elif response.status_code == 400:
            errors = response.json()
            doctor_data.update(old_input)
        else: messages.error(request, 'Failed to update doctor.')

    return render(request, 'doctors/doctor_form.html', {
        'edit_mode': True, 'doctor': doctor_data, 'errors': errors
    })

@login_required_template
@pharmacy_staff_required
def doctor_delete(request, id):
    if request.method == 'POST' and request.POST.get('_method') == 'DELETE':
        token = request.session.get('token')
        response = api_call('DELETE', f'/api/doctors/{id}/', token=token)
        if response.status_code == 204: messages.success(request, 'Doctor deleted.')
        else: messages.error(request, 'Failed to delete doctor.')
    return redirect('template-doctor-list')