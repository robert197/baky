from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def home(request: HttpRequest) -> HttpResponse:
    return render(request, "public/home.html")


def pricing(request: HttpRequest) -> HttpResponse:
    return render(request, "public/pricing.html")
