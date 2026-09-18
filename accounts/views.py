from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView

from .forms import SignUpForm


class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = 'accounts/signup.html'
    success_url = reverse_lazy('home')

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response


class HomeView(TemplateView):
    template_name = 'home.html'


class AccountView(LoginRequiredMixin, TemplateView):
    """A user's own account details. Every role - including customers - can reach this."""

    template_name = 'accounts/account.html'
