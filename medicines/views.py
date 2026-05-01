from .models import *
from .serializers import *
from rest_framework import viewsets

# ModelViewSet automatically provides list(), create(), retrieve(), update(), partial_update(), destroy()
# When registered with Router, it dynamically generates the URL PATTERNS!
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer

class MedicineViewSet(viewsets.ModelViewSet):
    queryset = Medicine.objects.all()
    serializer_class = MedicineSerializer