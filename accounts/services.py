"""Public API of the accounts module.

Other modules (e.g. staff) must go through these functions instead of
importing accounts.models and querying User/Permission directly.
"""
from django.contrib.auth.models import Permission
from django.shortcuts import get_object_or_404

from .models import User

# Framework/internal permissions that aren't meaningful "features" for
# an admin to hand out to staff members.
EXCLUDED_APP_LABELS = {'admin', 'contenttypes', 'sessions'}
EXCLUDED_CODENAMES = {
    'add_group', 'change_group', 'delete_group', 'view_group',
    'add_permission', 'change_permission', 'delete_permission', 'view_permission',
}


def serialize_user(user):
    return {
        'id': user.id,
        'phone_number': user.phone_number,
        'full_name': user.full_name,
        'role': user.role,
        'is_active': user.is_active,
    }


def serialize_permission(permission):
    return {
        'id': permission.id,
        'label': permission.name,
        'codename': permission.codename,
        'app_label': permission.content_type.app_label,
        'model': permission.content_type.model,
    }


def list_manageable_users():
    """All non-admin users, e.g. for staff-facing directories/management screens."""
    return User.objects.filter(is_superuser=False).order_by('phone_number')


def list_customers():
    """Users with the 'customer' role, e.g. for other modules' customer pickers."""
    return User.objects.filter(is_staff=False, is_superuser=False).order_by('phone_number')


def get_manageable_user(user_id):
    """A single non-admin user, or 404. Admin accounts can't be targeted this way."""
    return get_object_or_404(User, pk=user_id, is_superuser=False)


def assignable_permissions():
    """Permissions an Admin is allowed to grant to a staff member."""
    return (
        Permission.objects
        .select_related('content_type')
        .exclude(content_type__app_label__in=EXCLUDED_APP_LABELS)
        .exclude(codename__in=EXCLUDED_CODENAMES)
        .order_by('content_type__app_label', 'content_type__model', 'codename')
    )


def get_user_permission_ids(user):
    return list(user.user_permissions.values_list('id', flat=True))


def set_user_permissions(user, permission_ids):
    valid_ids = set(assignable_permissions().values_list('id', flat=True))
    requested_ids = {int(i) for i in permission_ids}
    user.user_permissions.set(requested_ids & valid_ids)


def set_staff_status(user, is_staff):
    user.is_staff = is_staff
    if not is_staff:
        user.user_permissions.clear()
    user.save(update_fields=['is_staff'])
