import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, FormView, ListView, TemplateView

from accounts.mixins import StaffPermissionRequiredMixin
from accounts.services import get_manageable_user

from . import services
from .forms import CreditSaleForm, PaymentForm
from .models import CreditSale, LedgerEntry


# --- Customer-facing views --------------------------------------------------

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'credit/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(services.customer_dashboard_context(self.request.user))
        return context


class SaleDetailView(LoginRequiredMixin, DetailView):
    template_name = 'credit/sale_detail.html'
    context_object_name = 'sale'

    def get_object(self, queryset=None):
        sale = services.sale_visible_to(self.request.user, self.kwargs['pk'])
        if sale is None:
            raise Http404('Credit sale not found.')
        return sale

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ledger_entries'] = services.sale_ledger(self.object)
        context['installments'] = self.object.installments.all()
        return context


class PaymentsView(LoginRequiredMixin, TemplateView):
    template_name = 'credit/payments.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payments = services.customer_payments(self.request.user)
        context['payments'] = payments
        context['total_paid'] = sum((p.credit for p in payments), 0)
        return context


class RunningLedgerView(LoginRequiredMixin, TemplateView):
    template_name = 'credit/running_ledger.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ledger_entries'] = services.customer_ledger(self.request.user)
        return context


# --- Staff-facing views ------------------------------------------------------

class StaffSalesListView(StaffPermissionRequiredMixin, ListView):
    permission_required = 'credit.view_creditsale'
    template_name = 'credit/staff/sales_list.html'
    context_object_name = 'sales'
    queryset = services.all_sales()
    paginate_by = 50


class StaffCreateSaleView(StaffPermissionRequiredMixin, FormView):
    permission_required = 'credit.add_creditsale'
    form_class = CreditSaleForm
    template_name = 'credit/staff/create_sale.html'

    def form_valid(self, form):
        data = form.cleaned_data
        sale = services.create_credit_sale(
            customer=data['customer'],
            motorcycle=data['motorcycle'],
            item_description=data['item_description'],
            cash_price=data['cash_price'],
            credit_price=data['credit_price'],
            down_payment=data['down_payment'] or 0,
            down_payment_method=data['down_payment_method'],
            duration_months=data['duration_months'],
            sale_date=data['sale_date'],
            notes=data['notes'],
            created_by=self.request.user,
        )
        messages.success(self.request, f'Credit sale {sale.display_id} created for {sale.customer}.')
        self._sale = sale
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('credit:staff_sale_detail', args=[self._sale.pk])


class StaffSaleDetailView(StaffPermissionRequiredMixin, DetailView):
    permission_required = 'credit.view_creditsale'
    template_name = 'credit/staff/sale_detail.html'
    context_object_name = 'sale'
    queryset = CreditSale.objects.select_related('customer', 'motorcycle')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ledger_entries'] = services.sale_ledger(self.object)
        context['installments'] = self.object.installments.all()
        return context


class StaffRecordPaymentView(StaffPermissionRequiredMixin, FormView):
    permission_required = 'credit.change_installment'
    form_class = PaymentForm
    template_name = 'credit/staff/record_payment.html'

    def dispatch(self, request, *args, **kwargs):
        self.sale = get_object_or_404(CreditSale.objects.select_related('customer'), pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['sale'] = self.sale
        return context

    def form_valid(self, form):
        data = form.cleaned_data
        services.record_payment(
            sale=self.sale,
            amount=data['amount'],
            payment_date=data['payment_date'],
            payment_method=data['payment_method'],
            reference_no=data['reference_no'],
            notes=data['notes'],
            recorded_by=self.request.user,
        )
        messages.success(self.request, f'Payment of {data["amount"]} recorded for {self.sale.display_id}.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('credit:staff_sale_detail', args=[self.sale.pk])


class StaffCustomerSummaryView(StaffPermissionRequiredMixin, TemplateView):
    permission_required = 'credit.view_creditsale'
    template_name = 'credit/staff/customer_summary.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['summary'] = services.customers_summary()
        return context


class StaffCustomerDetailView(StaffPermissionRequiredMixin, TemplateView):
    permission_required = 'credit.view_creditsale'
    template_name = 'credit/staff/customer_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = get_manageable_user(self.kwargs['pk'])
        context['customer'] = customer
        context.update(services.customer_detail_context(customer))
        return context


class StaffTransactionsView(StaffPermissionRequiredMixin, ListView):
    permission_required = 'credit.view_ledgerentry'
    template_name = 'credit/staff/transactions.html'
    context_object_name = 'entries'
    queryset = services.all_ledger_entries()
    paginate_by = 100


@login_required
@permission_required('credit.view_creditsale', raise_exception=True)
def staff_export_sales_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="credit_sales.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Customer', 'Item', 'Status', 'Credit Price', 'Remaining Balance', 'Sale Date'])
    for sale in services.all_sales():
        writer.writerow([
            sale.display_id, str(sale.customer), sale.item_label, sale.status,
            sale.credit_price, sale.remaining_balance, sale.sale_date,
        ])
    return response


@login_required
@permission_required('credit.view_ledgerentry', raise_exception=True)
def staff_export_payments_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="payments.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Customer', 'Sale', 'Description', 'Amount', 'Date'])
    for entry in services.all_payments():
        writer.writerow([
            entry.id, str(entry.customer), entry.sale.display_id if entry.sale else '',
            entry.description, entry.credit, entry.entry_date,
        ])
    return response
