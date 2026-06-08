import requests
from django.conf import settings
import re
from django.utils.dateparse import parse_date, parse_datetime

# Regex patterns to safely match ISO dates without false positives
ISO_DATETIME_RE = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$')
ISO_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

def parse_iso_strings(data):
    """
    Recursively walks through dicts and lists, automatically converting 
    ISO-8601 date/datetime strings into Python date/datetime objects.
    """
    if isinstance(data, dict):
        return {k: parse_iso_strings(v) for k, v in data.items()}
    
    elif isinstance(data, list):
        return [parse_iso_strings(item) for item in data]
    
    elif isinstance(data, str):
        # Check for full datetimes first
        if ISO_DATETIME_RE.match(data):
            dt = parse_datetime(data)
            if dt is not None:
                return dt
        # Check for standalone dates (e.g., expiration_date)
        elif ISO_DATE_RE.match(data):
            d = parse_date(data)
            if d is not None:
                return d
                
    return data

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
            response = requests.post(url, data=data, files=files, headers=headers)
        else:
            response = requests.post(url, json=data, headers=headers)
    elif method == 'PATCH':
        if files:
            response = requests.patch(url, data=data, files=files, headers=headers)
        else:
            response = requests.patch(url, json=data, headers=headers)
    elif method == 'DELETE':
        response = requests.delete(url, headers=headers)
    else:
        raise ValueError(f"Unsupported method: {method}")

    # MONKEY-PATCH THE RESPONSE: Inject our parser transparently into .json()
    if response.status_code in [200, 201]:
        original_json_method = response.json
        
        def auto_parsing_json(*args, **kwargs):
            raw_payload = original_json_method(*args, **kwargs)
            return parse_iso_strings(raw_payload)
            
        response.json = auto_parsing_json

    return response

def fetch_all_api_data(endpoint, token):
    """
    Fetches all pages from a paginated DRF API endpoint.
    """
    results = []
    page = 1
    
    # Ensure endpoint has query param separator
    separator = '&' if '?' in endpoint else '?'
    page_endpoint = f"{endpoint}{separator}page={page}"
    
    while True:
        # Construct the page-specific endpoint path
        page_endpoint = f"{endpoint}{separator}page={page}"
        
        # Route through api_call to take advantage of centralized headers and auto-parsing
        response = api_call('GET', page_endpoint, token=token)
        
        if response.status_code == 200:
            data = response.json()
        
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