from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import Http404


def role_required(role: str):
    """Decorator that requires the user to be logged in and have the specified role.

    Returns 404 (not 403) to prevent enumeration of resources.
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if request.user.role != role:
                raise Http404
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def owner_required(view_func):
    """Require authenticated user with Owner role."""
    return role_required("owner")(view_func)


def inspector_required(view_func):
    """Require authenticated user with Inspector role."""
    return role_required("inspector")(view_func)
