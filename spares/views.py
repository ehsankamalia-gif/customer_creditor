from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import FormView, TemplateView

from accounts.mixins import StaffPermissionRequiredMixin

from . import services
from .forms import SpareTransactionForm


class TransactionsView(StaffPermissionRequiredMixin, TemplateView):
    permission_required = 'spares.view_spareledgertransaction'
    template_name = 'spares/transactions.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        month = self.request.GET.get('month') or None
        trans_type = self.request.GET.get('trans_type') or None
        rows = services.transactions_with_running_balance(month_key=month, trans_type=trans_type)
        context['rows'] = rows
        context['total_credits'] = sum(
            (r['transaction'].amount for r in rows if r['transaction'].trans_type == 'CREDIT'), 0)
        context['total_debits'] = sum(
            (r['transaction'].amount for r in rows if r['transaction'].trans_type == 'DEBIT'), 0)
        context['unique_months'] = services.unique_months()
        context['selected_month'] = month
        context['selected_trans_type'] = trans_type
        return context


class AddTransactionView(StaffPermissionRequiredMixin, FormView):
    permission_required = 'spares.add_spareledgertransaction'
    form_class = SpareTransactionForm
    template_name = 'spares/add_transaction.html'
    success_url = reverse_lazy('spares:transactions')

    def form_valid(self, form):
        data = form.cleaned_data
        services.record_transaction(
            trans_type=data['trans_type'], amount=data['amount'], cash_type=data['cash_type'],
            reference_number=data['reference_number'], description=data['description'],
            timestamp=data['timestamp'], created_by=self.request.user,
        )
        messages.success(self.request, 'Transaction recorded.')
        return super().form_valid(form)


class MonthlyReportView(StaffPermissionRequiredMixin, TemplateView):
    permission_required = 'spares.view_spareledgertransaction'
    template_name = 'spares/monthly_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report = services.monthly_report()
        context['report'] = report
        context['grand_total_credit'] = sum((r['total_credit'] for r in report), 0)
        context['grand_total_debit'] = sum((r['total_debit'] for r in report), 0)
        context['overall_balance'] = report[-1]['closing_balance'] if report else 0
        return context


class MonthlySummaryView(StaffPermissionRequiredMixin, TemplateView):
    permission_required = 'spares.view_spareledgertransaction'
    template_name = 'spares/monthly_summary.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        summary = services.monthly_summary()
        context['summary'] = summary
        context['current_balance'] = summary[-1]['balance'] if summary else 0
        context['closed_months'] = services.closed_months()
        return context


class CloseMonthView(StaffPermissionRequiredMixin, TemplateView):
    permission_required = 'spares.add_spareledgermonthlyclose'

    def post(self, request, *args, **kwargs):
        month_key = request.POST.get('month_key')
        try:
            services.close_month(month_key, closed_by=request.user)
            messages.success(request, f'{month_key} closed.')
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect(reverse('spares:monthly_summary'))
