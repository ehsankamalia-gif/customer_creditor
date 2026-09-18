from django.conf import settings
from django.db import models
from django.utils import timezone


class CreditSale(models.Model):
    """A single item (usually a motorcycle) sold to a customer on credit."""

    ACTIVE = 'ACTIVE'
    CLOSED = 'CLOSED'
    OVERDUE = 'OVERDUE'
    STATUS_CHOICES = [
        (ACTIVE, 'Active'),
        (CLOSED, 'Closed'),
        (OVERDUE, 'Overdue'),
    ]

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='credit_sales',
    )
    motorcycle = models.ForeignKey(
        'inventory.Motorcycle', on_delete=models.PROTECT, related_name='credit_sales',
        null=True, blank=True,
        help_text='Leave blank for a credit sale that is not a motorcycle.',
    )
    item_description = models.CharField(
        max_length=255, blank=True,
        help_text='Used when no motorcycle is linked.',
    )
    cash_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit_price = models.DecimalField(max_digits=12, decimal_places=2)
    down_payment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    down_payment_method = models.CharField(max_length=50, default='Cash')
    duration_months = models.PositiveIntegerField(default=12)
    installment_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sale_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(null=True, blank=True)
    remaining_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ACTIVE)
    notes = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sale_date', '-id']

    def __str__(self):
        return f'{self.display_id} - {self.customer}'

    @property
    def display_id(self):
        return f'CS-{self.pk:06d}' if self.pk else 'CS-(unsaved)'

    @property
    def item_label(self):
        if self.motorcycle_id:
            return str(self.motorcycle)
        return self.item_description or 'Item'


class Installment(models.Model):
    """One scheduled instalment of a credit sale's repayment plan."""

    PENDING = 'PENDING'
    PARTIAL = 'PARTIAL'
    PAID = 'PAID'
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (PARTIAL, 'Partial'),
        (PAID, 'Paid'),
    ]

    sale = models.ForeignKey(CreditSale, on_delete=models.CASCADE, related_name='installments')
    installment_no = models.PositiveIntegerField()
    due_date = models.DateField(null=True, blank=True)
    amount_due = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_date = models.DateField(null=True, blank=True)
    payment_method = models.CharField(max_length=50, blank=True)
    reference_no = models.CharField(max_length=50, blank=True)
    notes = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sale', 'installment_no']
        unique_together = ('sale', 'installment_no')

    def __str__(self):
        return f'{self.sale.display_id} #{self.installment_no}'

    @property
    def balance_due(self):
        return self.amount_due - self.amount_paid


class LedgerEntry(models.Model):
    """One line of a customer's running credit ledger (debit = owed, credit = paid)."""

    DEBIT = 'DEBIT'
    CREDIT = 'CREDIT'
    ENTRY_TYPE_CHOICES = [
        (DEBIT, 'Debit'),
        (CREDIT, 'Credit'),
    ]

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='ledger_entries',
    )
    sale = models.ForeignKey(
        CreditSale, on_delete=models.CASCADE, related_name='ledger_entries', null=True, blank=True,
    )
    installment = models.ForeignKey(
        Installment, on_delete=models.SET_NULL, related_name='ledger_entries', null=True, blank=True,
    )
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPE_CHOICES)
    description = models.CharField(max_length=500, blank=True)
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    entry_date = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['entry_date', 'id']

    def __str__(self):
        return f'{self.get_entry_type_display()} {self.debit or self.credit} - {self.customer}'
