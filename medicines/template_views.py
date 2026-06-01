from django.shortcuts import render, redirect
from django.contrib import messages
from .api_helper import *
from .decorators import * 

@login_required_template
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

def logout_view(request):
    request.session.flush() # use flush, not clear 
    return redirect('template_login')

# === Categories ===
@login_required_template
def categories_list(request):
    token = request.session.get('token')
    
    # 1. What page is the user asking for? Default to 1
    current_page = request.GET.get('page', 1)
    
    # 2. Ask the API for that page
    response = api_call('GET', f'/api/categories/?page={current_page}', token=token)
    
    # 3. Setup default values
    categories = []
    next_page = None
    prev_page = None
    count = 0
    
    if response.status_code == 200:
        data = response.json()
        categories = data.get('results', [])
        count = data.get('count', 0)
        
        # 4. FIGURE OUT THE PAGE NUMBERS IN PYTHON
        # If 'next' exists, it looks like: "http://127.0.0.1:8000/api/categories/?page=3"
        # We split it by 'page=' and take the last part -> "3"
        if data.get('next'):
            next_page = data['next'].split('page=')[-1]
            
        if data.get('previous'):
            # If 'previous' exists but is empty string (API quirk), it means page 1
            if 'page=' in data['previous']:
                prev_page = data['previous'].split('page=')[-1]
            else:
                prev_page = 1
                
    else:
        messages.error(request, 'Failed to load categories')
    
    # 5. Pass SIMPLE variables to the template
    return render(request, 'categories/categories.html', {
        'categories': categories,
        'next_page': next_page,   # Just a number: "2" or None
        'prev_page': prev_page,   # Just a number: "1" or None
        'count': count,
        'current_page': current_page,
    })

@login_required_template
def category_create(request):
    # For now, just show the form
    return render(request, 'categories/category_form.html', {'edit_mode': False})

@login_required_template
def category_detail(request, id):
    token = request.session.get('token')
    
    # 1. Fetch the single category
    cat_response = api_call('GET', f'/api/categories/{id}/', token=token)
    
    if cat_response.status_code != 200:
        messages.error(request, 'Category not found')
        return redirect('template_categories')
        
    category = cat_response.json()

    # 2. Fetch descendant (children) categories
    desc_response = api_call('GET', f'/api/categories/{id}/descendants/', token=token)
    descendants = []
    if desc_response.status_code == 200:
        descendants = desc_response.json()
    
    # 2. Fetch products in this category (with pagination)
    page = request.GET.get('page', 1)
    prod_response = api_call('GET', f'/api/categories/{id}/products/?page={page}', token=token)
    
    products = []
    next_page = None
    prev_page = None
    count = 0
    
    if prod_response.status_code == 200:
        data = prod_response.json()
        products = data.get('results', [])
        count = data.get('count', 0)
        
        if data.get('next'):
            next_page = data['next'].split('page=')[-1]
        if data.get('previous'):
            if 'page=' in data['previous']:
                prev_page = data['previous'].split('page=')[-1]
            else:
                prev_page = 1
                
    return render(request, 'categories/category_detail.html', {
        'category': category,
        'descendants': descendants,
        'products': products,
        'next_page': next_page,
        'prev_page': prev_page,
        'count': count,
        'current_page': page,
    })
    