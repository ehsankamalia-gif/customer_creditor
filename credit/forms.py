from django import forms
from django.utils import timezone

from accounts.forms import BootstrapFormMixin
from accounts.services import list_customers
from inventory.services import list_in_stock_motorcycles

PAYMENT_METHOD_CHOICES = [('Cash', 'Cash'), ('Bank', 'Bank')]


class CreditSaleForm(BootstrapFormMixin, forms.Form):
    customer = forms.ModelChoiceField(queryset=list_customers().none())
    motorcycle = forms.ModelChoiceField(
        queryset=list_in_stock_motorcycles().none(), required=False,
        help_text='Leave blank for a credit sale that is not a motorcycle.',
    )
    item_description = forms.CharField(
        max_length=255, required=False,
        help_text='Required if no motorcycle is selected.',
    )
    cash_price = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, initial=0)
    credit_price = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    down_payment = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, initial=0, required=False)
    down_payment_method = forms.ChoiceField(choices=PAYMENT_METHOD_CHOICES, initial='Cash')
    duration_months = forms.IntegerField(min_value=1, initial=12)
    sale_date = forms.DateField(initial=timezone.localdate, widget=forms.DateInput(attrs={'type': 'date'}))
    notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Fetched fresh per-request rather than at class-definition time.
        self.fields['customer'].queryset = list_customers()
        self.fields['motorcycle'].queryset = list_in_stock_motorcycles()

    def clean(self):
        cleaned = super().clean()
        motorcycle = cleaned.get('motorcycle')
        item_description = cleaned.get('item_description')
        if not motorcycle and not item_description:
            raise forms.ValidationError('Select a motorcycle or describe the item being financed.')

        credit_price = cleaned.get('credit_price')
        down_payment = cleaned.get('down_payment') or 0
        if credit_price is not None and down_payment > credit_price:
            self.add_error('down_payment', 'Down payment cannot exceed the credit price.')
        return cleaned


class PaymentForm(BootstrapFormMixin, forms.Form):
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    payment_date = forms.DateField(initial=timezone.localdate, widget=forms.DateInput(attrs={'type': 'date'}))
    payment_method = forms.ChoiceField(choices=PAYMENT_METHOD_CHOICES, initial='Cash')
    reference_no = forms.CharField(max_length=50, required=False)
    notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)
