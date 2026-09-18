from django.contrib import admin

from .models import SpareLedgerMonthlyClose, SpareLedgerTransaction


@admin.register(SpareLedgerTransaction)
class SpareLedgerTransactionAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'trans_type', 'amount', 'cash_type', 'month_key', 'reference_number')
    list_filter = ('trans_type', 'cash_type', 'month_key')
    search_fields = ('reference_number', 'description')


@admin.register(SpareLedgerMonthlyClose)
class SpareLedgerMonthlyCloseAdmin(admin.ModelAdmin):
    list_display = ('month_key', 'opening_balance', 'total_credits', 'total_debits', 'closing_balance', 'closed_at')
