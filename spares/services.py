"""Public API of the spares module (the shop's spare-parts cash ledger)."""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import SpareLedgerMonthlyClose, SpareLedgerTransaction

ZERO = Decimal('0')


def record_transaction(*, trans_type, amount, cash_type, reference_number='', description='',
                        timestamp=None, created_by=None):
    return SpareLedgerTransaction.objects.create(
        trans_type=trans_type, amount=amount, cash_type=cash_type,
        reference_number=reference_number, description=description,
        timestamp=timestamp or timezone.now(), created_by=created_by,
    )


def list_transactions(month_key=None, trans_type=None):
    qs = SpareLedgerTransaction.objects.order_by('timestamp')
    if month_key:
        qs = qs.filter(month_key=month_key)
    if trans_type:
        qs = qs.filter(trans_type=trans_type)
    return qs


def transactions_with_running_balance(month_key=None, trans_type=None):
    """Transactions (optionally filtered) with a cumulative running balance."""
    running = ZERO
    rows = []
    for tx in list_transactions(month_key=month_key, trans_type=trans_type):
        running += tx.amount if tx.trans_type == SpareLedgerTransaction.CREDIT else -tx.amount
        rows.append({'transaction': tx, 'balance': running})
    return rows


def unique_months():
    return list(
        SpareLedgerTransaction.objects.order_by('month_key')
        .values_list('month_key', flat=True).distinct()
    )


def current_balance():
    totals = list_transactions()
    balance = ZERO
    for tx in totals:
        balance += tx.amount if tx.trans_type == SpareLedgerTransaction.CREDIT else -tx.amount
    return balance


def is_month_closed(month_key):
    return SpareLedgerMonthlyClose.objects.filter(month_key=month_key).exists()


def closed_months():
    return set(SpareLedgerMonthlyClose.objects.values_list('month_key', flat=True))


@transaction.atomic
def close_month(month_key, closed_by):
    """Snapshot a month's totals and carry the closing balance forward."""
    if is_month_closed(month_key):
        raise ValueError(f'{month_key} is already closed.')

    previous = SpareLedgerMonthlyClose.objects.order_by('-month_key').filter(month_key__lt=month_key).first()
    opening_balance = previous.closing_balance if previous else ZERO

    month_transactions = list_transactions(month_key=month_key)
    total_credits = sum(
        (tx.amount for tx in month_transactions if tx.trans_type == SpareLedgerTransaction.CREDIT), ZERO)
    total_debits = sum(
        (tx.amount for tx in month_transactions if tx.trans_type == SpareLedgerTransaction.DEBIT), ZERO)

    return SpareLedgerMonthlyClose.objects.create(
        month_key=month_key,
        opening_balance=opening_balance,
        total_credits=total_credits,
        total_debits=total_debits,
        closing_balance=opening_balance + total_credits - total_debits,
        closed_by=closed_by,
    )


def monthly_report():
    """Per-month breakdown by cash type, with running brought-forward balances."""
    stats = {}
    for tx in list_transactions():
        bucket = stats.setdefault(tx.month_key, {
            'bank_credit': ZERO, 'cash_credit': ZERO, 'bank_debit': ZERO, 'cash_debit': ZERO,
        })
        is_bank = tx.cash_type == SpareLedgerTransaction.BANK
        if tx.trans_type == SpareLedgerTransaction.CREDIT:
            bucket['bank_credit' if is_bank else 'cash_credit'] += tx.amount
        else:
            bucket['bank_debit' if is_bank else 'cash_debit'] += tx.amount

    report = []
    running = ZERO
    for month_key in sorted(stats):
        s = stats[month_key]
        total_credit = s['bank_credit'] + s['cash_credit']
        total_debit = s['bank_debit'] + s['cash_debit']
        closing = running + total_credit - total_debit
        report.append({
            'month_key': month_key,
            'brought_forward': running,
            'bank_credit': s['bank_credit'],
            'cash_credit': s['cash_credit'],
            'total_credit': total_credit,
            'bank_debit': s['bank_debit'],
            'cash_debit': s['cash_debit'],
            'total_debit': total_debit,
            'closing_balance': closing,
        })
        running = closing
    return report


def monthly_summary():
    """A simpler month-by-month view: credits in, debits out, running balance."""
    report = monthly_report()
    return [
        {
            'month_key': row['month_key'],
            'previous_balance': row['brought_forward'],
            'total_credit': row['total_credit'],
            'total_debit': row['total_debit'],
            'balance': row['closing_balance'],
        }
        for row in report
    ]
