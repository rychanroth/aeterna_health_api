from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from medicines.core.models import Supplier
from medicines.api.serializers import SupplierSerializer
from medicines.api.permissions import IsAdmin

class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    search_fields = ['name']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]