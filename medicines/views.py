from .models import *
from .serializers import *
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

# ModelViewSet automatically provides list(), create(), retrieve(), update(), partial_update(), destroy()
# When registered with Router, it dynamically generates the URL PATTERNS!
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    # === Custom Action ===
    # Function name determines the auto-generated url name e.g. /api/categories/roots/
    @action(detail=False, methods=['get'])
    def roots(self, request):
        """Get all root categories (category with no parent)"""
        root_categories = self.queryset.filter(parent__isnull=True)
        serializer = self.get_serializer(root_categories, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def medicines(self, request, pk=None):
        """Get all medicines in this category"""
        category = self.get_object()
        medicines = category.medicines.all()
        serializer = MedicineSerializer(medicines, many=True)
        return Response(serializer.data)

class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer

class MedicineViewSet(viewsets.ModelViewSet):
    queryset = Medicine.objects.all()
    serializer_class = MedicineSerializer