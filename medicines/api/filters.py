# medicines/api/filters.py
import django_filters
from django.db.models import Q
from django.utils import timezone
from medicines.core.models import *

class ProductFilter(django_filters.FilterSet):
    # Method filters for annotated/computed fields
    low_stock = django_filters.BooleanFilter(method='filter_low_stock', label='Low Stock')
    expired = django_filters.BooleanFilter(method='filter_expired', label='Is Expired')

    class Meta:
        model = Product
        fields = {
            'category': ['exact'],
            'product_type': ['exact'],
            'is_active': ['exact'],
            'requires_prescription': ['exact'],
        }

    def filter_low_stock(self, queryset, name, value):
        # total_stock is annotated in the ViewSet, so we can filter it at the DB level
        if value:
            return queryset.filter(total_stock__lt=10)
        return queryset

    def filter_expired(self, queryset, name, value):
        # nearest_expiration is annotated in the ViewSet
        today = timezone.now().date()
        if value:
            return queryset.filter(nearest_expiration__lt=today)
        return queryset.filter(nearest_expiration__gte=today)


class BatchFilter(django_filters.FilterSet):
    is_expired = django_filters.BooleanFilter(method='filter_is_expired', label='Is Expired')

    class Meta:
        model = Batch
        fields = {
            'product': ['exact'],
            'supplier': ['exact'],
            'is_active': ['exact'],
        }

    def filter_is_expired(self, queryset, name, value):
        today = timezone.now().date()
        if value:
            return queryset.filter(expiration_date__lt=today)
        return queryset.filter(expiration_date__gte=today)


class CategoryFilter(django_filters.FilterSet):
    class Meta:
        model = Category
        fields = {
            'product_type': ['exact'],
            'parent': ['exact', 'isnull'],
            'is_active': ['exact'],
        }


class ProductTypeFilter(django_filters.FilterSet):
    class Meta:
        model = ProductType
        fields = {
            'requires_expiration': ['exact'],
            'requires_prescription': ['exact'],
            'is_active': ['exact'],
        }

class UserFilter(django_filters.FilterSet):
    class Meta:
        model = User
        fields = {
            'role': ['exact'],
            'is_active': ['exact'],
        }

class SupplierFilter(django_filters.FilterSet):
    class Meta:
        model = Supplier
        fields = {
            'is_active': ['exact'],
        }

class DoctorFilter(django_filters.FilterSet):
    class Meta:
        model = Doctor
        fields = {
            'is_active': ['exact'],
        }

class PatientFilter(django_filters.FilterSet):
    # Method filter to replace the old custom action
    with_allergies = django_filters.BooleanFilter(method='filter_with_allergies', label='Has Allergies')

    class Meta:
        model = Patient
        fields = {
            'is_active': ['exact'],
            'gender': ['exact'],
        }

    def filter_with_allergies(self, queryset, name, value):
        if value:
            # Exclude null/empty allergy notes
            return queryset.exclude(Q(allergy_notes__isnull=True) | Q(allergy_notes=''))
        return queryset
    
class PrescriptionFilter(django_filters.FilterSet):
    # Filtering by prescription_date instead of created_at
    start_date = django_filters.DateFilter(field_name='prescription_date', lookup_expr='gte')
    end_date = django_filters.DateFilter(field_name='prescription_date', lookup_expr='lte')

    class Meta:
        model = Prescription
        fields = {
            'status': ['exact'],
            'patient': ['exact'],
            'doctor': ['exact'],
        }
    
class SaleFilter(django_filters.FilterSet):
    start_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    end_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')

    class Meta:
        model = Sale
        fields = {
            'cashier': ['exact'],
            'prescription': ['exact'],
            'payment_method': ['exact'],
        }


class StockMovementFilter(django_filters.FilterSet):
    # Map the 'product' query param to the 'batch__product' DB field
    product = django_filters.NumberFilter(field_name='batch__product')
    direction = django_filters.CharFilter(method='filter_direction', label='Direction (in/out)')
    start_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    end_date = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')
    # NEW: Filter movements by the status of their associated batch
    batch_is_active = django_filters.BooleanFilter(field_name='batch__is_active', label='Batch is Active')


    class Meta:
        model = StockMovement
        fields = {
            'batch': ['exact'],
            'movement_type': ['exact'],
            'supplier': ['exact'],
            'sale': ['exact'],
        }

    def filter_direction(self, queryset, name, value):
        if value == 'in':
            in_reasons = [r.value for r in StockMovement.Reason.get_in_reasons()]
            return queryset.filter(movement_type__in=in_reasons)
        elif value == 'out':
            out_reasons = [r.value for r in StockMovement.Reason.get_out_reasons()]
            return queryset.filter(movement_type__in=out_reasons)
        return queryset