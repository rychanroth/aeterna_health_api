# medicines/web/decorators.py
from django.shortcuts import redirect
from functools import wraps

def login_required_template(view_func):
    """
    Check if user has a token in session.
    If not, redirect to login page.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if 'token' not in request.session:
            return redirect('template-login')
        return view_func(request, *args, **kwargs)
    return wrapper

def role_required(allowed_roles):
    """
    Decorator to restrict views based on user roles.
    Usage: @role_required(['admin', 'pharmacist'])
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if 'token' not in request.session:
                return redirect('template-login')
            
            user_role = request.session.get('role')
            if user_role not in allowed_roles:
                # Redirect to home if they don't have permission
                # Alternatively, render a 403.html template
                return redirect('home')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def admin_required(view_func):
    """Admin Only (Users, Suppliers, Reports)"""
    return role_required(['admin'])(view_func)

def pharmacy_staff_required(view_func):
    """Admin or Pharmacist (Inventory, Clinical)"""
    return role_required(['admin', 'pharmacist'])(view_func)

def pos_staff_required(view_func):
    """Admin or Cashier (POS, Dispensing)"""
    return role_required(['admin', 'cashier'])(view_func)