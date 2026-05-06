from datetime import timedelta
from django.utils import timezone
from .models import *
from .serializers import *
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.permissions import *
from django.contrib.auth import authenticate
from django.db import models

# === AUTHENTICATION ===

@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def login(request):
    """Exchage username/password for auth token"""
    username = request.data.get('username')
    password = request.data.get('password')

    user =  authenticate(username=username, password=password)

    if user:
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.id,
            'username': user.username
        })
    return Response({'error': 'Invalid Credentials'}, status=status.HTTP_401_UNAUTHORIZED)

# User ViewSet

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser] # only Admin can manage users

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current logged-in user info"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


# ModelViewSet automatically provides list(), create(), retrieve(), update(), partial_update(), destroy()
# When registered with Router, it dynamically generates the URL PATTERNS!
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    # === Custom Permissions ===
    def get_permissions(self):
        """Anyone can view, but only authenticated user can add/update/delete"""
        if self.action in ['list', 'retrieve', 'roots', 'medicines']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]

    # === Custom Action ===
    # Function name determines the auto-generated url name e.g. /api/categories/roots/
    @action(detail=False, methods=['get'])
    def roots(self, request):
        """Get all root categories (category with no parent)"""
        root_categories = self.queryset.filter(parent__isnull=True)
        serializer = self.get_serializer(root_categories, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def medicines(self, request, pk=None):
        """Get all medicines in this category"""
        category = self.get_object()
        medicines = category.medicines.filter(is_active=True)
        serializer = MedicineSerializer(medicines, many=True)
        return Response(serializer.data)

class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated]

    # Custom Permission
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    # Custom Action
    @action(detail=True, methods=['get'])
    def medicines(self, request, pk=None):
        """Get all medicines from this supplier"""
        supplier = self.get_object()
        medicines = supplier.medicines.filter(is_active=True)
        serializer = MedicineSerializer(medicines, many=True)
        return Response(serializer.data)


class MedicineViewSet(viewsets.ModelViewSet):
    queryset = Medicine.objects.all()
    serializer_class = MedicineSerializer
    permission_classes = [IsAuthenticated]

    # === Custom Permissions ===
    def get_permissions(self):
        # Admin can do all these
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    # Custom Queryset
    def get_queryset(self):
        queryset = Medicine.objects.all()

        """Filter medicines by search query"""
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)

        """Filter medicines by category"""
        category_id = self.request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        """Filter medicines by expiration"""
        expired = self.request.query_params.get('expired')
        if expired == 'true':
            queryset = queryset.filter(expiration_date__lt=timezone.now().date())
        elif expired == 'false':
            queryset = queryset.filter(expiration_date__gte=timezone.now().date())

        """Filter medicines by low stock"""
        low_stock = self.request.query_params.get('low_stock')
        if low_stock == 'true':
            queryset = queryset.filter(stock_quantity__lt=10) 

        return queryset
    
    # Custom Logic
    def perform_create(self, serializer):
        medicine = serializer.save()

    # Custom Action
    @action(detail=False, methods=['get'])
    def expired(self, request):
        """Get all expired medicines"""
        expired = self.queryset.filter(
            expiration_date__lt=timezone.now().date(),
            is_active=True
        )
        serializer = self.get_serializer(expired, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Get all medicines with low stock"""
        low_stock = self.queryset.filter(
            stock_quantity__lt=10,
            is_active=True
        )
        serializer = self.get_serializer(low_stock, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """Get medicines expiring in the next 30 days"""
        soon = timezone.now().date() + timedelta(days=30)
        expiring = self.queryset.filter(
            expiration_date__lte=soon,
            expiration_date__gte=timezone.now().date(),
            is_active=True
        )
        serializer = self.get_serializer(expiring, many=True)
        return Response(serializer.data)
    
class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated]
    
    # Custom Queryset
    def get_queryset(self):
        queryset = Sale.objects.all()

        """Filter sales by date range"""
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)

        """Filter sales by cashier"""
        cashier_id = self.request.query_params.get('cashier')
        if cashier_id:
            queryset = queryset.filter(cashier_id=cashier_id)

        return queryset
    
    # Custom Logic
    def perform_create(self, serializer):
        serializer.save(cashier=self.request.user)

    # Custom Actions
    @action(detail=False, methods=['get'])
    def today(self, request):
        """Get today's sales"""
        today = timezone.now().date()
        sales = self.queryset.filter(created_at__date=today)
        serializer = self.get_serializer(sales, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_sales(self, request):
        """Get current cashier's sales"""
        sales = self.queryset.filter(cashier=request.user)
        serializer = self.get_serializer(sales, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def report(self, request):
        """Get sales summary report"""
        from django.db.models import Sum, Count

        today = timezone.now().date()

        # Today's statistic
        today_sales = Sale.objects.filter(created_at__date=today)
        today_total = today_sales.aggregate(
            total=Sum('total_price'),
            count=Count('id')
        )

        # This month's statistic
        month_start = today.replace(day=1)
        month_sales = Sale.objects.filter(created_at__date__gte=month_start)
        month_total = month_sales.aggregate(
            total=Sum('total_price'),
            count=Count('id')
        )

        return Response({
            'today': {
                'total_sales': today_total['total'] or 0,
                'transaction_count': today_total['count'] or 0
            },
            'this_month': {
                'total_sales': month_total['total'] or 0,
                'transaction_count': month_total['count'] or 0
            }
        })

class DoctorViewSet(viewsets.ModelViewSet):
    queryset = Doctor.objects.all()
    serializer_class = DoctorSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Doctor.objects.all()

        # Search by name or license
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search) |
                models.Q(license_number__icontains=search)
            )

        # Filter
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset
    
    def get_permissions(self):
        """Only admin and pharmacist can manage doctors"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Patient.objects.all()

        # Search by name or phone 
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search) |
                models.Q(phone__icontains=search)
            )

        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset
    
    @action(detail=False, methods=['get'])
    def with_allergies(self, request):
        """Get patients who have allegy notes"""
        patients = self.get_queryset().exclude(allergy_notes='')
        serializer = self.get_serializer(patients, many=True)
        return Response(serializer.data)

class PrescriptionViewSet(viewsets.ModelViewSet):
    queryset = Prescription.objects.all()
    serializer_class = PrescriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Prescription.objects.all()

        # Filter by status
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # Filter by patient
        patient_id = self.request.query_params.get('patient')
        if patient_id:
            queryset = queryset.filter(patient_id=patient_id)
        
        # Filter by doctor
        doctor_id = self.request.query_params.get('doctor')
        if doctor_id:
            queryset = queryset.filter(doctor_id=doctor_id)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(prescription_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(prescription_date__lte=end_date)

        return queryset
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Verify a prescription (pharmacist only)"""
        prescription = self.get_object()
        
        if prescription.status != Prescription.Status.PENDING:
            return Response(
                {'error': 'Only pending prescriptions can be verified'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        prescription.status = Prescription.Status.VERIFIED
        prescription.verified_by = request.user
        prescription.save()
        
        serializer = self.get_serializer(prescription)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a prescription (pharmacist only)"""
        prescription = self.get_object()
        
        if prescription.status != Prescription.Status.PENDING:
            return Response(
                {'error': 'Only pending prescriptions can be rejected'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        prescription.status = Prescription.Status.REJECTED
        prescription.verified_by = request.user
        prescription.save()
        
        serializer = self.get_serializer(prescription)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get all pending prescriptions"""
        pending = self.get_queryset().filter(status=Prescription.Status.PENDING)
        serializer = self.get_serializer(pending, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def verified(self, request):
        """Get all verified prescriptions"""
        verified = self.get_queryset().filter(status=Prescription.Status.VERIFIED)
        serializer = self.get_serializer(verified, many=True)
        return Response(serializer.data)
    

# StockMovements
class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = StockMovement.objects.all()
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = StockMovement.objects.all()
        
        # Filter by medicine
        medicine_id = self.request.query_params.get('medicine')
        if medicine_id:
            queryset = queryset.filter(medicine_id=medicine_id)
        
        # Filter by movement type
        movement_type = self.request.query_params.get('movement_type')
        if movement_type:
            queryset = queryset.filter(movement_type=movement_type)
        
        # Filter by IN/OUT
        direction = self.request.query_params.get('direction')
        if direction == 'in':
            queryset = queryset.filter(
                movement_type__in=[
                    StockMovement.MovementType.PURCHASE,
                    StockMovement.MovementType.RETURN_CUSTOMER,
                    StockMovement.MovementType.ADJUSTMENT_IN
                ]
            )
        elif direction == 'out':
            queryset = queryset.filter(
                movement_type__in=[
                    StockMovement.MovementType.SALE,
                    StockMovement.MovementType.EXPIRED,
                    StockMovement.MovementType.DAMAGED,
                    StockMovement.MovementType.RETURN_SUPPLIER,
                    StockMovement.MovementType.ADJUSTMENT_OUT
                ]
            )
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        return queryset

    @action(detail=False, methods=['get'])
    def stock_in(self, request):
        """Get all stock IN movements"""
        movements = self.queryset.filter(
            movement_type__in=[
                StockMovement.MovementType.PURCHASE,
                StockMovement.MovementType.RETURN_CUSTOMER,
                StockMovement.MovementType.ADJUSTMENT_IN
            ]
        )
        serializer = self.get_serializer(movements, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stock_out(self, request):
        """Get all stock OUT movements"""
        movements = self.queryset.filter(
            movement_type__in=[
                StockMovement.MovementType.SALE,
                StockMovement.MovementType.EXPIRED,
                StockMovement.MovementType.DAMAGED,
                StockMovement.MovementType.RETURN_SUPPLIER,
                StockMovement.MovementType.ADJUSTMENT_OUT
            ]
        )
        serializer = self.get_serializer(movements, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get stock movement summary"""
        from django.db.models import Sum
        
        medicine_id = request.query_params.get('medicine')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        queryset = StockMovement.objects.all()
        
        if medicine_id:
            queryset = queryset.filter(medicine_id=medicine_id)
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        # Calculate totals
        stock_in_types = [
            StockMovement.MovementType.PURCHASE,
            StockMovement.MovementType.RETURN_CUSTOMER,
            StockMovement.MovementType.ADJUSTMENT_IN
        ]
        stock_out_types = [
            StockMovement.MovementType.SALE,
            StockMovement.MovementType.EXPIRED,
            StockMovement.MovementType.DAMAGED,
            StockMovement.MovementType.RETURN_SUPPLIER,
            StockMovement.MovementType.ADJUSTMENT_OUT
        ]
        
        total_in = queryset.filter(
            movement_type__in=stock_in_types
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        total_out = queryset.filter(
            movement_type__in=stock_out_types
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        return Response({
            'total_in': total_in,
            'total_out': total_out,
            'net_change': total_in - total_out
        })