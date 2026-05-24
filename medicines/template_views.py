from django.shortcuts import render, redirect
from django.contrib import messages
from .api_helper import *

def home(request):
    return render(request, 'home.html')

def login_page(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Step 1: Get the token
        response = api_call(
            'POST', 
            '/api/login/', 
            data={'username': username, 'password': password}
        )
        
        if response.status_code == 200:
            data = response.json()
            token = data['token']
            
            # Step 2: Get full user info (including role)
            me_response = api_call('GET', '/api/users/me/', token=token)
            user_data = me_response.json()
            
            # Step 3: Store everything in session
            request.session['token'] = token
            request.session['user_id'] = data['user_id']
            request.session['username'] = data['username']
            request.session['role'] = user_data['role']
            
            return redirect('home')
        else:
            messages.error(request, 'Invalid username or password')
    
    return render(request, 'login.html')