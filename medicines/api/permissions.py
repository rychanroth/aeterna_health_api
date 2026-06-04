"""
Custom Permission Classes for Pharmacy Management System
=========================================================

Role Hierarchy:
- ADMIN: Full access to all resources
- PHARMACIST: Products, Stock adjustments, Prescription verification
- CASHIER: Sales, Products (read-only)

Usage in views:
    from medicines.core.permissoins import IsAdmin, IsPharmacist, IsCashier, IsAdminOrPharmacist

    class ProductViewSet(viewsets.ModelViewSet):
        def get_permissions(self):
            if self.action in ['create', 'update', 'destroy']:
                permission_classes = [IsAdmin | IsPharmacist]
            else:
                permission_classes = [IsAuthenticated]
            return [permission() for permission in permission_classes]
"""

from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """
    Allows access only to users with role='admin'.
    """
    message = "This action requires Admin privileges."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == 'admin'
        )


class IsPharmacist(BasePermission):
    """
    Allows access only to users with role='pharmacist'.
    """
    message = "This action requires Pharmacist privileges."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == 'pharmacist'
        )


class IsCashier(BasePermission):
    """
    Allows access only to users with role='cashier'.
    """
    message = "This action requires Cashier privileges."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == 'cashier'
        )


class IsAdminOrPharmacist(BasePermission):
    """
    Allows access to Admin or Pharmacist users.
    Used for: Stock adjustments, Prescription verification, Product management
    """
    message = "This action requires Admin or Pharmacist privileges."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['admin', 'pharmacist']
        )


class IsAdminOrCashier(BasePermission):
    """
    Allows access to Admin or Cashier users.
    Used for: Creating sales
    """
    message = "This action requires Admin or Cashier privileges."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['admin', 'cashier']
        )


class IsAdminOrPharmacistOrCashier(BasePermission):
    """
    Allows access to all authenticated users with defined roles.
    Equivalent to IsAuthenticated but with role validation.
    """
    message = "This action requires a valid user role."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['admin', 'pharmacist', 'cashier']
        )


class IsOwnerOrAdmin(BasePermission):
    """
    Object-level permission: Allow access to object owner or admin.
    Used for: Users viewing/editing their own data.
    """
    message = "You can only access your own data."

    def has_object_permission(self, request, view, obj):
        # Admin has full access
        if request.user.role == 'admin':
            return True

        # Check if object has a user field or is the user itself
        if hasattr(obj, 'user'):
            return obj.user == request.user
        if hasattr(obj, 'cashier'):
            return obj.cashier == request.user

        return obj == request.user


# === COMBINED PERMISSIONS FOR SPECIFIC USE CASES ===

class CanManageProducts(BasePermission):
    """
    Product management: Admin can CRUD, Pharmacist can view.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Admin can do anything
        if request.user.role == 'admin':
            return True

        # Pharmacist and Cashier can only read
        if request.user.role in ['pharmacist', 'cashier']:
            return request.method in ['GET', 'HEAD', 'OPTIONS']

        return False


class CanManageStock(BasePermission):
    """
    Stock movements: Admin and Pharmacist can create, others can view.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Admin and Pharmacist can create stock movements
        if request.user.role in ['admin', 'pharmacist']:
            return True

        # Cashier can only view
        if request.user.role == 'cashier':
            return request.method in ['GET', 'HEAD', 'OPTIONS']

        return False


class CanVerifyPrescriptions(BasePermission):
    """
    Prescription verification: Admin and Pharmacist only.
    """
    message = "Only Admin or Pharmacist can verify prescriptions."

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['admin', 'pharmacist']
        )


class CanCreateSales(BasePermission):
    """
    Sales creation: Admin and Cashier only.
    """
    message = "Only Admin or Cashier can create sales."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Admin and Cashier can create sales
        if request.user.role in ['admin', 'cashier']:
            return True

        # Pharmacist can only view
        if request.user.role == 'pharmacist':
            return request.method in ['GET', 'HEAD', 'OPTIONS']

        return False
