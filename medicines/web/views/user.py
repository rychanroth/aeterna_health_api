# medicines/web/views/user.py
from django.shortcuts import render, redirect
from django.contrib import messages
from urllib.parse import urlencode
from medicines.web.api_helper import *
from medicines.web.decorators import login_required_template, role_required

@login_required_template
@role_required(['admin'])
def user_list(request):
    token = request.session.get('token')
    current_page = request.GET.get('page', 1)
    search_query = request.GET.get('search', '')
    role_filter = request.GET.get('role', '')

    api_params = {k: v for k, v in {
        'page': current_page, 'search': search_query, 'role': role_filter
    }.items() if v}

    api_url = f'/api/users/?{urlencode(api_params)}'
    response = api_call('GET', api_url, token=token)

    users, next_page, prev_page, count = [], None, None, 0
    if response.status_code == 200:
        data = response.json()
        users = data.get('results', [])
        count = data.get('count', 0)
        if data.get('next'): next_page = data['next'].split('page=')[-1]
        if data.get('previous'): prev_page = 1 if 'page=' not in data['previous'] else data['previous'].split('page=')[-1]
    else:
        messages.error(request, 'Failed to load users.')

    return render(request, 'users/user_list.html', {
        'users': users, 'count': count,
        'next_page': next_page, 'prev_page': prev_page, 'current_page': current_page,
        'search_query': search_query, 'role_filter': role_filter,
    })

@login_required_template
@role_required(['admin'])
def user_create(request):
    token = request.session.get('token')
    errors = {}
    old_input = {}

    if request.method == 'POST':
        old_input = request.POST.dict()
        payload = {
            'username': old_input.get('username'),
            'first_name': old_input.get('first_name'),
            'last_name': old_input.get('last_name'),
            'phone': old_input.get('phone'),
            'role': old_input.get('role'),
            'is_active': old_input.get('is_active') == 'on',
            'password': old_input.get('password'), # Add password to payload
        }
        files = {'image': request.FILES['image']} if 'image' in request.FILES else None

        response = api_call('POST', '/api/users/', data=payload, token=token, files=files)
        if response.status_code == 201:
            messages.success(request, 'User created successfully.')
            return redirect('template-user-list')
        elif response.status_code == 400:
            errors = response.json()
        else:
            messages.error(request, 'Failed to create user.')

    return render(request, 'users/user_form.html', {
        'edit_mode': False, 'errors': errors, 'user': old_input
    })

@login_required_template
def user_me(request):
    token = request.session.get('token')
    response = api_call('GET', '/api/users/me/', token=token)
    
    if response.status_code != 200:
        messages.error(request, 'Failed to load profile.')
        return redirect('home')
    
    profile_data = response.json()
    
    # Parse date_joined if it exists
    if profile_data.get('date_joined'):
        from django.utils.dateparse import parse_datetime
        profile_data['date_joined'] = parse_datetime(profile_data['date_joined'])
        
    return render(request, 'users/user_profile.html', {'profile': profile_data})

@login_required_template
@role_required(['admin'])
def user_edit(request, id):
    token = request.session.get('token')
    errors = {}

    response = api_call('GET', f'/api/users/{id}/', token=token)
    if response.status_code != 200:
        messages.error(request, 'User not found.')
        return redirect('template-user-list')
    user_data = response.json()

    if request.method == 'POST':
        old_input = request.POST.dict()
        payload = {
            'username': old_input.get('username'),
            'first_name': old_input.get('first_name'),
            'last_name': old_input.get('last_name'),
            'phone': old_input.get('phone'),
            'role': old_input.get('role'),
        }
        files = {'image': request.FILES['image']} if 'image' in request.FILES else None

        response = api_call('PATCH', f'/api/users/{id}/', data=payload, token=token, files=files)
        if response.status_code == 200:
            messages.success(request, 'User updated successfully.')
            return redirect('template-user-list')
        elif response.status_code == 400:
            errors = response.json()
            user_data.update(old_input)
        else:
            messages.error(request, 'Failed to update user.')

    return render(request, 'users/user_form.html', {
        'edit_mode': True, 'errors': errors, 'user': user_data
    })


@login_required_template
@role_required(['admin'])
def user_delete(request, id):
    # SAFETY: Cannot delete primary Admin (id=1) or currently logged in user
    current_user_id = request.session.get('user_id')
    if id == 1:
        messages.error(request, "Cannot delete the primary Administrator account.")
        return redirect('template-user-list')
    if id == current_user_id:
        messages.error(request, "You cannot delete your own account.")
        return redirect('template-user-list')

    if request.method == 'POST' and request.POST.get('_method') == 'DELETE':
        token = request.session.get('token')
        response = api_call('DELETE', f'/api/users/{id}/', token=token)
        if response.status_code == 204:
            messages.success(request, 'User deleted.')
        else:
            messages.error(request, 'Failed to delete user.')
    return redirect('template-user-list')