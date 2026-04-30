from django.shortcuts import render
from .models import *
from .serializers import *
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

# Create your views here.
@api_view(['GET', 'POST'])
def medicine_list(request):
    """Get or create data."""
    if request.method == 'GET':
        medicines = Medicine.objects.all().order_by('created_at')
        serializer = MedicineSerializer(medicines, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = MedicineSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    


@api_view(['GET'])
def medicine_detail(request, pk):
    medicine = Medicine.objects.get(pk=pk)
    serializer = MedicineSerializer(medicine)
    return Response(serializer.data)