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
        payload = {
            'doctor_id': old_input.get('doctor_id') or None,
            'patient_id': old_input.get('patient_id') or None,
            'prescription_date': old_input.get('prescription_date'),
            'notes': old_input.get('notes', ''),
            'items': []
        }

        # Assemble items
        product_ids = request.POST.getlist('product_id[]')
        quantities = request.POST.getlist('quantity_prescribed[]')
        dosages = request.POST.getlist('dosage_instructions[]')

        for i in range(len(product_ids)):
            if product_ids[i]:
                payload['items'].append({
                    'product': int(product_ids[i]),       # FIX: Standard DRF relational key expectation
                    'product_id': int(product_ids[i]),    # Kept as fallback for explicit primary key configurations
                    'quantity_prescribed': int(quantities[i]),
                    'dosage_instructions': dosages[i]
                })

        response = api_call('POST', '/api/prescriptions/', data=payload, token=token)
        if response.status_code == 201:
            messages.success(request, 'Prescription created successfully.')
            return redirect('template-prescription-list')
        elif response.status_code == 400:
            errors = response.json()
            messages.error(request, 'Failed to create prescription.')
        else:
            # --- START DEBUGGING BLOCK ---
            print("\n" + "="*50)
            print(f"DEBUG: API returned unexpected status code: {response.status_code}")
            try:
                print(f"DEBUG: Response JSON: {response.json()}")
            except Exception:
                print(f"DEBUG: Raw Response Text: {response.text[:500]}") # limit output
            print("="*50 + "\n")
            
            # Pass the status code to the UI so you know what happened immediately
            messages.error(request, f'An unexpected error occurred (API Status {response.status_code}).')
            # --- END DEBUGGING BLOCK ---

    return render(request, 'prescriptions/prescription_form.html', {
        'errors': errors,
        'old_input': old_input,
    })

@login_required_template
def prescription_dispense(request, id):
    token = request.session.get('token')
    errors = {}

    # 1. Fetch the specific prescription
    rx_response = api_call('GET', f'/api/prescriptions/{id}/', token=token)
    if rx_response.status_code != 200:
        messages.error(request, 'Prescription not found.')
        return redirect('template-prescription-list')
    
    prescription = _parse_prescription_dates([rx_response.json()])[0]

    # Ensure it's verified before allowing dispense
    if prescription.get('status') != 'verified':
        messages.error(request, 'Only verified prescriptions can be dispensed.')
        return redirect('template-prescription-detail', id=id)

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'cash')
        
        product_ids = request.POST.getlist('product_id[]')
        quantities = request.POST.getlist('quantity[]')
        unit_prices = request.POST.getlist('unit_price[]')

        sale_items = []
        for i in range(len(product_ids)):
            sale_items.append({
                'product_id': int(product_ids[i]),
                'quantity': int(quantities[i]),
                'unit_price': unit_prices[i]
            })

        payload = {
            'prescription_id': prescription['id'],
            'payment_method': payment_method,
            'items': sale_items,
            'notes': f"Dispensed from Prescription #{prescription['prescription_number']}"
        }

        # 3. Create the Sale via API
        response = api_call('POST', '/api/sales/', data=payload, token=token)
        if response.status_code == 201:
            sale_id = response.json().get('id')
            messages.success(request, f"Prescription {prescription['prescription_number']} dispensed successfully!")
            return redirect('template-sale-detail', id=sale_id)
        else:
            errors = response.json()
            messages.error(request, 'Failed to dispense prescription. Check stock availability.')

    # GET Request: Enrich prescription items with current product prices
    total_amount = 0
    enriched_items = []
    
    for item in prescription.get('items', []):
        prod_id = item.get('product') # Now this will actually return the ID (e.g., 5)
        qty = item.get('quantity_prescribed', 0)
        price = 0.0
        
        if prod_id:
            # Fetch the specific product to get the live selling_price
            prod_res = api_call('GET', f'/api/products/{prod_id}/', token=token)
            if prod_res.status_code == 200:
                prod_data = prod_res.json()
                # Your model uses DecimalField, which DRF coerces to string
                price_str = prod_data.get('selling_price', '0') or '0'
                try:
                    price = float(price_str)
                except (ValueError, TypeError):
                    price = 0.0
            else:
                messages.warning(request, f"Failed to fetch price for product ID {prod_id}")
        
        subtotal = qty * price
        total_amount += subtotal
        
        enriched_items.append({
            **item, 
            'unit_price': price,
            'subtotal': subtotal
        })
        
    # Overwrite the items with our enriched data
    prescription['items'] = enriched_items
    prescription['calculated_total'] = total_amount

    return render(request, 'prescriptions/prescription_dispense.html', {
        'prescription': prescription,
        'errors': errors,
    })