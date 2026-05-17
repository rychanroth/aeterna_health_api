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
from django.db.models import Q
from .permissions import (
    IsAdmin, IsPharmacist, IsCashier,
    IsAdminOrPharmacist, IsAdminOrCashier
)
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiExample, OpenApiResponse

# === AUTHENTICATION ===

@extend_schema(
    tags=['Auth'],
    request=inline_serializer(
        name='LoginRequest',
        fields={
            'username': serializers.CharField(),
            'password': serializers.CharField(),
        }
    ),
    responses={
        200: inline_serializer(
            name='LoginResponse',
            fields={
                'token': serializers.CharField(),
                'user_id': serializers.IntegerField(),
                'username': serializers.CharField(),
            }
        ),
        401: OpenApiResponse(description='Invalid Credentials')
    },
    auth=None # Explicitly tell Swagger this has no security
)
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

    def get_permissions(self):
        if self.action == 'me':
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAdmin]  # Changed from IsAdminUser
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current logged-in user info"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


# ModelViewSet automatically provides list(), create(), retrieve(), update(), partial_update(), destroy()
# When registered with Router, it dynamically generates the URL PATTERNS!

class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin]  # Changed from IsAdminUser
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
class ProductTypeViewSet(viewsets.ModelViewSet):
    queryset = ProductType.objects.all()
    serializer_class = ProductTypeSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin]  # Changed from IsAdminUser
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=True, methods=['get'])
    def root_categories(self, request, pk):
        """Get all root categories of a producttype"""
        product_type = self.get_object()
        categories = product_type.categories.filter(parent=None, is_active=True)
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def categories(self, request, pk):
        """Get all categories of a producttype"""
        product_type = self.get_object()
        categories = product_type.categories.filter(is_active=True)
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)

    def get_queryset(self):
        """Filter products by type flag"""
        queryset = ProductType.objects.all()

        requires_expiration = self.request.query_params.get('requires_expiration')
        if requires_expiration is not None:
            queryset = queryset.filter(requires_expiration=requires_expiration.lower() == 'true')

        requires_prescription = self.request.query_params.get('requires_prescription')
        if requires_prescription is not None:
            queryset = queryset.filter(requires_prescription=requires_prescription.lower() == 'true')

        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset
    
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'roots', 'products', 'tree', 'descendants', 'ancestors']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAdmin]  # Changed from IsAdminUser
        return [permission() for permission in permission_classes]

    # === Custom Actions ===

    @action(detail=False, methods=['get'])
    def roots(self, request):
        """Get all root categories (no parent)"""
        queryset = self.get_queryset().filter(parent__isnull=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def tree(self, request):
        """
        Get full category tree for a ProductType.
        Usage: /api/categories/tree/?product_type=1
        """
        product_type_id = request.query_params.get('product_type')
        if not product_type_id:
            return Response(
                {'error': 'product_type parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get root categories for this type
        roots = Category.objects.filter(
            product_type_id=product_type_id,
            parent__isnull=True,
            is_active=True
        )
        serializer = self.get_serializer(roots, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def descendants(self, request, pk=None):
        """Get all descendant categories"""
        category = self.get_object()
        descendants = category.get_descendants()
        serializer = self.get_serializer(descendants, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def ancestors(self, request, pk=None):
        """Get all ancestor categories (breadcrumb trail)"""
        category = self.get_object()
        ancestors = category.get_ancestors()
        serializer = self.get_serializer(ancestors, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """Get all products in this category AND its descendants"""
        category = self.get_object()
        products = category.get_all_products().filter(is_active=True)
        
        # Apply pagination
        page = self.paginate_queryset(products)
        if page is not None:
            serializer = ProductSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)

    @extend_schema(
        responses={
            200: inline_serializer(
                name='CategoryStockSummary',
                fields={
                    'category': serializers.CharField(),
                    'full_path': serializers.CharField(),
                    'total_products': serializers.IntegerField(),
                    'total_stock': serializers.IntegerField(),
                    'total_value': serializers.FloatField(),
                }
            )
        }
    )
    @action(detail=True, methods=['get'])
    def stock_summary(self, request, pk=None):
        """Get stock summary for this category and all descendants"""
        category = self.get_object()
        return Response({
            'category': category.name,
            'full_path': category.full_path,
            'total_products': category.get_all_products().count(),
            'total_stock': category.get_total_stock(),
            'total_value': category.get_total_value(),  # Will update below
        })

    @extend_schema(
        request=inline_serializer(
            name='BulkMoveRequest',
            fields={
                'category_ids': serializers.ListField(child=serializers.IntegerField()),
                'new_parent_id': serializers.IntegerField(required=False, allow_null=True),
            }
        ),
        responses={
            200: inline_serializer(
                name='BulkMoveResponse',
                fields={
                    'moved': serializers.ListField(child=serializers.IntegerField()),
                    'errors': serializers.ListField(child=serializers.DictField()),
                }
            )
        }
    )
    @action(detail=False, methods=['post'])
    def bulk_move(self, request):
        """
        Move multiple categories to a new parent.
        Uses transaction.atomic for safety.
        """
        from django.db import transaction
        
        category_ids = request.data.get('category_ids', [])
        new_parent_id = request.data.get('new_parent_id')
        
        if not category_ids:
            return Response(
                {'error': 'category_ids is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        new_parent = None
        if new_parent_id:
            try:
                new_parent = Category.objects.get(id=new_parent_id)
            except Category.DoesNotExist:
                return Response(
                    {'error': 'New parent category not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

        with transaction.atomic():
            moved = []
            errors = []
            
            for cat_id in category_ids:
                try:
                    category = Category.objects.get(id=cat_id)
                    
                    # Validate type consistency
                    if new_parent and category.product_type_id != new_parent.product_type_id:
                        errors.append({
                            'category_id': cat_id,
                            'error': 'ProductType mismatch'
                        })
                        continue
                    
                    # Validate no circular reference
                    if new_parent and new_parent.is_descendant_of(category):
                        errors.append({
                            'category_id': cat_id,
                            'error': 'Would create circular reference'
                        })
                        continue
                    
                    category.parent = new_parent
                    category.save()
                    moved.append(cat_id)
                    
                except Category.DoesNotExist:
                    errors.append({
                        'category_id': cat_id,
                        'error': 'Category not found'
                    })

        return Response({
            'moved': moved,
            'errors': errors
        })
    
    # === Custom Querysets ===
    def get_queryset(self):
        queryset = Category.objects.all()

        # Filter by product type
        product_type_id = self.request.query_params.get('product_type')
        if product_type_id:
            queryset = queryset.filter(product_type_id=product_type_id)

        # Filter by depth level
        depth = self.request.query_params.get('depth')
        if depth:
            # Filter categories at specific depth
            category_ids = [c.id for c in Category.objects.all() if c.depth == int(depth)]
            queryset = queryset.filter(id__in=category_ids)

        # Filter by parent (for lazy loading)
        parent_id = self.request.query_params.get('parent')
        if parent_id:
            if parent_id == 'null':
                queryset = queryset.filter(parent__isnull=True)
            else:
                queryset = queryset.filter(parent_id=parent_id)

        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin | IsPharmacist]  # NEW: Admin OR Pharmacist can manage
        else:
            permission_classes = [IsAuthenticated]  # All roles can view
        return [permission() for permission in permission_classes]

    # Custom Queryset
    def get_queryset(self):
        queryset = Product.objects.all()

        """Filter products by search query"""
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)

        """Filter products by category"""
        category_id = self.request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        """Filter products by product_type"""
        product_type_id = self.request.query_params.get('product_type')
        if product_type_id:
            queryset = queryset.filter(product_type_id=product_type_id)

        """Filter products by base unit"""
        base_unit = self.request.query_params.get('base_unit')
        if base_unit:
            queryset = queryset.filter(base_unit=base_unit)

        """Filter products by expiration"""
        expired = self.request.query_params.get('expired')
        if expired == 'true':
            queryset = queryset.filter(expiration_date__lt=timezone.now().date())
        elif expired == 'false':
            queryset = queryset.filter(expiration_date__gte=timezone.now().date())

        """Filter products by low stock"""
        low_stock = self.request.query_params.get('low_stock')
        if low_stock == 'true':
            queryset = queryset.filter(stock_quantity__lt=10) 

        # Filter by prescription requirement (at product level)
        requires_prescription = self.request.query_params.get('requires_prescription')
        if requires_prescription is not None:
            queryset = queryset.filter(requires_prescription=requires_prescription.lower() == 'true')

        # Filter by product type's requires_expiration flag
        type_requires_expiration = self.request.query_params.get('type_requires_expiration')
        if type_requires_expiration is not None:
            queryset = queryset.filter(
                product_type__requires_expiration=type_requires_expiration.lower() == 'true'
            )

        # Filter by product type's requires_prescription flag
        type_requires_prescription = self.request.query_params.get('type_requires_prescription')
        if type_requires_prescription is not None:
            queryset = queryset.filter(
                product_type__requires_prescription=type_requires_prescription.lower() == 'true'
            )

        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset
    
    # Custom Logic
    def perform_create(self, serializer):
        product = serializer.save()

    # Custom Action
    @action(detail=False, methods=['get'])
    def expired(self, request):
        """Get all expired products"""
        expired = self.queryset.filter(
            expiration_date__lt=timezone.now().date(),
            is_active=True
        )
        serializer = self.get_serializer(expired, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Get all products with low stock"""
        low_stock = self.queryset.filter(
            stock_quantity__lt=10,
            is_active=True
        )
        serializer = self.get_serializer(low_stock, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """Get products expiring in the next 30 days"""
        soon = timezone.now().date() + timedelta(days=30)
        expiring = self.queryset.filter(
            expiration_date__lte=soon,
            expiration_date__gte=timezone.now().date(),
            is_active=True
        )
        serializer = self.get_serializer(expiring, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Get products grouped by product type"""
        product_type_id = request.query_params.get('product_type_id')
        if not product_type_id:
            return Response({"error": "product_type_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        products = self.get_queryset().filter(product_type_id=product_type_id)
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)

class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer

    def get_permissions(self):
        """
        Role-based access for Sales:
        - CREATE: Admin or Cashier
        - UPDATE/DELETE: Admin only
        - VIEW: All authenticated users
        """
        if self.action == 'create':
            permission_classes = [IsAdmin | IsCashier]  # NEW: Only Admin or Cashier can create
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin]  # Only Admin can modify/delete
        else:
            permission_classes = [IsAuthenticated]  # All can view
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = Sale.objects.all()

        # Cashiers see only their own sales by default
        if self.request.user.role == 'cashier':
            queryset = queryset.filter(cashier=self.request.user)

        # Admin/Pharmacist can see all sales with filters
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
        """Auto-assign cashier to current user"""
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
    
    @extend_schema(
        responses=inline_serializer(
            name='SaleReportResponse',
            fields={
                'today': serializers.DictField(),
                'this_month': serializers.DictField(),
            }
        )
    )
    @action(detail=False, methods=['get'])
    def report(self, request):
        """Get sales summary report"""
        from django.db.models import Sum, Count

        today = timezone.now().date()

        # Today's statistic
        today_sales = Sale.objects.filter(created_at__date=today)
        today_total = today_sales.aggregate(
            total=Sum('total_amount'),
            count=Count('id')
        )

        # This month's statistic
        month_start = today.replace(day=1)
        month_sales = Sale.objects.filter(created_at__date__gte=month_start)
        month_total = month_sales.aggregate(
            total=Sum('total_amount'),
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

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin | IsPharmacist]  # NEW: Admin or Pharmacist
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = Doctor.objects.all()

        # Search by name or license
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(license_number__icontains=search)
            )

        # Filter
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset
    
class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin | IsPharmacist]  # NEW: Admin or Pharmacist
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = Patient.objects.all()

        # Search by name or phone 
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(phone__icontains=search)
            )

        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset
    
    @action(detail=False, methods=['get'])
    def with_allergies(self, request):
        """Get patients who have allegy notes"""
        from django.db.models import Q
        patients = self.get_queryset().exclude(Q(allergy_notes__isnull=True) | Q(allergy_notes=''))
        serializer = self.get_serializer(patients, many=True)
        return Response(serializer.data)

class PrescriptionViewSet(viewsets.ModelViewSet):
    queryset = Prescription.objects.all()
    serializer_class = PrescriptionSerializer

    def get_permissions(self):
        """
        Role-based access for Prescriptions:
        - CREATE/UPDATE/DELETE: Admin or Pharmacist
        - VERIFY/REJECT: Admin or Pharmacist ONLY
        - VIEW: All authenticated users
        """
        if self.action in ['verify', 'reject']:
            permission_classes = [IsAdmin | IsPharmacist]  # NEW: Enforce pharmacist check
        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin | IsPharmacist]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

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

    def get_permissions(self):
        """
        Role-based access for Stock Movements:
        - CREATE: Admin or Pharmacist (for adjustments, purchases)
        - DELETE: Admin only (reverses stock)
        - VIEW: All authenticated users
        """
        if self.action == 'create':
            permission_classes = [IsAdmin | IsPharmacist]  # NEW: Only Admin/Pharmacist can create
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin]  # Only Admin can modify/delete
        else:
            permission_classes = [IsAuthenticated]  # All can view
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = StockMovement.objects.all()
        
        # Filter by product
        product_id = self.request.query_params.get('product')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        
        # Filter by movement type
        movement_type = self.request.query_params.get('movement_type')
        if movement_type:
            queryset = queryset.filter(movement_type=movement_type)
        
        # Filter by IN/OUT
        direction = self.request.query_params.get('direction')
        if direction == 'in':
            in_reasons = [r.value for r in StockMovement.Reason.get_in_reasons()]
            queryset = queryset.filter(movement_type__in=in_reasons)
        elif direction == 'out':
            out_reasons = [r.value for r in StockMovement.Reason.get_out_reasons()]
            queryset = queryset.filter(movement_type__in=out_reasons)

        # Filter by supplier
        supplier_id = self.request.query_params.get('supplier')
        if supplier_id:
            queryset = queryset.filter(suppliers_id=supplier_id)

        # Filter by sale
        sale_id = self.request.query_params.get('sale')
        if sale_id:
            queryset = queryset.filter(sale_id=sale_id)
        
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
        in_reasons = [r.value for r in StockMovement.Reason.get_in_reasons()]
        movements = self.queryset.filter(movement_type__in=in_reasons)
        serializer = self.get_serializer(movements, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stock_out(self, request):
        """Get all stock OUT movements"""
        out_reasons = [r.value for r in StockMovement.Reason.get_out_reasons()]
        movements = self.queryset.filter(movement_type__in=out_reasons)
        serializer = self.get_serializer(movements, many=True)
        return Response(serializer.data)

    @extend_schema(
        responses=inline_serializer(
            name='StockMovementSummaryResponse',
            fields={
                'total_in': serializers.IntegerField(),
                'total_out': serializers.IntegerField(),
                'net_change': serializers.IntegerField(),
            }
        )
    )
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get stock movement summary"""
        from django.db.models import Sum
        
        product_id = request.query_params.get('product')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        queryset = StockMovement.objects.all()
        
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        # Calculate totals
        in_reasons = [r.value for r in StockMovement.Reason.get_in_reasons()]
        out_reasons = [r.value for r in StockMovement.Reason.get_out_reasons()]
        
        total_in = queryset.filter(
            movement_type__in=in_reasons
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        total_out = queryset.filter(
            movement_type__in=out_reasons
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        return Response({
            'total_in': total_in,
            'total_out': total_out,
            'net_change': total_in - total_out
        })