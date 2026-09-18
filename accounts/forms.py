from django import forms
from django.contrib.auth.forms import AuthenticationForm as BaseAuthenticationForm
from django.contrib.auth.forms import UserChangeForm as BaseUserChangeForm
from django.contrib.auth.forms import UserCreationForm as BaseUserCreationForm

from .models import User


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            bootstrap_class = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
            field.widget.attrs['class'] = (existing + ' ' + bootstrap_class).strip()


class UserCreationForm(BaseUserCreationForm):
    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = ('phone_number', 'full_name')


class UserChangeForm(BaseUserChangeForm):
    class Meta(BaseUserChangeForm.Meta):
        model = User
        fields = ('phone_number', 'full_name')


class SignUpForm(BootstrapFormMixin, BaseUserCreationForm):
    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = ('phone_number', 'full_name')


class PhoneAuthenticationForm(BootstrapFormMixin, BaseAuthenticationForm):
    pass


class CustomerCreationForm(BootstrapFormMixin, BaseUserCreationForm):
    """Used by staff to register a new customer. Role is fixed - not a form field."""

    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = ('phone_number', 'full_name')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
        return user


class AdminAccountCreationForm(BootstrapFormMixin, BaseUserCreationForm):
    """Used by admins to register a new staff member or customer."""

    ROLE_CHOICES = (
        ('customer', 'Customer'),
        ('staff', 'Staff'),
    )
    role = forms.ChoiceField(choices=ROLE_CHOICES, initial='customer')

    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = ('phone_number', 'full_name')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = self.cleaned_data['role'] == 'staff'
        user.is_superuser = False
        if commit:
            user.save()
        return user
