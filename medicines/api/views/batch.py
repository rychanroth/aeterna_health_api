# medicines/api/views/batch.py
from rest_framework import viewsets, filters
from medicines.core.models import Batch
from medicines.api.serializers import BatchSerializer
from medicines.api.permissions import IsAdmin, IsPharmacist
from rest_framework.permissions import IsAuthenticated
from medicines.api.filters import BatchFilter

class BatchViewSet(viewsets.ModelViewSet):
    queryset = Batch.objects.select_related('product', 'supplier').all()
    serializer_class = BatchSerializer
    search_fields = ['batch_number', 'product__name', 'supplier__name']
    filterset_class = BatchFilter
    ordering_fields = ['expiration_date', 'quantity', 'received_date', 'created_at']
    ordering = ['expiration_date']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAdmin | IsPharmacist]
        return [permission() for permission in permission_classes]