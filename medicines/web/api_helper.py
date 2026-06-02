import requests
from django.conf import settings

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

    return response