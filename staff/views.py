from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, TemplateView

from accounts.forms import AdminAccountCreationForm, CustomerCreationForm
from accounts.mixins import StaffPermissionRequiredMixin, StaffRequiredMixin, SuperuserRequiredMixin


class StaffDashboardView(StaffRequiredMixin, TemplateView):
    template_name = 'staff/staff_dashboard.html'


class UserDirectoryView(StaffPermissionRequiredMixin, TemplateView):
    permission_required = 'accounts.view_user'
    template_name = 'staff/user_directory.html'


class StaffManagementView(SuperuserRequiredMixin, TemplateView):
    template_name = 'staff/staff_management.html'


class AdminCreateAccountView(SuperuserRequiredMixin, CreateView):
    """Admins can register a new account as either Staff or Customer."""

    form_class = AdminAccountCreationForm
    template_name = 'staff/admin_create_account.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Account created for {self.object.phone_number}.')
        return response

    def get_success_url(self):
        return reverse('staff:staff_management' if self.object.is_staff else 'staff:user_directory')


class StaffCreateCustomerView(StaffPermissionRequiredMixin, CreateView):
    """Staff (granted the 'add_user' permission by an admin) can register new customers only."""

    permission_required = 'accounts.add_user'
    form_class = CustomerCreationForm
    template_name = 'staff/create_customer.html'
    success_url = reverse_lazy('staff:staff_dashboard')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Customer account created for {self.object.phone_number}.')
        return response
