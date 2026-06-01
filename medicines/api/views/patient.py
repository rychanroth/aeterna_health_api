from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from medicines.core.models import Patient
from medicines.api.serializers import PatientSerializer
from medicines.api.permissions import IsAdmin, IsPharmacist

class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin | IsPharmacist]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = Patient.objects.all()
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(phone__icontains=search))
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset
    
    @action(detail=False, methods=['get'])
    def with_allergies(self, request):
        patients = self.get_queryset().exclude(Q(allergy_notes__isnull=True) | Q(allergy_notes=''))
        serializer = self.get_serializer(patients, many=True)
        return Response(serializer.data)