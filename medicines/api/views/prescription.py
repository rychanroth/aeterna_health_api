from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from medicines.core.models import Prescription
from medicines.api.serializers import PrescriptionSerializer
from medicines.api.permissions import IsAdmin, IsPharmacist

class PrescriptionViewSet(viewsets.ModelViewSet):
    queryset = Prescription.objects.all()
    serializer_class = PrescriptionSerializer
    search_fields = ['prescription_number', 'doctor__name', 'patient__name', 'notes']

    def get_permissions(self):
        if self.action in ['verify', 'reject']:
            permission_classes = [IsAdmin | IsPharmacist]
        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin | IsPharmacist]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = Prescription.objects.all()
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
        patient_id = self.request.query_params.get('patient')
        if patient_id:
            queryset = queryset.filter(patient_id=patient_id)
        doctor_id = self.request.query_params.get('doctor')
        if doctor_id:
            queryset = queryset.filter(doctor_id=doctor_id)
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(prescription_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(prescription_date__lte=end_date)
        return queryset
    
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
        pending = self.get_queryset().filter(status=Prescription.Status.PENDING)
        serializer = self.get_serializer(pending, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def verified(self, request):
        verified = self.get_queryset().filter(status=Prescription.Status.VERIFIED)
        serializer = self.get_serializer(verified, many=True)
        return Response(serializer.data)