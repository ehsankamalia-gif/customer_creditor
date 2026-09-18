"""Public API of the credit module.

Other modules must go through these functions instead of importing
credit.models and querying CreditSale/Installment/LedgerEntry directly.
"""
import calendar
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from inventory.services import mark_sold

from .models import CreditSale, Installment, LedgerEntry

ZERO = Decimal('0')
TWO_PLACES = Decimal('0.01')


def _add_months(date, months):
    month_index = date.month - 1 + months
    year = date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(date.day, calendar.monthrange(year, month)[1])
    return date.replace(year=year, month=month, day=day)


def _record_ledger_entry(customer, *, sale=None, installment=None, entry_type,
                          description, debit=ZERO, credit=ZERO, entry_date=None):
    entry_date = entry_date or timezone.localdate()
    last = LedgerEntry.objects.filter(customer=customer).order_by('-entry_date', '-id').first()
    running_balance = (last.balance if last else ZERO) + debit - credit
    return LedgerEntry.objects.create(
        customer=customer, sale=sale, installment=installment, entry_type=entry_type,
        description=description, debit=debit, credit=credit, balance=running_balance,
        entry_date=entry_date,
    )


@transaction.atomic
def create_credit_sale(*, customer, motorcycle, item_description, cash_price, credit_price,
                        down_payment, down_payment_method, duration_months, sale_date, notes, created_by):
    """Create a credit sale, its instalment schedule and its opening ledger entries."""
    down_payment = down_payment or ZERO
    duration_months = max(int(duration_months), 1)
    financed_amount = credit_price - down_payment
    installment_amount = (financed_amount / duration_months).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    sale = CreditSale.objects.create(
        customer=customer,
        motorcycle=motorcycle,
        item_description=item_description,
        cash_price=cash_price,
        credit_price=credit_price,
        down_payment=down_payment,
        down_payment_method=down_payment_method,
        duration_months=duration_months,
        installment_amount=installment_amount,
        sale_date=sale_date,
        due_date=_add_months(sale_date, duration_months),
        remaining_balance=financed_amount,
        notes=notes,
        created_by=created_by,
    )

    if motorcycle is not None:
        mark_sold(motorcycle)

    _record_ledger_entry(
        customer, sale=sale, entry_type=LedgerEntry.DEBIT,
        description=f'Credit sale {sale.display_id} - {sale.item_label}',
        debit=credit_price, entry_date=sale_date,
    )

    if down_payment > 0:
        _record_ledger_entry(
            customer, sale=sale, entry_type=LedgerEntry.CREDIT,
            description=f'Down payment ({down_payment_method}) - {sale.display_id}',
            credit=down_payment, entry_date=sale_date,
        )

    allocated = ZERO
    for number in range(1, duration_months + 1):
        amount = installment_amount
        if number == duration_months:
            amount = financed_amount - allocated  # last instalment absorbs rounding
        allocated += amount
        Installment.objects.create(
            sale=sale, installment_no=number, due_date=_add_months(sale_date, number),
            amount_due=amount,
        )

    if financed_amount <= 0:
        sale.status = CreditSale.CLOSED
        sale.save(update_fields=['status'])

    return sale


@transaction.atomic
def record_payment(*, sale, amount, payment_date, payment_method, reference_no, notes, recorded_by):
    """Apply a payment to a sale's oldest unpaid instalments and log it on the ledger."""
    amount = Decimal(amount)
    remaining = amount
    touched_installment = None

    for installment in sale.installments.filter(status__in=[Installment.PENDING, Installment.PARTIAL]).order_by('installment_no'):
        if remaining <= 0:
            break
        owed = installment.balance_due
        if owed <= 0:
            continue
        applied = min(owed, remaining)
        installment.amount_paid += applied
        installment.payment_date = payment_date
        installment.payment_method = payment_method
        installment.reference_no = reference_no
        installment.notes = notes
        installment.recorded_by = recorded_by
        installment.status = Installment.PAID if installment.balance_due <= 0 else Installment.PARTIAL
        installment.save()
        touched_installment = touched_installment or installment
        remaining -= applied

    _record_ledger_entry(
        sale.customer, sale=sale, installment=touched_installment, entry_type=LedgerEntry.CREDIT,
        description=notes or f'Payment ({payment_method}) - {sale.display_id}',
        credit=amount, entry_date=payment_date,
    )

    sale.remaining_balance = max(sale.remaining_balance - amount, ZERO)
    if sale.remaining_balance <= 0:
        sale.status = CreditSale.CLOSED
    sale.save(update_fields=['remaining_balance', 'status'])

    return sale


def mark_overdue_sales():
    """Flag active sales past their due date as overdue. Intended for a periodic task."""
    today = timezone.localdate()
    return CreditSale.objects.filter(status=CreditSale.ACTIVE, due_date__lt=today).update(status=CreditSale.OVERDUE)


# --- Read queries -----------------------------------------------------------

def get_sale(pk):
    return CreditSale.objects.select_related('customer', 'motorcycle').get(pk=pk)


def sale_visible_to(user, pk):
    """A sale, or None, restricted to the given user unless they're staff."""
    qs = CreditSale.objects.select_related('customer', 'motorcycle')
    if not user.is_staff:
        qs = qs.filter(customer=user)
    return qs.filter(pk=pk).first()


def sale_ledger(sale):
    return sale.ledger_entries.select_related('installment').all()


def customer_active_sales(customer):
    return CreditSale.objects.filter(customer=customer, status__in=[CreditSale.ACTIVE, CreditSale.OVERDUE]).select_related('motorcycle')


def customer_closed_sales(customer):
    return CreditSale.objects.filter(customer=customer, status=CreditSale.CLOSED).select_related('motorcycle')


def customer_ledger(customer):
    return LedgerEntry.objects.filter(customer=customer).select_related('sale').all()


def customer_payments(customer):
    return LedgerEntry.objects.filter(customer=customer, credit__gt=0).select_related('sale').order_by('-entry_date', '-id')


def customer_dashboard_context(customer):
    active = list(customer_active_sales(customer).order_by('-sale_date'))
    closed = list(customer_closed_sales(customer).order_by('-sale_date')[:5])
    total_outstanding = sum((s.remaining_balance for s in active), ZERO)
    total_paid = customer_payments(customer).aggregate(total=Sum('credit'))['total'] or ZERO
    return {
        'active_sales': active,
        'closed_sales': closed,
        'total_outstanding': total_outstanding,
        'total_paid': total_paid,
    }


def all_sales():
    return CreditSale.objects.select_related('customer', 'motorcycle').all()


def all_payments():
    return LedgerEntry.objects.filter(credit__gt=0).select_related('customer', 'sale').order_by('-entry_date', '-id')


def all_ledger_entries():
    return LedgerEntry.objects.select_related('customer', 'sale').order_by('-entry_date', '-id')


def dashboard_stats():
    outstanding = CreditSale.objects.filter(status__in=[CreditSale.ACTIVE, CreditSale.OVERDUE]).aggregate(
        total=Sum('remaining_balance'))['total'] or ZERO
    paid = LedgerEntry.objects.filter(credit__gt=0).aggregate(total=Sum('credit'))['total'] or ZERO
    sales_by_status = CreditSale.objects.values('status').annotate(
        count=Count('id'), total=Sum('remaining_balance')).order_by('status')
    return {
        'total_sales': CreditSale.objects.count(),
        'total_outstanding': outstanding,
        'total_paid': paid,
        'recent_sales': CreditSale.objects.select_related('customer').order_by('-sale_date')[:10],
        'recent_payments': all_payments()[:10],
        'sales_by_status': sales_by_status,
    }


def customers_summary():
    """Per-customer credit summary for staff-facing directories."""
    from accounts.services import list_customers

    results = []
    for customer in list_customers():
        sales = list(CreditSale.objects.filter(customer=customer))
        if not sales:
            continue
        total_credit = sum((s.credit_price for s in sales), ZERO)
        total_remaining = sum((s.remaining_balance for s in sales), ZERO)
        total_paid = customer_payments(customer).aggregate(total=Sum('credit'))['total'] or ZERO
        results.append({
            'customer': customer,
            'sales_count': len(sales),
            'total_credit': total_credit,
            'total_remaining': total_remaining,
            'total_paid': total_paid,
        })
    results.sort(key=lambda r: r['total_remaining'], reverse=True)
    return results


def customer_detail_context(customer):
    sales = CreditSale.objects.filter(customer=customer).select_related('motorcycle').order_by('-sale_date')
    payments = customer_payments(customer)
    total_credit = sales.aggregate(total=Sum('credit_price'))['total'] or ZERO
    total_remaining = sales.aggregate(total=Sum('remaining_balance'))['total'] or ZERO
    total_paid = payments.aggregate(total=Sum('credit'))['total'] or ZERO
    return {
        'sales': sales,
        'payments': payments,
        'ledger': customer_ledger(customer),
        'total_credit': total_credit,
        'total_remaining': total_remaining,
        'total_paid': total_paid,
    }
