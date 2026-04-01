from django.urls import path

from . import views

app_name = "public"

urlpatterns = [
    path("", views.home, name="home"),
    path("preise/", views.pricing, name="pricing"),
    path("impressum/", views.impressum, name="impressum"),
    path("datenschutz/", views.datenschutz, name="datenschutz"),
    path("agb/", views.agb, name="agb"),
]
