# medicines/api/views/doctor.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from medicines.core.models import Doctor
from medicines.api.serializers import DoctorSerializer
from medicines.api.permissions import IsAdmin, IsPharmacist
from medicines.api.filters import DoctorFilter

class DoctorViewSet(viewsets.ModelViewSet):
    queryset = Doctor.objects.all()
    serializer_class = DoctorSerializer
    search_fields = ['name', 'license_number', 'clinic_name'] # Formalized from manual Q objects
    filterset_class = DoctorFilter

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin | IsPharmacist]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]