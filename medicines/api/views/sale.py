from rest_framework import viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Sum, Count
from medicines.core.models import *
from medicines.api.serializers import SaleSerializer
from medicines.api.permissions import IsAdmin, IsCashier
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework.decorators import action
from rest_framework import status
from django.db import transaction
from django.core.exceptions import ValidationError

class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer
    search_fields = ['sale_number', 'notes']

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAdmin | IsCashier]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = Sale.objects.all()
        if self.request.user.role == 'cashier':
            queryset = queryset.filter(cashier=self.request.user)
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        cashier_id = self.request.query_params.get('cashier')
        if cashier_id:
            queryset = queryset.filter(cashier_id=cashier_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(cashier=self.request.user)

    @action(detail=False, methods=['get'])
    def today(self, request):
        today = timezone.now().date()
        sales = self.queryset.filter(created_at__date=today)
        serializer = self.get_serializer(sales, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_sales(self, request):
        sales = self.queryset.filter(cashier=request.user)
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
        Atomic POS checkout endpoint.
        Payload: { "items": [{"product_id": 1, "quantity": 2}], "payment_method": "cash", "prescription_id": null }
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
                sale_items_payload = []
                for item_data in items_data:
                    product_id = item_data.get('product_id')
                    quantity = int(item_data.get('quantity', 0))

                    if quantity <= 0:
                        raise ValidationError(f"Invalid quantity for product ID {product_id}")

                    # Lock the product row for atomic stock check & deduction
                    product = Product.objects.select_for_update().get(pk=product_id)

                    if product.stock_quantity < quantity:
                        raise ValidationError(f"Insufficient stock for {product.name}. Available: {product.stock_quantity}")

                    if product.effective_requires_prescription and not prescription:
                        raise ValidationError(f"Product {product.name} requires a prescription.")

                    # Server-side price calculation (never trust client)
                    unit_price = product.selling_price
                    subtotal = unit_price * quantity

                    sale_item = SaleItem.objects.create(
                        sale=sale,
                        product=product,
                        quantity=quantity,
                        unit_price=unit_price,
                        subtotal=subtotal
                    )
                    # SaleItem.save() automatically creates the StockMovement and updates product stock

                # 4. Update Prescription Status if applicable
                if prescription:
                    prescription.status = Prescription.Status.DISPENSED
                    prescription.save(update_fields=['status'])

                # 5. Serialize and return the successful sale
                serializer = self.get_serializer(sale)
                return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Product.DoesNotExist:
            return Response({"error": "One or more products not found."}, status=status.HTTP_404_NOT_FOUND)
        except Prescription.DoesNotExist:
            return Response({"error": "Prescription not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as e:
            return Response({"error": str(e.message_dict if hasattr(e, 'message_dict') else e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": "An unexpected error occurred during checkout."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)