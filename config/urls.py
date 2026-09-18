from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from accounts.forms import PhoneAuthenticationForm
from accounts.views import HomeView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('accounts/', include('staff.urls')),
    path('accounts/login/', auth_views.LoginView.as_view(form_class=PhoneAuthenticationForm), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('inventory.urls')),
    path('', include('credit.urls')),
    path('', include('spares.urls')),
    path('', HomeView.as_view(), name='home'),
]
