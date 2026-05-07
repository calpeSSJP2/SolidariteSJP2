# accounts/utils/rbac.py    RBAC stands for Role-Based Access Control.
from django.contrib.auth.decorators import user_passes_test

def has_role(user, role):
    return user.is_authenticated and user.roles.filter(name=role).exists()


def has_any_role(user, roles):
    return user.is_authenticated and user.roles.filter(name__in=roles).exists()


def get_user_roles(user):
    if not user.is_authenticated:
        return set()
    return set(user.roles.values_list("name", flat=True))


# -------------------------
# SESSION-BASED (ACTIVE ROLE)
# -------------------------

def get_active_role(request):
    return request.session.get("active_role")


def has_active_role(request, *roles):
    active_role = get_active_role(request)
    return active_role in roles


def get_active_mode(request):
    return request.session.get("active_mode")


def get_effective_role(request):
    """
    Future-proof alias (in case you later add fallback logic)
    """
    return get_active_role(request)


##Add decorators for ACTIVE ROLE.

from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required


def active_roles_required(*roles):

    def decorator(view_func):

        @login_required
        def _wrapped_view(request, *args, **kwargs):

            active_role = request.session.get("active_role")

            if active_role not in roles:
                return HttpResponseForbidden("Permission denied!Contact +250788624565")

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator