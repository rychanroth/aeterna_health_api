"""
Shared helpers for medicines test suite.
Reduces boilerplate without introducing heavy frameworks like Factory Boy.
"""
from decimal import Decimal
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from medicines.core.models import (
    ProductType, Category, Supplier, Product, Batch, StockMovement
)

User = get_user_model()


def create_authenticated_client(user):
    """Return APIClient with valid auth token for API tests."""
    from rest_framework.test import APIClient
    from rest_framework.authtoken.models import Token

    client = APIClient()
    token, _ = Token.objects.get_or_create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    return client


def create_product_with_stock(name, stock_quantity=100, created_by=None, **kwargs):
    """
    Create a fully valid product with initial stock via Batch and StockMovement.
    Mirrors proper business flow (no direct stock_quantity manipulation on Product).
    """
    # Defaults
    product_type_name = kwargs.get('product_type_name', 'Equipment')
    requires_expiration = kwargs.get('requires_expiration', False)
    requires_prescription = kwargs.get('requires_prescription', False)
    selling_price = kwargs.get('selling_price', Decimal('10.00'))
    cost_price = kwargs.get('cost_price', Decimal('6.00')) # Default cost

    # Get or create dependency chain
    product_type, _ = ProductType.objects.get_or_create(
        name=product_type_name,
        defaults={
            'requires_expiration': requires_expiration,
            'requires_prescription': requires_prescription
        }
    )

    category, _ = Category.objects.get_or_create(
        name=f"{product_type_name} Category",
        product_type=product_type
    )

    supplier, _ = Supplier.objects.get_or_create(
        name='Default Test Supplier',
        phone='000-000-0000'
    )

    # FIX: Create product WITHOUT stock_quantity or expiration_date
    product = Product.objects.create(
        name=name,
        product_type=product_type,
        category=category,
        base_unit='piece',
        selling_price=selling_price,
        requires_prescription=requires_prescription
    )
    product.suppliers.add(supplier)

    # FIX: Create a Batch to hold the stock and expiration
    batch = Batch.objects.create(
        product=product,
        quantity=0, # Start at 0, StockMovement will increment it
        cost_price=cost_price,
        supplier=supplier,
        expiration_date=kwargs.get('expiration_date', date.today() + timedelta(days=365)) if product_type.requires_expiration else None
    )

    # Add stock via proper business flow
    if stock_quantity > 0 and created_by:
        StockMovement.objects.create(
            batch=batch, # FIX: Target batch, not product
            movement_type=StockMovement.Reason.PURCHASE,
            quantity=stock_quantity,
            supplier=supplier,
            # REMOVED: unit_cost (Tracked at Batch level now)
            created_by=created_by
        )
        product.refresh_from_db()
        batch.refresh_from_db()

    return product