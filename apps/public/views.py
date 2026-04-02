import logging

from django.db import connection
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


def home(request: HttpRequest) -> HttpResponse:
    return render(request, "public/home.html")


def pricing(request: HttpRequest) -> HttpResponse:
    return render(request, "public/pricing.html")


def impressum(request: HttpRequest) -> HttpResponse:
    return render(request, "public/impressum.html")


def datenschutz(request: HttpRequest) -> HttpResponse:
    return render(request, "public/datenschutz.html")


def agb(request: HttpRequest) -> HttpResponse:
    return render(request, "public/agb.html")


@require_GET
def health_check(request: HttpRequest) -> JsonResponse:
    """Lightweight health check for Docker/LB probes."""
    checks = {"status": "ok", "version": "1.0.0"}
    status_code = 200

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        checks["status"] = "error"
        checks["database"] = "unreachable"
        status_code = 503
        logger.error("Health check failed: database unreachable", exc_info=True)

    return JsonResponse(checks, status=status_code)
