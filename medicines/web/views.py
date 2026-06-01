from django.shortcuts import render, redirect
from django.contrib import messages
from medicines.web.api_helper import *
from medicines.web.decorators import * 

@login_required_template
def home(request):
    role = request.session.get('role')
    
    # CASHIER GUARD: Defer POS screen for later
    if role == 'cashier':
        return render(request, 'cashier_placeholder.html')
    
    token = request.session.get('token')
    context = {'role': role}
    
    # 1. Fetch Stock Alerts (Admin & Pharmacist both care about this)
    alerts_response = api_call('GET', '/api/reports/stock_alerts/', token=token)
    if alerts_response.status_code == 200:
        context['alerts'] = alerts_response.json()
        
    # 2. Fetch Prescription Stats (Mostly for Pharmacist)
    rx_response = api_call('GET', '/api/reports/prescription_stats/', token=token)
    if rx_response.status_code == 200:
        context['rx_stats'] = rx_response.json()
        
    # 3. Fetch Sales Summary (Mostly for Admin)
    if role == 'admin':
        sales_response = api_call('GET', '/api/reports/sales_summary/', token=token)
        if sales_response.status_code == 200:
            context['sales'] = sales_response.json()

    return render(request, 'dashboard.html', context)

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
    
    # NEW: Capture the search term (default to empty string)
    search_query = request.GET.get('search', '')

    # 2. Ask the API for that page
    # NEW: Append ?search= to the API call
    api_url = f'/api/categories/?page={current_page}&search={search_query}'
    response = api_call('GET', api_url, token=token)
    
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
    
@login_required_template
def category_create(request):
    token = request.session.get('token')
    errors = {}  # Initialize empty errors dict
    
    if request.method == 'POST':
        data = {
            'name': request.POST.get('name'),
            'product_type_id': request.POST.get('product_type_id'),
        }
        
        # Handle parent dropdown (if selected)
        parent_id = request.POST.get('parent')
        if parent_id:
            data['parent'] = parent_id
            
        # Handle file
        files = None
        if 'image' in request.FILES:
            files = {'image': request.FILES['image']}
            
        response = api_call('POST', '/api/categories/', data=data, token=token, files=files)
        
        if response.status_code == 201:
            messages.success(request, 'Category created successfully!')
            return redirect('template_categories')
        else:
            # Parse the DRF error JSON
            errors = response.json()
    
    # Fetch product types for the dropdown (we'll add the HTML next)
    pt_response = api_call('GET', '/api/product-types/', token=token)
    product_types = pt_response.json().get('results', []) if pt_response.status_code == 200 else []
    
    return render(request, 'categories/category_form.html', {
        'edit_mode': False,
        'errors': errors,
        'product_types': product_types,
    })

@login_required_template
def category_edit(request, id):
    token = request.session.get('token')
    errors = {}
    
    # 1. Fetch the existing category to pre-populate the form
    cat_response = api_call('GET', f'/api/categories/{id}/', token=token)
    if cat_response.status_code != 200:
        messages.error(request, 'Category not found')
        return redirect('template_categories')
    category = cat_response.json()
    
    # 2. Handle form submission
    if request.method == 'POST':
        data = {
            'name': request.POST.get('name'),
            'product_type_id': request.POST.get('product_type_id'),
        }
        
        parent_id = request.POST.get('parent')
        if parent_id:
            data['parent'] = parent_id
            
        files = None
        if 'image' in request.FILES:
            files = {'image': request.FILES['image']}
            
        # 3. USE PATCH (not POST). PATCH only updates the fields you send.
        response = api_call('PATCH', f'/api/categories/{id}/', data=data, token=token, files=files)
        
        if response.status_code == 200:
            messages.success(request, 'Category updated successfully!')
            return redirect('template_categories')
        else:
            errors = response.json()
            
    # Fetch product types for dropdown
    pt_response = api_call('GET', '/api/product-types/', token=token)
    product_types = pt_response.json().get('results', []) if pt_response.status_code == 200 else []
    
    return render(request, 'categories/category_form.html', {
        'edit_mode': True,
        'category': category,
        'errors': errors,
        'product_types': product_types,
    })

@login_required_template
def category_delete(request, id):
    # Only process if it's our special POST disguised as DELETE
    if request.method == 'POST' and request.POST.get('_method') == 'DELETE':
        token = request.session.get('token')
        response = api_call('DELETE', f'/api/categories/{id}/', token=token)
        
        if response.status_code == 204:
            messages.success(request, 'Category deleted.')
        else:
            messages.error(request, 'Failed to delete category.')
            
    return redirect('template_categories')