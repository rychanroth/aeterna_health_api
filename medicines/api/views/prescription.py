# medicines/api/views/prescription.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from medicines.core.models import Prescription, Batch, Sale, SaleItem
from medicines.api.serializers import PrescriptionSerializer
from medicines.api.permissions import IsAdmin, IsPharmacist
from medicines.api.filters import PrescriptionFilter
from django.db.models import F
from django.db import transaction
from django.core.exceptions import ValidationError


class PrescriptionViewSet(viewsets.ModelViewSet):
    queryset = Prescription.objects.all()
    serializer_class = PrescriptionSerializer
    search_fields = ['prescription_number', 'doctor__name', 'patient__name', 'notes']
    filterset_class = PrescriptionFilter

    def get_permissions(self):
        if self.action in ['verify', 'reject']:
            permission_classes = [IsAdmin | IsPharmacist]
        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin | IsPharmacist]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        prescription = self.get_object()
        if prescription.status != Prescription.Status.PENDING:
            return Response({'error': 'Only pending prescriptions can be verified'}, status=400)
        prescription.status = Prescription.Status.VERIFIED
        prescription.verified_by = request.user
        prescription.save()
        serializer = self.get_serializer(prescription)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        prescription = self.get_object()
        if prescription.status != Prescription.Status.PENDING:
            return Response({'error': 'Only pending prescriptions can be rejected'}, status=400)
        prescription.status = Prescription.Status.REJECTED
        prescription.verified_by = request.user
        prescription.save()
        serializer = self.get_serializer(prescription)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def dispense(self, request, pk=None):
        """
        Atomic FEFO dispensing endpoint.
        Payload: { "payment_method": "cash" }
        """
        prescription = self.get_object()

        if prescription.status != Prescription.Status.VERIFIED:
            return Response(
                {'error': f'Prescription must be verified before dispensing. Current status: {prescription.status}'},
                status=400
            )

        payment_method = request.data.get('payment_method', Sale.PaymentMethod.CASH)

        try:
            with transaction.atomic():
                # 1. Lock the prescription to prevent double-dispense
                prescription = Prescription.objects.select_for_update().get(pk=prescription.pk)

                # 2. Create the Sale header
                sale = Sale.objects.create(
                    cashier=request.user,
                    payment_method=payment_method,
                    prescription=prescription,
                    notes=f"Auto-created from Prescription #{prescription.prescription_number}"
                )

                # 3. Process each Prescription Item using FEFO
                for item in prescription.items.select_related('product').all():
                    if item.is_dispensed:
                        continue # Skip already dispensed items if any

                    remaining_qty = item.quantity_prescribed
                    
                    # Find active batches with stock, sorted by expiration date (FEFO)
                    # nulls_last=True ensures batches without dates don't take priority
                    available_batches = Batch.objects.filter(
                        product=item.product, 
                        is_active=True, 
                        quantity__gt=0
                    ).order_by(F('expiration_date').asc(nulls_last=True))

                    if not available_batches.exists():
                        raise DjangoValidationError(f"No active stock available for {item.product.name}")

                    for batch in available_batches:
                        if remaining_qty <= 0:
                            break

                        qty_to_dispense = min(remaining_qty, batch.quantity)
                        
                        # Create SaleItem (which automatically creates StockMovement & updates batch quantity)
                        SaleItem.objects.create(
                            sale=sale,
                            batch=batch,
                            quantity=qty_to_dispense,
                            unit_price=item.product.selling_price
                        )

                        # Assign the first batch used to the PrescriptionItem for traceability
                        if not item.batch_id:
                            item.batch = batch
                        
                        remaining_qty -= qty_to_dispense

                    if remaining_qty > 0:
                        # If we exit the loop and still need stock, we don't have enough
                        raise DjangoValidationError(
                            f"Insufficient stock for {item.product.name}. Short by {remaining_qty} units."
                        )

                    item.is_dispensed = True
                    item.save()

                # 4. Update Prescription Status
                prescription.status = Prescription.Status.DISPENSED
                prescription.save()

                serializer = self.get_serializer(prescription)
                return Response(serializer.data, status=200)

        except DjangoValidationError as e:
            return Response({'error': e.message}, status=400)
        except Exception as e:
            return Response({'error': 'An unexpected error occurred during dispensing.'}, status=500)

    @action(detail=False, methods=['get'])
    def pending(self, request):
        # We can now simply use the filterset!
        # GET /api/prescriptions/?status=pending
        return Response(self.get_serializer(self.get_queryset(), many=True).data)
    
    # NOTE: The `verified` custom action is now redundant since you can do 
    # GET /api/prescriptions/?status=verified, but I'll leave it for backward compatibility
    @action(detail=False, methods=['get'])
    def verified(self, request):
        return Response(self.get_serializer(self.get_queryset(), many=True).data)