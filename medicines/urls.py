from . import views
from django.urls import path

urlpatterns = [
    path('medicines/', views.medicine_list, name='medicine-list'),
    path('medicines/<int:pk>/', views.medicine_detail, name='medicine-detail')
]