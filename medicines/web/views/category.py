from django.shortcuts import render, redirect
from django.contrib import messages
from urllib.parse import urlencode
from medicines.web.api_helper import *
from medicines.web.decorators import * 

# === Categories ===
@login_required_template
def categories_list(request):
    token = request.session.get('token')
    
    # 1. Capture all possible query parameters from the user's request
    current_page = request.GET.get('page', 1)
    search_query = request.GET.get('search', '')
    ordering = request.GET.get('ordering', '') # e.g., 'name', '-created_at', 'depth'
    
    # 2. Build the API parameters dictionary
    api_params = {
        'page': current_page,
        'search': search_query,
        'ordering': ordering,
    }
    
    # Remove keys with empty values so we don't send ?search=&ordering= to the API
    api_params = {k: v for k, v in api_params.items() if v}
    
    # 3. Construct the clean API URL
    api_url = f'/api/categories/?{urlencode(api_params)}'
    response = api_call('GET', api_url, token=token)
    
    # 4. Setup default values
    categories = []
    next_page = None
    prev_page = None
    count = 0
    
    if response.status_code == 200:
        data = response.json()
        categories = data.get('results', [])
        count = data.get('count', 0)
        
        if data.get('next'):
            next_page = data['next'].split('page=')[-1]
            
        if data.get('previous'):
            if 'page=' in data['previous']:
                prev_page = data['previous'].split('page=')[-1]
            else:
                prev_page = 1
                
    else:
        messages.error(request, 'Failed to load categories')
    
    # 5. Pass variables to the template, including the new ordering filter
    return render(request, 'categories/categories.html', {
        'categories': categories,
        'next_page': next_page,
        'prev_page': prev_page,
        'count': count,
        'current_page': current_page,
        'search_query': search_query,
        'ordering': ordering,
    })
    
@login_required_template
def category_create(request):
    token = request.session.get('token')
    errors = {}
    old_input = {} # Initialize empty

    if request.method == 'POST':
        data = {
            'name': request.POST.get('name'),
            'product_type_id': request.POST.get('product_type_id') or None,
            'parent_id': request.POST.get('parent_id') or None,
            'is_active': request.POST.get('is_active') == 'on',
        }

        files = None
        if 'image' in request.FILES:
            files = {'image': request.FILES['image']}

        response = api_call('POST', '/api/categories/', data=data, token=token, files=files)

        if response.status_code == 201:
            messages.success(request, 'Category created successfully!')
            return redirect('template_categories')
        else:
            if response.status_code == 400:
                errors = response.json()
                old_input = request.POST # <--- KEEP THE OLD INPUT ALIVE
            else:
                messages.error(request, 'An unexpected error occurred.')

    # Fetch dropdown data
    pt_response = api_call('GET', '/api/product-types/', token=token)
    product_types = pt_response.json().get('results', []) if pt_response.status_code == 200 else []

    cat_response = api_call('GET', '/api/categories/?page_size=50', token=token) 
    parent_categories = cat_response.json().get('results', []) if cat_response.status_code == 200 else []

    return render(request, 'categories/category_form.html', {
        'edit_mode': False,
        'errors': errors,
        'product_types': product_types,
        'parent_categories': parent_categories,
        'category': old_input or {}, # <--- PASS IT AS CATEGORY CONTEXT
    })

# === Category Detail (GET) ===
@login_required_template
def category_detail(request, id):
    token = request.session.get('token')
    
    # 1. Fetch the single category
    cat_response = api_call('GET', f'/api/categories/{id}/', token=token)
    
    if cat_response.status_code == 404:
        messages.error(request, 'Category not found.')
        return redirect('template_categories')
    if cat_response.status_code != 200:
        messages.error(request, 'Failed to load category details.')
        return redirect('template_categories')
        
    category = cat_response.json()

    # 2. Fetch descendant categories (assuming API returns a flat list ordered by tree)
    desc_response = api_call('GET', f'/api/categories/{id}/descendants/', token=token)
    descendants = desc_response.json() if desc_response.status_code == 200 else []

    # 3. Fetch products in this category (paginated)
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
            prev_page = 1 if 'page=' not in data['previous'] else data['previous'].split('page=')[-1]

    return render(request, 'categories/category_detail.html', {
        'category': category,
        'descendants': descendants,
        'products': products,
        'next_page': next_page,
        'prev_page': prev_page,
        'count': count,
        'current_page': page,
    })


# === Category Edit (PATCH) ===
@login_required_template
def category_edit(request, id):
    token = request.session.get('token')
    errors = {}

    # 1. Fetch the existing category to pre-populate the form
    cat_response = api_call('GET', f'/api/categories/{id}/', token=token)
    if cat_response.status_code != 200:
        messages.error(request, 'Category not found')
        return redirect('template_categories')
    category_data = cat_response.json()

    # 2. Handle form submission
    if request.method == 'POST':
        # Convert QueryDict to standard dict and handle types for our template "old()" logic
        old_input = request.POST.dict()
        old_input['is_active'] = request.POST.get('is_active') == 'on'
        
        payload = {
            'name': request.POST.get('name'),
            'product_type_id': request.POST.get('product_type_id') or None,
            'parent_id': request.POST.get('parent_id') or None,
            'is_active': old_input['is_active'],
        }

        files = None
        if 'image' in request.FILES:
            files = {'image': request.FILES['image']}

        # 3. Use PATCH
        response = api_call('PATCH', f'/api/categories/{id}/', data=payload, token=token, files=files)

        if response.status_code == 200:
            messages.success(request, 'Category updated successfully!')
            return redirect('template_categories')
        else:
            if response.status_code == 400:
                errors = response.json()
                # Merge old input over API data so the template repopulates the failed form
                category_data.update(old_input)
            else:
                messages.error(request, 'Failed to update category.')

    # Fetch product types and parent categories for dropdowns
    pt_response = api_call('GET', '/api/product-types/', token=token)
    product_types = pt_response.json().get('results', []) if pt_response.status_code == 200 else []

    cat_response_all = api_call('GET', '/api/categories/?page_size=50', token=token) 
    parent_categories = cat_response_all.json().get('results', []) if cat_response_all.status_code == 200 else []

    # Exclude current category from parent options (a category can't be its own parent)
    parent_categories = [c for c in parent_categories if c.get('id') != id]

    return render(request, 'categories/category_form.html', {
        'edit_mode': True,
        'category': category_data,
        'errors': errors,
        'product_types': product_types,
        'parent_categories': parent_categories,
    })


# === Category Delete (DELETE) ===
@login_required_template
def category_delete(request, id):
    # Only process if it's our special POST disguised as DELETE
    if request.method == 'POST' and request.POST.get('_method') == 'DELETE':
        token = request.session.get('token')
        response = api_call('DELETE', f'/api/categories/{id}/', token=token)

        if response.status_code == 204:
            messages.success(request, 'Category deleted successfully.')
        else:
            # Often fails if it has children/products depending on API constraints
            messages.error(request, 'Failed to delete category. Ensure it has no child categories or products.')

    return redirect('template_categories')