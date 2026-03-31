from django.contrib.auth import views as auth_views
from django.shortcuts import redirect

from .forms import BakyPasswordResetForm, BakySetPasswordForm, LoginForm


def login_redirect(request):
    """Redirect authenticated users to the correct dashboard based on their role."""
    user = request.user
    if not user.is_authenticated:
        return redirect("accounts:login")
    if user.role == "inspector":
        return redirect("inspections:index")
    if user.role == "admin":
        return redirect("admin:index")
    # Default: owner
    return redirect("dashboard:index")


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    form_class = LoginForm
    redirect_authenticated_user = True

    def get_redirect_url(self):
        """Override to redirect based on role when no 'next' parameter."""
        url = super().get_redirect_url()
        if url:
            return url
        return self.request.build_absolute_uri("/accounts/redirect/")


class LogoutView(auth_views.LogoutView):
    next_page = "/"


class PasswordResetView(auth_views.PasswordResetView):
    template_name = "accounts/password_reset.html"
    email_template_name = "accounts/password_reset_email.html"
    subject_template_name = "accounts/password_reset_subject.txt"
    form_class = BakyPasswordResetForm
    success_url = "/accounts/password-reset/done/"


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    form_class = BakySetPasswordForm
    success_url = "/accounts/password-reset/complete/"


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"
