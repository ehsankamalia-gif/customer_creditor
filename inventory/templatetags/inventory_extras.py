from django import template

from inventory.models import Motorcycle

register = template.Library()

# Maps each stock status to a Bootstrap badge class, so every template
# renders status consistently instead of repeating an if/elif chain.
_STATUS_BADGE_CLASSES = {
    Motorcycle.AVAILABLE: 'bg-success',
    Motorcycle.RESERVED: 'bg-warning text-dark',
    Motorcycle.SOLD: 'bg-secondary',
    Motorcycle.IN_TRANSIT: 'bg-info text-dark',
    Motorcycle.DAMAGED: 'bg-danger',
}


@register.filter
def status_badge_class(status):
    return _STATUS_BADGE_CLASSES.get(status, 'bg-secondary')
