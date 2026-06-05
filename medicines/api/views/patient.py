# medicines/api/views/patient.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from medicines.core.models import Patient
from medicines.api.serializers import PatientSerializer
from medicines.api.permissions import IsAdmin, IsPharmacist
from medicines.api.filters import PatientFilter

class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
    search_fields = ['name', 'phone', 'address'] # Formalized from manual Q objects
    filterset_class = PatientFilter

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin | IsPharmacist]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    # NOTE: The `with_allergies` custom action is no longer needed 
    # because it's now a filter: GET /api/patients/?with_allergies=true