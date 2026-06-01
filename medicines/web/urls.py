from django.urls import path
from medicines.web.views import *
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', home, name='home'),
    path('login/', login_page, name='template_login'),
    path('logout/', logout_view, name='template_logout'),
    path('categories/', categories_list, name='template_categories'),
    path('categories/create/', category_create, name='template_category_create'),
    path('categories/<int:id>/edit/', category_edit, name='template_category_edit'),
    path('categories/<int:id>/delete/', category_delete, name='template_category_delete'),
    path('categories/<int:id>/', category_detail, name='template_category_detail'),
]

# By default, Django's development server refuses to serve media files.
# If you upload an image and try to view it in the browser, you get a 404.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)