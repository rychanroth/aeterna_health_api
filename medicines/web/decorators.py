from django.shortcuts import redirect


def login_required_template(view_func):
    """
    Check if user has a token in session.
    If not, redirect to login page.
    """
    def wrapper(request, *args, **kwargs):
        if 'token' not in request.session:
            return redirect('template_login')
        return view_func(request, *args, **kwargs)
    return wrapper