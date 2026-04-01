from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


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
