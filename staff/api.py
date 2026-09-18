import json
from functools import wraps

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from accounts import services


def staff_permission_required_json(perm):
    """Requires is_staff AND the given permission; returns JSON 401/403 instead of redirecting."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({'detail': 'Authentication required.'}, status=401)
            if not (request.user.is_staff and request.user.has_perm(perm)):
                return JsonResponse({'detail': 'Permission denied.'}, status=403)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def superuser_required_json(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'detail': 'Authentication required.'}, status=401)
        if not request.user.is_superuser:
            return JsonResponse({'detail': 'Permission denied.'}, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper


@staff_permission_required_json('accounts.view_user')
@require_http_methods(['GET'])
def user_list(request):
    users = services.list_manageable_users()
    return JsonResponse({'users': [services.serialize_user(u) for u in users]})


@superuser_required_json
@require_http_methods(['GET', 'POST'])
def user_permissions(request, pk):
    target = services.get_manageable_user(pk)

    if request.method == 'POST':
        payload = json.loads(request.body or '{}')
        services.set_user_permissions(target, payload.get('permission_ids', []))
        return JsonResponse({'status': 'ok'})

    available = services.assignable_permissions()
    return JsonResponse({
        'available': [services.serialize_permission(p) for p in available],
        'assigned_ids': services.get_user_permission_ids(target),
    })


@superuser_required_json
@require_http_methods(['POST'])
def user_role(request, pk):
    target = services.get_manageable_user(pk)
    payload = json.loads(request.body or '{}')
    services.set_staff_status(target, bool(payload.get('is_staff')))
    return JsonResponse({'status': 'ok', 'user': services.serialize_user(target)})
