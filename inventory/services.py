"""Public API of the inventory module.

Other modules (e.g. credit) must go through these functions instead of
importing inventory.models and querying Motorcycle/ProductModel/Supplier/
StockLocation directly.
"""
from django.db.models import Count, Q, Sum
from django.utils import timezone

from .models import Motorcycle, ProductModel, StockLocation, Supplier

# Only these columns may be used to sort the inventory list - an explicit
# allow-list so a stray/unknown ?sort= query param can't be used to sort by
# an arbitrary (and possibly sensitive) column.
SORTABLE_FIELDS = {
    'chassis_number', '-chassis_number',
    'purchase_date', '-purchase_date',
    'selling_price', '-selling_price',
    'year', '-year',
    'status', '-status',
}


def list_product_models():
    return ProductModel.objects.all()


def list_suppliers():
    return Supplier.objects.all()


def list_locations():
    return StockLocation.objects.all()


def list_colors_in_use():
    """Distinct colors currently in stock, for the list page's filter dropdown."""
    return (
        Motorcycle.objects.filter(is_active=True).exclude(color='')
        .values_list('color', flat=True).distinct().order_by('color')
    )


def list_in_stock_motorcycles():
    """Units a new sale can actually be made against."""
    return Motorcycle.objects.filter(
        status=Motorcycle.AVAILABLE, is_active=True,
    ).select_related('product_model')


def list_all_motorcycles(include_archived=False):
    qs = Motorcycle.objects.select_related('product_model', 'purchase_supplier', 'location')
    if not include_archived:
        qs = qs.filter(is_active=True)
    return qs


def search_motorcycles(*, query=None, status=None, product_model_id=None, color=None,
                        location_id=None, ordering=None, include_archived=False):
    """Server-side search/filter behind the inventory list page.

    Filtering happens in the database, not in the browser, so the page
    stays fast no matter how large the inventory grows.
    """
    qs = list_all_motorcycles(include_archived=include_archived)

    if query:
        qs = qs.filter(
            Q(chassis_number__icontains=query)
            | Q(engine_number__icontains=query)
            | Q(product_model__model_name__icontains=query)
            | Q(color__icontains=query)
            | Q(purchase_reference__icontains=query)
        )
    if status:
        qs = qs.filter(status=status)
    if product_model_id:
        qs = qs.filter(product_model_id=product_model_id)
    if color:
        qs = qs.filter(color__iexact=color)
    if location_id:
        qs = qs.filter(location_id=location_id)
    if ordering in SORTABLE_FIELDS:
        qs = qs.order_by(ordering, 'id')

    return qs


def get_motorcycle(pk):
    return Motorcycle.objects.select_related('product_model', 'purchase_supplier', 'location').get(pk=pk)


def summary_stats():
    """Aggregate counts and values for the inventory dashboard."""
    active = Motorcycle.objects.filter(is_active=True)
    counts_by_status = dict(active.values_list('status').annotate(count=Count('id')))
    unsold = active.exclude(status=Motorcycle.SOLD)

    return {
        'total': active.count(),
        'available': counts_by_status.get(Motorcycle.AVAILABLE, 0),
        'reserved': counts_by_status.get(Motorcycle.RESERVED, 0),
        'sold': counts_by_status.get(Motorcycle.SOLD, 0),
        'in_transit': counts_by_status.get(Motorcycle.IN_TRANSIT, 0),
        'damaged': counts_by_status.get(Motorcycle.DAMAGED, 0),
        # "Stock value" = what's still tied up in unsold inventory at cost;
        # "potential sales value" = what it would bring in if sold at the
        # listed price. Sold units are excluded from both - their value is
        # realized, not held in stock.
        'stock_value': unsold.aggregate(total=Sum('purchase_price'))['total'] or 0,
        'potential_sales_value': unsold.aggregate(total=Sum('selling_price'))['total'] or 0,
    }


def mark_sold(motorcycle):
    """Called by other modules (e.g. credit) when a sale is finalized."""
    change_status(motorcycle, Motorcycle.SOLD)
    motorcycle.date_sold = timezone.localdate()
    motorcycle.save(update_fields=['date_sold'])


def change_status(motorcycle, new_status):
    """Move a unit to any status except out of SOLD.

    A sold unit can only come back to stock through return_to_stock() - a
    separate, deliberate operation - never through this general-purpose
    setter. That keeps a sale from being silently undone by someone picking
    a different value in a status dropdown.
    """
    if motorcycle.status == Motorcycle.SOLD and new_status != Motorcycle.SOLD:
        raise ValueError('A sold motorcycle can only be returned to stock via return_to_stock().')
    motorcycle.status = new_status
    motorcycle.save(update_fields=['status'])


def return_to_stock(motorcycle):
    """Explicitly reverses a sale (e.g. the unit was returned by the buyer)."""
    motorcycle.status = Motorcycle.AVAILABLE
    motorcycle.date_sold = None
    motorcycle.save(update_fields=['status', 'date_sold'])


def archive_motorcycle(motorcycle):
    """Soft delete: hides the unit from the active list without erasing it."""
    motorcycle.is_active = False
    motorcycle.save(update_fields=['is_active'])


def restore_motorcycle(motorcycle):
    motorcycle.is_active = True
    motorcycle.save(update_fields=['is_active'])
