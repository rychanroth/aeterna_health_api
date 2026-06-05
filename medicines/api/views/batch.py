from rest_framework import viewsets
from medicines.core.models import Batch
from medicines.api.serializers import BatchSerializer
from medicines.api.permissions import IsAdmin, IsPharmacist
from rest_framework.permissions import *

class BatchViewSet(viewsets.ModelViewSet):
    queryset = Batch.objects.all()
    serializer_class = BatchSerializer
    search_fields = ['batch_number', 'product__name']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAdmin | IsPharmacist]
        return [permission() for permission in permission_classes]