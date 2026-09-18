from django.conf import settings
from django.db import models
from django.utils import timezone


class SpareLedgerTransaction(models.Model):
    """A single cash-in/cash-out entry in the spare parts cash ledger."""

    CREDIT = 'CREDIT'
    DEBIT = 'DEBIT'
    TRANS_TYPE_CHOICES = [
        (CREDIT, 'Credit (money in)'),
        (DEBIT, 'Debit (money out)'),
    ]

    BANK = 'BANK'
    CASH = 'CASH'
    CASH_TYPE_CHOICES = [
        (BANK, 'Bank'),
        (CASH, 'Cash'),
    ]

    timestamp = models.DateTimeField(default=timezone.now)
    trans_type = models.CharField(max_length=10, choices=TRANS_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference_number = models.CharField(max_length=50, blank=True)
    description = models.CharField(max_length=255, blank=True)
    cash_type = models.CharField(max_length=20, choices=CASH_TYPE_CHOICES, default=CASH)
    month_key = models.CharField(max_length=7, editable=False, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+',
    )

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.get_trans_type_display()} {self.amount} ({self.month_key})'

    def save(self, *args, **kwargs):
        self.month_key = timezone.localtime(self.timestamp).strftime('%Y-%m')
        super().save(*args, **kwargs)


class SpareLedgerMonthlyClose(models.Model):
    """A closed month's snapshot for the spare parts cash ledger."""

    month_key = models.CharField(max_length=7, unique=True)
    closed_at = models.DateTimeField(auto_now_add=True)
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_credits = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_debits = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    closing_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+',
    )

    class Meta:
        ordering = ['-month_key']

    def __str__(self):
        return f'{self.month_key} closing {self.closing_balance}'
