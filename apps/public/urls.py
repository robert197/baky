from django.urls import path

from . import views

app_name = "public"

urlpatterns = [
    path("", views.home, name="home"),
    path("preise/", views.pricing, name="pricing"),
]
