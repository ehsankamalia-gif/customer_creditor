from django.urls import path

from . import api
from .views import (
    AdminCreateAccountView,
    StaffCreateCustomerView,
    StaffDashboardView,
    StaffManagementView,
    UserDirectoryView,
)

app_name = 'staff'

urlpatterns = [
    path('staff/', StaffDashboardView.as_view(), name='staff_dashboard'),
    path('staff/users/', UserDirectoryView.as_view(), name='user_directory'),
    path('staff/manage/', StaffManagementView.as_view(), name='staff_management'),
    path('staff/accounts/new/', AdminCreateAccountView.as_view(), name='admin_create_account'),
    path('staff/customers/new/', StaffCreateCustomerView.as_view(), name='create_customer'),
    path('api/users/', api.user_list, name='api_user_list'),
    path('api/users/<int:pk>/permissions/', api.user_permissions, name='api_user_permissions'),
    path('api/users/<int:pk>/role/', api.user_role, name='api_user_role'),
]
