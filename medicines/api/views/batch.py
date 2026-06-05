from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, BooleanFilter
from django.utils import timezone
from medicines.core.models import Batch
from medicines.api.serializers import BatchSerializer
from medicines.api.permissions import IsAdmin, IsPharmacist
from rest_framework.permissions import IsAuthenticated

class BatchFilter(FilterSet):
    is_expired = BooleanFilter(method='filter_is_expired', label='Is Expired')

    class Meta:
        model = Batch
        fields = ['product', 'supplier', 'is_active']

    def filter_is_expired(self, queryset, name, value):
        today = timezone.now().date()
        if value:
            return queryset.filter(expiration_date__lt=today)
        return queryset.filter(expiration_date__gte=today)

class BatchViewSet(viewsets.ModelViewSet):
    queryset = Batch.objects.select_related('product', 'supplier').all()
    serializer_class = BatchSerializer
    
    # Search & Filter Configuration
    search_fields = ['batch_number', 'product__name', 'supplier__name']
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = BatchFilter
    ordering_fields = ['expiration_date', 'quantity', 'received_date', 'created_at']
    ordering = ['expiration_date'] # Default FEFO ordering

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAdmin | IsPharmacist]
        return [permission() for permission in permission_classes]