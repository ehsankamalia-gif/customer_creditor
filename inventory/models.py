from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class ProductModel(models.Model):
    """A motorcycle model/variant that the dealership stocks, e.g. 'CD 70'."""

    model_name = models.CharField(max_length=50, unique=True)
    make = models.CharField(max_length=50, default='Honda')
    engine_capacity = models.CharField(max_length=20, blank=True)
    pct_code = models.CharField(max_length=20, blank=True, verbose_name='PCT code')
    item_code = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ['model_name']

    def __str__(self):
        return self.model_name


class Supplier(models.Model):
    """A vendor the dealership buys motorcycles from."""

    name = models.CharField(max_length=100, unique=True)
    contact_person = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class StockLocation(models.Model):
    """A physical place a unit can sit: a showroom, warehouse or branch.

    A lookup table (not a free-text field) so location names stay
    consistent and new branches can be added without a code change.
    """

    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Motorcycle(models.Model):
    """A single physical unit in stock, identified by its chassis number."""

    AVAILABLE = 'AVAILABLE'
    RESERVED = 'RESERVED'
    SOLD = 'SOLD'
    IN_TRANSIT = 'IN_TRANSIT'
    DAMAGED = 'DAMAGED'
    STATUS_CHOICES = [
        (AVAILABLE, 'Available'),
        (RESERVED, 'Reserved'),
        (SOLD, 'Sold'),
        (IN_TRANSIT, 'In transit'),
        (DAMAGED, 'Damaged'),
    ]

    # Once a unit is sold, these fields describe a transaction that already
    # happened - they're removed from the edit form entirely rather than
    # just disabled, so history can't be rewritten by mistake.
    # See forms.MotorcycleEditForm.
    LOCKED_AFTER_SALE_FIELDS = (
        'chassis_number', 'engine_number', 'vin',
        'purchase_supplier', 'purchase_price', 'purchase_date', 'purchase_reference',
    )

    # --- Identification -----------------------------------------------
    product_model = models.ForeignKey(
        ProductModel, on_delete=models.PROTECT, related_name='motorcycles',
    )
    chassis_number = models.CharField(max_length=50, unique=True, db_index=True)
    engine_number = models.CharField(max_length=50, unique=True, db_index=True)
    vin = models.CharField(max_length=50, unique=True, null=True, blank=True, verbose_name='VIN')
    year = models.PositiveIntegerField(
        validators=[MinValueValidator(1980)],
        help_text='Manufacture year.',
    )
    color = models.CharField(max_length=30, blank=True, db_index=True)

    # --- Purchase / stock-in --------------------------------------------
    purchase_supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, null=True, blank=True, related_name='motorcycles',
    )
    purchase_price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)],
    )
    purchase_date = models.DateField(default=timezone.localdate, db_index=True)
    purchase_reference = models.CharField(
        max_length=100, blank=True,
        help_text="Supplier's purchase/delivery order number, e.g. from a manufacturer stock export.",
    )

    # --- Selling ----------------------------------------------------------
    selling_price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)],
    )

    # --- Stock --------------------------------------------------------------
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=AVAILABLE, db_index=True)
    location = models.ForeignKey(
        StockLocation, on_delete=models.PROTECT, null=True, blank=True, related_name='motorcycles',
    )
    date_sold = models.DateField(null=True, blank=True)

    # --- Additional info ----------------------------------------------------
    notes = models.TextField(blank=True)

    # --- Lifecycle / audit ----------------------------------------------------
    is_active = models.BooleanField(
        default=True,
        help_text='Archived units are hidden from the default list but never deleted.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'is_active']),
        ]

    def __str__(self):
        return f'{self.chassis_number} - {self.product_model.model_name}'

    @property
    def is_available(self):
        return self.status == self.AVAILABLE and self.is_active

    @property
    def is_locked(self):
        """True once a sale has happened - the edit form hides sale-defining fields."""
        return self.status == self.SOLD
