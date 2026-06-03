from django.shortcuts import render
from medicines.web.decorators import login_required_template

@login_required_template
def pos_screen(request):
    # The POS is a standalone SPA-like shell. Data is loaded via JS.
    return render(request, 'pos/pos.html')