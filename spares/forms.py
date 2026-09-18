from django import forms
from django.utils import timezone

from accounts.forms import BootstrapFormMixin

from .models import SpareLedgerTransaction


class SpareTransactionForm(BootstrapFormMixin, forms.Form):
    trans_type = forms.ChoiceField(choices=SpareLedgerTransaction.TRANS_TYPE_CHOICES)
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    cash_type = forms.ChoiceField(choices=SpareLedgerTransaction.CASH_TYPE_CHOICES, initial=SpareLedgerTransaction.CASH)
    timestamp = forms.DateTimeField(
        initial=timezone.now,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        input_formats=['%Y-%m-%dT%H:%M'],
    )
    reference_number = forms.CharField(max_length=50, required=False)
    description = forms.CharField(max_length=255, required=False)
