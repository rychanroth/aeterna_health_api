from .models import *
from .serializers import *
from rest_framework import viewsets

# ModelViewSet automatically provides list(), create(), retrieve(), update(), partial_update(), destroy()
# With the exception of using Router of course
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer

class MedicineViewSet(viewsets.ModelViewSet):
    queryset = Medicine.objects.all()
    serializer_class = MedicineSerializer