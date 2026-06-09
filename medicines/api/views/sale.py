from rest_framework import viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import *
from medicines.api.serializers import SaleSerializer
from medicines.api.permissions import IsAdmin, IsCashier
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework.decorators import action
from rest_framework import status
from django.db import transaction
from django.core.exceptions import ValidationError
import datetime
from medicines.core.models import Sale, Prescription, Product, SaleItem, Batch
from medicines.api.filters import SaleFilter

class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer
    search_fields = ['sale_number', 'notes']
    filterset_class = SaleFilter

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticated]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        # We only override get_queryset for authorization scoping now
        queryset = super().get_queryset()
        if self.request.user.role == 'cashier':
            queryset = queryset.filter(cashier=self.request.user)
        return queryset

    def perform_create(self, serializer):
        serializer.save(cashier=self.request.user)

    @action(detail=False, methods=['get'])
    def today(self, request):
        today = timezone.now().date()
        sales = self.get_queryset().filter(created_at__date=today)
        serializer = self.get_serializer(sales, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def my_sales(self, request):
        sales = self.get_queryset().filter(cashier=request.user)
        serializer = self.get_serializer(sales, many=True)
        return Response(serializer.data)

    @extend_schema(
        responses=inline_serializer(name='SaleReportResponse', fields={'today': serializers.DictField(), 'this_month': serializers.DictField()})
    )
    @action(detail=False, methods=['get'])
    def report(self, request):
        today = timezone.now().date()
        today_sales = Sale.objects.filter(created_at__date=today)
        today_total = today_sales.aggregate(total=Sum('total_amount'), count=Count('id'))
        month_start = today.replace(day=1)
        month_sales = Sale.objects.filter(created_at__date__gte=month_start)
        month_total = month_sales.aggregate(total=Sum('total_amount'), count=Count('id'))
        return Response({
            'today': {'total_sales': today_total['total'] or 0, 'transaction_count': today_total['count'] or 0},
            'this_month': {'total_sales': month_total['total'] or 0, 'transaction_count': month_total['count'] or 0}
        })
    
    @action(detail=False, methods=['post'], url_path='checkout', permission_classes=[IsAuthenticated])
    def checkout(self, request):
        """
        Atomic POS checkout endpoint with FEFO Batch allocation.
        Payload: { "items": [{"product_id": 1, "quantity": 2, "batch_id": null}], "payment_method": "cash", "prescription_id": null }
        """
        items_data = request.data.get('items', [])
        payment_method = request.data.get('payment_method', Sale.PaymentMethod.CASH)
        prescription_id = request.data.get('prescription_id')

        if not items_data:
            return Response({"error": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # 1. Lock the prescription row if provided (prevent double-dispense)
                prescription = None
                if prescription_id:
                    prescription = Prescription.objects.select_for_update().get(pk=prescription_id)
                    if prescription.status != Prescription.Status.VERIFIED:
                        raise ValidationError(f"Prescription must be verified. Current status: {prescription.status}")

                # 2. Create the Sale object
                sale = Sale.objects.create(
                    cashier=request.user,
                    payment_method=payment_method,
                    prescription=prescription
                )

                # 3. Process items: Validate stock, calculate prices, create movements
                for item_data in items_data:
                    product_id = item_data.get('product_id')
                    quantity = int(item_data.get('quantity', 0))
                    batch_id = item_data.get('batch_id') # Optional: Cashier can force a specific batch

                    if quantity <= 0:
                        raise ValidationError(f"Invalid quantity for product ID {product_id}")

                    # Fetch product for pricing and RX check
                    product = Product.objects.get(pk=product_id)

                    if product.effective_requires_prescription and not prescription:
                        raise ValidationError(f"Product {product.name} requires a prescription.")

                    remaining_qty = quantity
                    batches_to_sell = []

                    if batch_id:
                        # EXPLICIT BATCH SELECTION
                        batch = Batch.objects.select_for_update().get(pk=batch_id)
                        if batch.product_id != product.id:
                            raise ValidationError(f"Batch {batch.batch_number} does not belong to product {product.name}.")
                        if batch.quantity < remaining_qty:
                            raise ValidationError(f"Insufficient stock in Batch {batch.batch_number}. Available: {batch.quantity}")
                        batches_to_sell.append((batch, remaining_qty))
                    else:
                        # FEFO AUTO-ALLOCATION
                        available_batches = Batch.objects.filter(
                            product=product, is_active=True, quantity__gt=0
                        ).order_by(F('expiration_date').asc(nulls_last=True)).select_for_update()

                        if not available_batches.exists():
                            raise ValidationError(f"No active stock available for {product.name}.")

                        for batch in available_batches:
                            if remaining_qty <= 0:
                                break
                            qty_to_take = min(remaining_qty, batch.quantity)
                            batches_to_sell.append((batch, qty_to_take))
                            remaining_qty -= qty_to_take

                        if remaining_qty > 0:
                            raise ValidationError(f"Insufficient stock for {product.name}. Short by {remaining_qty} units.")

                    # Create SaleItems (which auto-create StockMovements & update batch quantities)
                    for batch, qty in batches_to_sell:
                        SaleItem.objects.create(
                            sale=sale,
                            batch=batch,
                            quantity=qty,
                            unit_price=product.selling_price
                        )

                # 4. Update Prescription Status if applicable
                if prescription:
                    prescription.status = Prescription.Status.DISPENSED
                    prescription.save(update_fields=['status'])

                # 5. Serialize and return the successful sale
                serializer = self.get_serializer(sale)
                return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Product.DoesNotExist:
            return Response({"error": "One or more products not found."}, status=status.HTTP_404_NOT_FOUND)
        except Batch.DoesNotExist:
            return Response({"error": "Specified batch not found."}, status=status.HTTP_404_NOT_FOUND)
        except Prescription.DoesNotExist:
            return Response({"error": "Prescription not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as e:
            return Response({"error": str(e.message_dict if hasattr(e, 'message_dict') else e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": "An unexpected error occurred during checkout."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)