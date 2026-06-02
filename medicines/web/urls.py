from django.urls import path
from medicines.web.views import *
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', home, name='home'),
    path('login/', login_page, name='template-login'),
    path('logout/', logout_view, name='template-logout'),
    path('categories/', categories_list, name='template-categories'),
    path('categories/create/', category_create, name='template-category-create'),
    path('categories/<int:id>/edit/', category_edit, name='template-category-edit'),
    path('categories/<int:id>/delete/', category_delete, name='template-category-delete'),
    path('categories/<int:id>/', category_detail, name='template-category-detail'),
    path('categories/bulk-move/', category_bulk_move, name='template-category-bulk-move'),
    path('categories/roots/', category_roots, name='template-category-roots'),
    path('categories/tree/', category_tree, name='template-category-tree'),
]

# By default, Django's development server refuses to serve media files.
# If you upload an image and try to view it in the browser, you get a 404.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)