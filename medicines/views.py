from django.shortcuts import render
from .models import *
from .serializers import *
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

# Create your views here.
@api_view(['GET'])
def medicine_list(request):
    """List all medicines."""
    medicines = Medicine.objects.all().order_by('created_at')
    serializer = MedicineSerializer(medicines, many=True)
    return  Response(serializer.data)

@api_view(['GET'])
def medicine_detail(request, pk):
    medicine = Medicine.objects.get(pk=pk)
    serializer = MedicineSerializer(medicine)
    return Response(serializer.data)