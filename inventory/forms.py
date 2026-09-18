from django import forms

from accounts.forms import BootstrapFormMixin

from .models import Motorcycle, ProductModel, StockLocation, Supplier


class ProductModelForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ProductModel
        fields = ['model_name', 'make', 'engine_capacity', 'pct_code', 'item_code']


class SupplierForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'contact_person', 'phone', 'address']


class StockLocationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = StockLocation
        fields = ['name']


class MotorcycleForm(BootstrapFormMixin, forms.ModelForm):
    """Adds a brand-new unit to stock."""

    class Meta:
        model = Motorcycle
        fields = [
            'product_model', 'chassis_number', 'engine_number', 'vin', 'year', 'color',
            'purchase_supplier', 'purchase_reference', 'purchase_price', 'purchase_date',
            'selling_price', 'status', 'location', 'notes',
        ]
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class MotorcycleEditForm(BootstrapFormMixin, forms.ModelForm):
    """Edits an existing unit.

    Once a unit is marked Sold, the fields that describe the original
    purchase/identity (chassis, engine, VIN, purchase details) are dropped
    from the form entirely - not just disabled in the browser. A disabled
    HTML field is only a UI suggestion and isn't submitted at all, so the
    reliable way to stop a field from being changed is to never accept it
    as input in the first place.
    """

    class Meta:
        model = Motorcycle
        fields = [
            'product_model', 'chassis_number', 'engine_number', 'vin', 'year', 'color',
            'purchase_supplier', 'purchase_reference', 'purchase_price', 'purchase_date',
            'selling_price', 'location', 'notes',
        ]
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.is_locked:
            for field_name in Motorcycle.LOCKED_AFTER_SALE_FIELDS:
                self.fields.pop(field_name, None)


class StockImportForm(BootstrapFormMixin, forms.Form):
    """A file (.xlsx or .csv) or pasted table data is accepted - whichever
    is easier depending on what the source portal lets you export/copy."""

    file = forms.FileField(
        required=False,
        help_text='An .xlsx or .csv export (Purchase Order, Recv. Date, Model, Colour, Engine No, Chassis No, Status).',
    )
    pasted_data = forms.CharField(
        required=False, label='Or paste rows',
        widget=forms.Textarea(attrs={
            'rows': 10,
            'placeholder': 'Paste rows copied from the portal here, including the header row.',
        }),
    )

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('file') and not cleaned.get('pasted_data', '').strip():
            raise forms.ValidationError('Upload a CSV file or paste rows to import.')
        return cleaned
