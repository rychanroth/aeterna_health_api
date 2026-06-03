from django.urls import path
from medicines.web.views import *
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', home, name='home'),
    path('login/', login_page, name='template-login'),
    path('logout/', logout_view, name='template-logout'),

    # CATEGORYs
    path('categories/', categories_list, name='template-category-list'),
    path('categories/create/', category_create, name='template-category-create'),
    path('categories/<int:id>/edit/', category_edit, name='template-category-edit'),
    path('categories/<int:id>/delete/', category_delete, name='template-category-delete'),
    path('categories/<int:id>/', category_detail, name='template-category-detail'),
    path('categories/bulk-move/', category_bulk_move, name='template-category-bulk-move'),
    path('categories/roots/', category_roots, name='template-category-roots'),
    path('categories/tree/', category_tree, name='template-category-tree'),

    # PRODUCT TYPE
    path('product-types/', product_type_list, name='template-product-type-list'),
    path('product-types/create/', product_type_create, name='template-product-type-create'),
    path('product-types/<int:id>/', product_type_detail, name='template-product-type-detail'),
    path('product-types/<int:id>/edit/', product_type_edit, name='template-product-type-edit'),
    path('product-types/<int:id>/delete/', product_type_delete, name='template-product-type-delete'),

    # SUPPLIER
    path('suppliers/', supplier_list, name='template-supplier-list'),
    path('suppliers/create/', supplier_create, name='template-supplier-create'),
    path('suppliers/<int:id>/', supplier_detail, name='template-supplier-detail'),
    path('suppliers/<int:id>/edit/', supplier_edit, name='template-supplier-edit'),
    path('suppliers/<int:id>/delete/', supplier_delete, name='template-supplier-delete'),

    # DOCTOR
    path('doctors/', doctor_list, name='template-doctor-list'),
    path('doctors/create/', doctor_create, name='template-doctor-create'),
    path('doctors/<int:id>/', doctor_detail, name='template-doctor-detail'),
    path('doctors/<int:id>/edit/', doctor_edit, name='template-doctor-edit'),
    path('doctors/<int:id>/delete/', doctor_delete, name='template-doctor-delete'),

    # PATIENT
    path('patients/', patient_list, name='template-patient-list'),
    path('patients/create/', patient_create, name='template-patient-create'),
    path('patients/<int:id>/', patient_detail, name='template-patient-detail'),
    path('patients/<int:id>/edit/', patient_edit, name='template-patient-edit'),
    path('patients/<int:id>/delete/', patient_delete, name='template-patient-delete'),

    # STOCK MOVEMENT
    path('stock-movements/', stock_movement_list, name='template-stock-movement-list'),
    path('stock-movements/summary/', stock_movement_summary, name='template-stock-movement-summary'),
    # path('stock-movements/create/', stoc    k_movement_create, name='template-stock-movement-create'),
    path('stock-movements/<int:id>/', stock_movement_detail, name='template-stock-movement-detail'),

    # PRESCRIPTION
    path('prescriptions/', prescription_list, name='template-prescription-list'),
    path('prescriptions/create/', prescription_create, name='template-prescription-create'),
    path('prescriptions/<int:id>/', prescription_detail, name='template-prescription-detail'),
    path('prescriptions/<int:id>/verify/', prescription_verify, name='template-prescription-verify'),
    path('prescriptions/<int:id>/reject/', prescription_reject, name='template-prescription-reject'),
]

# By default, Django's development server refuses to serve media files.
# If you upload an image and try to view it in the browser, you get a 404.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)