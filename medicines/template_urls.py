from django.urls import path
from .template_views import *

urlpatterns = [
    path('', home, name='home')
]