# medicines/api/views/prescription.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from medicines.core.models import Prescription
from medicines.api.serializers import PrescriptionSerializer
from medicines.api.permissions import IsAdmin, IsPharmacist
from medicines.api.filters import PrescriptionFilter

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