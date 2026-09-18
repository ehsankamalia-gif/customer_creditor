from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView, UpdateView

from accounts.mixins import StaffPermissionRequiredMixin

from . import importers, services
from .forms import MotorcycleEditForm, MotorcycleForm, ProductModelForm, StockImportForm, StockLocationForm, SupplierForm
from .models import Motorcycle


class InventoryDashboardView(StaffPermissionRequiredMixin, TemplateView):
    permission_required = 'inventory.view_motorcycle'
    template_name = 'inventory/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stats'] = services.summary_stats()
        return context


class InventoryListView(StaffPermissionRequiredMixin, ListView):
    permission_required = 'inventory.view_motorcycle'
    template_name = 'inventory/inventory_list.html'
    context_object_name = 'motorcycles'
    paginate_by = 50

    def get_queryset(self):
        params = self.request.GET
        return services.search_motorcycles(
            query=(params.get('q') or '').strip() or None,
            status=params.get('status') or None,
            product_model_id=params.get('model') or None,
            color=params.get('color') or None,
            location_id=params.get('location') or None,
            ordering=params.get('sort') or None,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['product_models'] = services.list_product_models()
        context['locations'] = services.list_locations()
        context['colors'] = services.list_colors_in_use()
        context['status_choices'] = Motorcycle.STATUS_CHOICES
        params = self.request.GET
        context['filters'] = {
            'q': params.get('q', ''),
            'status': params.get('status', ''),
            'model': params.get('model', ''),
            'color': params.get('color', ''),
            'location': params.get('location', ''),
            'sort': params.get('sort', ''),
        }
        return context


class MotorcycleDetailView(StaffPermissionRequiredMixin, DetailView):
    permission_required = 'inventory.view_motorcycle'
    template_name = 'inventory/motorcycle_detail.html'
    context_object_name = 'motorcycle'
    queryset = Motorcycle.objects.select_related('product_model', 'purchase_supplier', 'location')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = [c for c in Motorcycle.STATUS_CHOICES if c[0] != Motorcycle.SOLD]
        return context


class AddMotorcycleView(StaffPermissionRequiredMixin, CreateView):
    permission_required = 'inventory.add_motorcycle'
    form_class = MotorcycleForm
    template_name = 'inventory/add_motorcycle.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Added {self.object.chassis_number} to stock.')
        return response

    def get_success_url(self):
        return reverse('inventory:motorcycle_detail', args=[self.object.pk])


class EditMotorcycleView(StaffPermissionRequiredMixin, UpdateView):
    permission_required = 'inventory.change_motorcycle'
    form_class = MotorcycleEditForm
    template_name = 'inventory/edit_motorcycle.html'
    queryset = Motorcycle.objects.select_related('product_model')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Updated {self.object.chassis_number}.')
        return response

    def get_success_url(self):
        return reverse('inventory:motorcycle_detail', args=[self.object.pk])


class AddProductModelView(StaffPermissionRequiredMixin, CreateView):
    permission_required = 'inventory.add_productmodel'
    form_class = ProductModelForm
    template_name = 'inventory/add_product_model.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Added product model {self.object.model_name}.')
        return response

    def get_success_url(self):
        return reverse('inventory:inventory_list')


class AddSupplierView(StaffPermissionRequiredMixin, CreateView):
    permission_required = 'inventory.add_supplier'
    form_class = SupplierForm
    template_name = 'inventory/add_supplier.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Added supplier {self.object.name}.')
        return response

    def get_success_url(self):
        return reverse('inventory:inventory_list')


class AddLocationView(StaffPermissionRequiredMixin, CreateView):
    permission_required = 'inventory.add_stocklocation'
    form_class = StockLocationForm
    template_name = 'inventory/add_location.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Added location {self.object.name}.')
        return response

    def get_success_url(self):
        return reverse('inventory:inventory_list')


class ImportStockView(StaffPermissionRequiredMixin, FormView):
    """Bulk-load/sync stock from a supplier portal's CSV export.

    Renders the results (counts + per-row errors) on the same page instead
    of redirecting away, since staff need to see exactly which rows - if
    any - didn't import cleanly.
    """

    permission_required = 'inventory.add_motorcycle'
    form_class = StockImportForm
    template_name = 'inventory/import_stock.html'

    def form_valid(self, form):
        source = form.cleaned_data.get('file') or form.cleaned_data['pasted_data']
        rows = importers.parse_stock_rows(source)
        result = importers.import_stock_rows(rows) if rows else {
            'created': 0, 'updated': 0, 'unchanged': 0,
            'errors': ['No data rows were found - check that a header row is included.'],
        }

        if result['created'] or result['updated']:
            messages.success(
                self.request,
                f"Imported {result['created']} new unit(s), updated {result['updated']}, "
                f"{result['unchanged']} already up to date.",
            )
        if result['errors']:
            messages.warning(self.request, f"{len(result['errors'])} row(s) could not be imported - see details below.")

        return self.render_to_response(self.get_context_data(form=self.form_class(), result=result))


@login_required
@permission_required('inventory.change_motorcycle', raise_exception=True)
def change_status(request, pk):
    """A staff-triggered status change - anything except undoing a sale.

    Kept as a small dedicated endpoint (rather than folding status into the
    edit form) so a status change is always an explicit action with its own
    audit-friendly entry point, not a side effect of an unrelated field edit.
    """
    motorcycle = get_object_or_404(Motorcycle, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid_statuses = {c[0] for c in Motorcycle.STATUS_CHOICES if c[0] != Motorcycle.SOLD}
        if new_status not in valid_statuses:
            messages.error(request, 'Please choose a valid status.')
        else:
            try:
                services.change_status(motorcycle, new_status)
                messages.success(request, f'{motorcycle.chassis_number} marked {motorcycle.get_status_display()}.')
            except ValueError as exc:
                messages.error(request, str(exc))
    return redirect('inventory:motorcycle_detail', pk=pk)


@login_required
@permission_required('inventory.change_motorcycle', raise_exception=True)
def return_to_stock(request, pk):
    """The deliberate, separate operation for undoing a sale (see services.py)."""
    motorcycle = get_object_or_404(Motorcycle, pk=pk)
    if request.method == 'POST':
        services.return_to_stock(motorcycle)
        messages.success(request, f'{motorcycle.chassis_number} returned to stock.')
    return redirect('inventory:motorcycle_detail', pk=pk)


@login_required
@permission_required('inventory.delete_motorcycle', raise_exception=True)
def archive_motorcycle(request, pk):
    motorcycle = get_object_or_404(Motorcycle, pk=pk)
    if request.method == 'POST':
        services.archive_motorcycle(motorcycle)
        messages.success(request, f'{motorcycle.chassis_number} archived.')
    return redirect('inventory:inventory_list')


@login_required
@permission_required('inventory.delete_motorcycle', raise_exception=True)
def restore_motorcycle(request, pk):
    motorcycle = get_object_or_404(Motorcycle, pk=pk)
    if request.method == 'POST':
        services.restore_motorcycle(motorcycle)
        messages.success(request, f'{motorcycle.chassis_number} restored.')
    return redirect('inventory:motorcycle_detail', pk=pk)
