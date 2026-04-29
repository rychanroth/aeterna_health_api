from . import views
from django.urls import path

urlpatterns = [
    path('medicines/', views.medicine_list, name='medicine-list')
]