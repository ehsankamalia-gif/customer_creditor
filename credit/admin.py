from django.contrib import admin

from .models import CreditSale, Installment, LedgerEntry


class InstallmentInline(admin.TabularInline):
    model = Installment
    extra = 0
    fields = ('installment_no', 'due_date', 'amount_due', 'amount_paid', 'status')
    readonly_fields = ('installment_no',)


@admin.register(CreditSale)
class CreditSaleAdmin(admin.ModelAdmin):
    list_display = ('display_id', 'customer', 'item_label', 'status', 'credit_price', 'remaining_balance', 'sale_date')
    list_filter = ('status',)
    search_fields = ('customer__phone_number', 'customer__full_name', 'item_description')
    autocomplete_fields = ('customer', 'motorcycle', 'created_by')
    inlines = [InstallmentInline]


@admin.register(Installment)
class InstallmentAdmin(admin.ModelAdmin):
    list_display = ('sale', 'installment_no', 'due_date', 'amount_due', 'amount_paid', 'status')
    list_filter = ('status',)
    search_fields = ('sale__customer__phone_number', 'sale__customer__full_name', 'reference_no')
    autocomplete_fields = ('sale', 'recorded_by')


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ('customer', 'entry_type', 'debit', 'credit', 'balance', 'entry_date')
    list_filter = ('entry_type',)
    search_fields = ('customer__phone_number', 'customer__full_name', 'description')
    autocomplete_fields = ('customer', 'sale', 'installment')
