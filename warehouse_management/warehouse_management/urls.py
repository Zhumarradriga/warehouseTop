
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('warehouse/', include('warehouse.urls', namespace='warehouse')),
    path('login/', auth_views.LoginView.as_view(
        template_name='warehouse/login.html',
        redirect_authenticated_user=True
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='warehouse:dashboard'), name='logout'),
    path('', RedirectView.as_view(url='/warehouse/', permanent=True)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
