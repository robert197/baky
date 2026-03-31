from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("redirect/", views.login_redirect, name="login-redirect"),
    path("password-reset/", views.PasswordResetView.as_view(), name="password-reset"),
    path("password-reset/done/", views.PasswordResetDoneView.as_view(), name="password-reset-done"),
    path(
        "password-reset/<uidb64>/<token>/",
        views.PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path("password-reset/complete/", views.PasswordResetCompleteView.as_view(), name="password-reset-complete"),
]
