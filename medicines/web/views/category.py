from django.shortcuts import render, redirect
from django.contrib import messages
from urllib.parse import urlencode
from medicines.web.api_helper import *
from medicines.web.decorators import * 

# === Categories ===
@login_required_template
@pharmacy_staff_required
def categories_list(request):
    token = request.session.get('token')

    current_page = request.GET.get('page', 1)
    search_query = request.GET.get('search', '')
    ordering = request.GET.get('ordering', '')
    # FIX: Replaced unsupported 'depth' filter with DB-supported 'parent__isnull'
    # e.g., ?parent__isnull=true fetches root categories (depth 0)
    parent_isnull = request.GET.get('parent__isnull', '') 

    api_params = {k: v for k, v in {
        'page': current_page,
        'search': search_query,
        'ordering': ordering,
        'parent__isnull': parent_isnull,
    }.items() if v}

    api_url = f'/api/categories/?{urlencode(api_params)}'
    response = api_call('GET', api_url, token=token)

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

    return render(request, 'categories/categories.html', {
        'categories': categories,
        'next_page': next_page,
        'prev_page': prev_page,
        'count': count,
        'current_page': current_page,
        'search_query': search_query,
        'ordering': ordering,
        'parent_isnull': parent_isnull, # Updated context variable
    })
    
@login_required_template
@pharmacy_staff_required
def category_create(request):
    token = request.session.get('token')
    errors = {}
    old_input = {}

    if request.method == 'POST':
        old_input = request.POST.dict()
        old_input['is_active'] = 'is_active' in request.POST
        
        payload = {
            'name': old_input.get('name'),
            'product_type_id': old_input.get('product_type_id') or None,
            'parent_id': old_input.get('parent_id') or None,
            'is_active': old_input['is_active'],
        }

        files = {'image': request.FILES['image']} if 'image' in request.FILES else None

        response = api_call('POST', '/api/categories/', data=payload, token=token, files=files)

        if response.status_code == 201:
            messages.success(request, 'Category created successfully!')
            return redirect('template-category-list')
        elif response.status_code == 400:
            errors = response.json()
        else:
            messages.error(request, 'An unexpected error occurred.')

    # FIX: Fetch ALL pages for dropdowns
    product_types = fetch_all_api_data('/api/product-types/', token)
    parent_categories = fetch_all_api_data('/api/categories/', token)

    return render(request, 'categories/category_form.html', {
        'edit_mode': False, 'errors': errors,
        'product_types': product_types,
        'parent_categories': parent_categories,
        'category': old_input or {},
    })

# === Category Detail (Updated) ===
@login_required_template
@pharmacy_staff_required
def category_detail(request, id):
    token = request.session.get('token')
    
    cat_response = api_call('GET', f'/api/categories/{id}/', token=token)
    if cat_response.status_code != 200:
        messages.error(request, 'Category not found.')
        return redirect('template-category-list')
    category = cat_response.json()

    # Fetch Ancestors (for Breadcrumbs)
    anc_response = api_call('GET', f'/api/categories/{id}/ancestors/', token=token)
    ancestors = anc_response.json() if anc_response.status_code == 200 else []

    # Fetch Descendants
    desc_response = api_call('GET', f'/api/categories/{id}/descendants/', token=token)
    descendants = desc_response.json() if desc_response.status_code == 200 else []

    # Fetch Stock Summary
    stock_response = api_call('GET', f'/api/categories/{id}/stock_summary/', token=token)
    stock_summary = stock_response.json() if stock_response.status_code == 200 else None

    # Fetch Products (Paginated)
    page = request.GET.get('page', 1)
    prod_response = api_call('GET', f'/api/categories/{id}/products/?page={page}', token=token)
    products = []
    next_page = prev_page = None
    count = 0
    if prod_response.status_code == 200:
        data = prod_response.json()
        products = data.get('results', [])
        count = data.get('count', 0)
        if data.get('next'): next_page = data['next'].split('page=')[-1]
        if data.get('previous'): prev_page = 1 if 'page=' not in data['previous'] else data['previous'].split('page=')[-1]

    return render(request, 'categories/category_detail.html', {
        'category': category,
        'ancestors': ancestors,
        'descendants': descendants,
        'stock_summary': stock_summary,
        'products': products,
        'next_page': next_page, 'prev_page': prev_page, 'count': count, 'current_page': page,
    })


# === Category Edit (PATCH) ===
@login_required_template
@pharmacy_staff_required
def category_edit(request, id):
    token = request.session.get('token')
    errors = {}

    cat_response = api_call('GET', f'/api/categories/{id}/', token=token)
    if cat_response.status_code != 200:
        messages.error(request, 'Category not found')
        return redirect('template-category-list')
    category_data = cat_response.json()

    if request.method == 'POST':
        old_input = request.POST.dict()
        old_input['is_active'] = 'is_active' in request.POST
        
        payload = {
            'name': old_input.get('name'),
            'product_type_id': old_input.get('product_type_id') or None,
            'parent_id': old_input.get('parent_id') or None,
            'is_active': old_input['is_active'],
        }

        files = {'image': request.FILES['image']} if 'image' in request.FILES else None

        response = api_call('PATCH', f'/api/categories/{id}/', data=payload, token=token, files=files)

        if response.status_code == 200:
            messages.success(request, 'Category updated successfully!')
            return redirect('template-category-list')
        elif response.status_code == 400:
            errors = response.json()
            category_data.update(old_input)
        else:
            messages.error(request, 'Failed to update category.')

    # FIX: Fetch ALL pages for dropdowns
    product_types = fetch_all_api_data('/api/product-types/', token)
    parent_categories = fetch_all_api_data('/api/categories/', token)

    # Exclude current category from parent options
    parent_categories = [c for c in parent_categories if c.get('id') != id]

    return render(request, 'categories/category_form.html', {
        'edit_mode': True, 'category': category_data, 'errors': errors,
        'product_types': product_types,
        'parent_categories': parent_categories,
    })


# === Category Delete (DELETE) ===
@login_required_template
@pharmacy_staff_required
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

    return redirect('template-category-list')


# === Category Tree View ===
@login_required_template
@pharmacy_staff_required
def category_tree(request):
    token = request.session.get('token')
    
    # 1. Capture the selected product type filtering parameter
    selected_product_type = request.GET.get('product_type', '')
    
    tree_data = []
    
    # 2. Only request tree hierarchies if a type parameter context exists 
    if selected_product_type:
        api_url = f'/api/categories/tree/?product_type={selected_product_type}'
        response = api_call('GET', api_url, token=token)
        if response.status_code == 200:
            tree_data = response.json()
        else:
            messages.error(request, 'Failed to load category tree structure.')
            
    # 3. Fetch product types so your HTML page can provide a select/dropdown menu
    pt_response = api_call('GET', '/api/product-types/', token=token)
    product_types = pt_response.json().get('results', []) if pt_response.status_code == 200 else []
    
    return render(request, 'categories/category_tree.html', {
        'tree_data': tree_data,
        'product_types': product_types,
        'selected_product_type': selected_product_type,
    })

# === Category Roots View ===
@login_required_template
@pharmacy_staff_required
def category_roots(request):
    token = request.session.get('token')
    response = api_call('GET', '/api/categories/roots/', token=token)
    roots = response.json() if response.status_code == 200 else []
    # Note: API might return paginated results for roots. If so, handle page logic here.
    return render(request, 'categories/category_roots.html', {'roots': roots})

# === Category Bulk Move ===
@login_required_template
@pharmacy_staff_required
def category_bulk_move(request):
    token = request.session.get('token')
    errors = {}

    if request.method == 'POST':
        # Extract list of IDs from checked checkboxes
        category_ids = request.POST.getlist('category_ids')
        new_parent_id = request.POST.get('new_parent_id') or None

        if not category_ids:
            messages.error(request, "Please select at least one category to move.")
        else:
            payload = {
                "category_ids": [int(cid) for cid in category_ids],
                "new_parent_id": int(new_parent_id) if new_parent_id else None
            }
            response = api_call('POST', '/api/categories/bulk_move/', data=payload, token=token)
            
            if response.status_code == 200:
                data = response.json()
                moved_count = len(data.get('moved', []))
                messages.success(request, f'Successfully moved {moved_count} categories.')
                return redirect('template-category-list')
            else:
                messages.error(request, 'Failed to move categories.')

    # Fetch all categories for the selection list and parent dropdown
    cat_response = api_call('GET', '/api/categories/?page_size=100', token=token)
    categories = cat_response.json().get('results', []) if cat_response.status_code == 200 else []

    return render(request, 'categories/category_bulk_move.html', {
        'categories': categories,
        'errors': errors
    })