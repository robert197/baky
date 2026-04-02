from django.urls import path

from apps.dashboard import views as dashboard_views

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("redirect/", views.login_redirect, name="login-redirect"),
    path("signup/", views.signup, name="signup"),
    path("verify/<uuid:token>/", views.verify_email, name="verify-email"),
    path("onboarding/apartment/", views.onboarding_apartment, name="onboarding-apartment"),
    path("onboarding/checklist/", views.onboarding_checklist, name="onboarding-checklist"),
    path("onboarding/plan/", views.onboarding_plan, name="onboarding-plan"),
    path("onboarding/confirmation/", views.onboarding_confirmation, name="onboarding-confirmation"),
    path("password-reset/", views.PasswordResetView.as_view(), name="password-reset"),
    path("password-reset/done/", views.PasswordResetDoneView.as_view(), name="password-reset-done"),
    path(
        "password-reset/<uidb64>/<token>/",
        views.PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path("password-reset/complete/", views.PasswordResetCompleteView.as_view(), name="password-reset-complete"),
    path("delete-cancel/", dashboard_views.account_delete_cancel, name="account-delete-cancel"),
]
