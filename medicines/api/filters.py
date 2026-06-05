# medicines/api/filters.py
import django_filters
from django.utils import timezone
from medicines.core.models import Product, Batch, Category, ProductType

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