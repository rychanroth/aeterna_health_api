import requests
from django.conf import settings


def api_call(method, endpoint, data=None, token=None):
    """
    Call our own DRF API.
    
    method: 'GET', 'POST', 'PATCH', 'DELETE'
    endpoint: '/api/categories/' (relative to base URL)
    data: dict of data to send (for POST/PATCH)
    token: auth token string (if user is logged in)
    """
    base_url = f"http://127.0.0.1:8000{endpoint}"
    
    headers = {}
    if token:
        headers['Authorization'] = f'Token {token}'
    
    if method == 'GET':
        response = requests.get(base_url, headers=headers)
    elif method == 'POST':
        response = requests.post(base_url, json=data, headers=headers)
    elif method == 'PATCH':
        response = requests.patch(base_url, json=data, headers=headers)
    elif method == 'DELETE':
        response = requests.delete(base_url, headers=headers)
    
    return response