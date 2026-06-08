# medicines/web/api_helper.py
import requests
from django.conf import settings

def _sanitize_multipart_data(data):
    """
    DRF strictly expects lowercase string booleans ('true'/'false') in multipart/form-data.
    The Python requests library converts Python bools to the string 'True'/'False', which DRF rejects.
    This helper sanitizes the payload to ensure compatibility.
    """
    if not data:
        return data
    
    sanitized = {}
    for key, value in data.items():
        if isinstance(value, bool):
            sanitized[key] = 'true' if value else 'false'
        else:
            sanitized[key] = value
    return sanitized

def api_call(method, endpoint, data=None, token=None, files=None):
    """
    Call our own DRF API.
    """
    base_url = getattr(settings, 'API_BASE_URL', 'http://127.0.0.1:8000')
    url = f"{base_url}{endpoint}"

    headers = {}
    if token:
        headers['Authorization'] = f'Token {token}'

    if method == 'GET':
        response = requests.get(url, headers=headers)
    elif method == 'POST':
        if files:
            # FIX: Sanitize booleans before sending as multipart form data
            sanitized_data = _sanitize_multipart_data(data)
            response = requests.post(url, data=sanitized_data, files=files, headers=headers)
        else:
            response = requests.post(url, json=data, headers=headers)
    elif method == 'PATCH':
        if files:
            # FIX: Sanitize booleans before sending as multipart form data
            sanitized_data = _sanitize_multipart_data(data)
            response = requests.patch(url, data=sanitized_data, files=files, headers=headers)
        else:
            response = requests.patch(url, json=data, headers=headers)
    elif method == 'DELETE':
        response = requests.delete(url, headers=headers)
    else:
        raise ValueError(f"Unsupported method: {method}")

    return response

def fetch_all_api_data(endpoint, token):
    """
    Fetches all pages from a paginated DRF API endpoint.
    """
    results = []
    page = 1
    
    # Ensure endpoint has query param separator
    separator = '&' if '?' in endpoint else '?'
    base_url = f"{getattr(settings, 'API_BASE_URL', 'http://127.0.0.1:8000')}{endpoint}"
    
    while True:
        headers = {}
        if token:
            headers['Authorization'] = f'Token {token}'
            
        url = f"{base_url}{separator}page={page}"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            # Handle paginated responses
            if isinstance(data, dict) and 'results' in data:
                results.extend(data.get('results', []))
                if data.get('next'):
                    page += 1
                else:
                    break # No more pages
            # Handle custom actions that return flat lists
            elif isinstance(data, list):
                results.extend(data)
                break 
        else:
            break # Stop on error
            
    return results# medicines/web/api_helper.py
import requests
from django.conf import settings

def _sanitize_multipart_data(data):
    """
    DRF strictly expects lowercase string booleans ('true'/'false') in multipart/form-data.
    The Python requests library converts Python bools to the string 'True'/'False', which DRF rejects.
    This helper sanitizes the payload to ensure compatibility.
    """
    if not data:
        return data
    
    sanitized = {}
    for key, value in data.items():
        if isinstance(value, bool):
            sanitized[key] = 'true' if value else 'false'
        else:
            sanitized[key] = value
    return sanitized

def api_call(method, endpoint, data=None, token=None, files=None):
    """
    Call our own DRF API.
    """
    base_url = getattr(settings, 'API_BASE_URL', 'http://127.0.0.1:8000')
    url = f"{base_url}{endpoint}"

    headers = {}
    if token:
        headers['Authorization'] = f'Token {token}'

    if method == 'GET':
        response = requests.get(url, headers=headers)
    elif method == 'POST':
        if files:
            # FIX: Sanitize booleans before sending as multipart form data
            sanitized_data = _sanitize_multipart_data(data)
            response = requests.post(url, data=sanitized_data, files=files, headers=headers)
        else:
            response = requests.post(url, json=data, headers=headers)
    elif method == 'PATCH':
        if files:
            # FIX: Sanitize booleans before sending as multipart form data
            sanitized_data = _sanitize_multipart_data(data)
            response = requests.patch(url, data=sanitized_data, files=files, headers=headers)
        else:
            response = requests.patch(url, json=data, headers=headers)
    elif method == 'DELETE':
        response = requests.delete(url, headers=headers)
    else:
        raise ValueError(f"Unsupported method: {method}")

    return response

def fetch_all_api_data(endpoint, token):
    """
    Fetches all pages from a paginated DRF API endpoint.
    """
    results = []
    page = 1
    
    # Ensure endpoint has query param separator
    separator = '&' if '?' in endpoint else '?'
    base_url = f"{getattr(settings, 'API_BASE_URL', 'http://127.0.0.1:8000')}{endpoint}"
    
    while True:
        headers = {}
        if token:
            headers['Authorization'] = f'Token {token}'
            
        url = f"{base_url}{separator}page={page}"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            # Handle paginated responses
            if isinstance(data, dict) and 'results' in data:
                results.extend(data.get('results', []))
                if data.get('next'):
                    page += 1
                else:
                    break # No more pages
            # Handle custom actions that return flat lists
            elif isinstance(data, list):
                results.extend(data)
                break 
        else:
            break # Stop on error
            
    return results