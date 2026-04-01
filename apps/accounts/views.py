import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy

from .decorators import owner_required
from .forms import (
    ApartmentOnboardingForm,
    BakyPasswordResetForm,
    BakySetPasswordForm,
    LoginForm,
    PlanSelectionForm,
    SignupForm,
)
from .models import EmailVerificationToken, OnboardingProgress, Subscription, User


@login_required
def login_redirect(request):
    """Redirect authenticated users to the correct dashboard based on their role."""
    user = request.user
    if user.role == User.Role.INSPECTOR:
        return redirect("inspections:index")
    if user.role == User.Role.ADMIN:
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
        return reverse("accounts:login-redirect")


class LogoutView(auth_views.LogoutView):
    next_page = "/"


class PasswordResetView(auth_views.PasswordResetView):
    template_name = "accounts/password_reset.html"
    email_template_name = "accounts/password_reset_email.html"
    subject_template_name = "accounts/password_reset_subject.txt"
    form_class = BakyPasswordResetForm
    success_url = reverse_lazy("accounts:password-reset-done")


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    form_class = BakySetPasswordForm
    success_url = reverse_lazy("accounts:password-reset-complete")


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"


def signup(request):
    """Step 1: Account creation."""
    if request.user.is_authenticated:
        return redirect("accounts:login-redirect")

    plan = request.GET.get("plan", "")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                token = EmailVerificationToken.objects.create(user=user)
                OnboardingProgress.objects.create(
                    user=user,
                    selected_plan=request.POST.get("selected_plan", plan),
                )

            _send_verification_email(request, user, token)
            login(request, user)

            return redirect("accounts:onboarding-apartment")
    else:
        form = SignupForm()

    return render(request, "accounts/signup.html", {"form": form, "selected_plan": plan})


def verify_email(request, token):
    """Email verification callback."""
    verification = get_object_or_404(EmailVerificationToken, token=token)

    if verification.is_verified:
        messages.info(request, "Ihre E-Mail-Adresse wurde bereits bestätigt.")
    elif verification.is_expired:
        messages.error(request, "Dieser Bestätigungslink ist abgelaufen. Bitte fordern Sie einen neuen an.")
    else:
        verification.verify()
        messages.success(request, "Ihre E-Mail-Adresse wurde erfolgreich bestätigt.")

    if request.user.is_authenticated:
        return redirect("accounts:login-redirect")
    return redirect("accounts:login")


@owner_required
def onboarding_apartment(request):
    """Onboarding Step 2: Register first apartment."""
    onboarding = _get_or_create_onboarding(request.user)
    if onboarding.is_complete:
        return redirect("dashboard:index")

    if request.method == "POST":
        form = ApartmentOnboardingForm(request.POST)
        if form.is_valid():
            apartment = form.save(commit=False)
            apartment.owner = request.user
            apartment.save()

            onboarding.apartment = apartment
            onboarding.current_step = OnboardingProgress.Step.CHECKLIST
            onboarding.save(update_fields=["apartment", "current_step"])

            if request.headers.get("HX-Request"):
                return render(request, "accounts/_onboarding_checklist.html", _checklist_context(onboarding))
            return redirect("accounts:onboarding-checklist")
    else:
        form = ApartmentOnboardingForm()

    ctx = {
        "form": form,
        "onboarding": onboarding,
        "current_step": 1,
        "total_steps": 4,
        "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
    }
    if request.headers.get("HX-Request"):
        return render(request, "accounts/_onboarding_apartment.html", ctx)
    return render(request, "accounts/onboarding.html", {**ctx, "step_template": "accounts/_onboarding_apartment.html"})


@owner_required
def onboarding_checklist(request):
    """Onboarding Step 3: Customize checklist."""
    onboarding = _get_or_create_onboarding(request.user)
    if onboarding.is_complete:
        return redirect("dashboard:index")
    if not onboarding.apartment:
        return redirect("accounts:onboarding-apartment")
    if onboarding.current_step < OnboardingProgress.Step.CHECKLIST:
        return redirect("accounts:onboarding-apartment")

    checklist = onboarding.apartment.checklist_template

    if request.method == "POST":
        enabled_items = request.POST.getlist("enabled_items")
        custom_items_raw = request.POST.get("custom_items", "").strip()

        items = checklist.items
        updated_items = [item for item in items if item["label"] in enabled_items]

        if custom_items_raw:
            max_order = max((item["order"] for item in updated_items), default=0)
            for line in custom_items_raw.splitlines():
                line = line.strip()
                if line:
                    max_order += 1
                    updated_items.append(
                        {
                            "category": "Individuell",
                            "label": line,
                            "allowed_results": ["ok", "flagged"],
                            "order": max_order,
                        }
                    )

        checklist.items = updated_items
        checklist.save(update_fields=["items"])

        onboarding.current_step = OnboardingProgress.Step.PLAN
        onboarding.save(update_fields=["current_step"])

        if request.headers.get("HX-Request"):
            return render(request, "accounts/_onboarding_plan.html", _plan_context(onboarding))
        return redirect("accounts:onboarding-plan")

    ctx = _checklist_context(onboarding)
    if request.headers.get("HX-Request"):
        return render(request, "accounts/_onboarding_checklist.html", ctx)
    return render(request, "accounts/onboarding.html", {**ctx, "step_template": "accounts/_onboarding_checklist.html"})


@owner_required
def onboarding_plan(request):
    """Onboarding Step 4: Select subscription plan."""
    onboarding = _get_or_create_onboarding(request.user)
    if onboarding.is_complete:
        return redirect("dashboard:index")
    if not onboarding.apartment:
        return redirect("accounts:onboarding-apartment")
    if onboarding.current_step < OnboardingProgress.Step.PLAN:
        return redirect("accounts:onboarding-checklist")

    initial_plan = onboarding.selected_plan or "basis"

    if request.method == "POST":
        form = PlanSelectionForm(request.POST)
        if form.is_valid():
            selected_plan = form.cleaned_data["plan"]
            onboarding.selected_plan = selected_plan
            onboarding.current_step = OnboardingProgress.Step.CONFIRMATION
            onboarding.save(update_fields=["selected_plan", "current_step"])

            Subscription.objects.update_or_create(
                owner=request.user,
                defaults={
                    "plan": selected_plan,
                    "status": Subscription.Status.ACTIVE,
                    "started_at": datetime.date.today(),
                    "billing_cycle": Subscription.BillingCycle.MONTHLY,
                },
            )

            if request.headers.get("HX-Request"):
                return render(request, "accounts/_onboarding_confirmation.html", _confirmation_context(onboarding))
            return redirect("accounts:onboarding-confirmation")
    else:
        form = PlanSelectionForm(initial={"plan": initial_plan})

    ctx = _plan_context(onboarding, form)
    if request.headers.get("HX-Request"):
        return render(request, "accounts/_onboarding_plan.html", ctx)
    return render(request, "accounts/onboarding.html", {**ctx, "step_template": "accounts/_onboarding_plan.html"})


@owner_required
def onboarding_confirmation(request):
    """Onboarding Step 5: Confirmation and finish."""
    onboarding = _get_or_create_onboarding(request.user)
    if onboarding.is_complete:
        return redirect("dashboard:index")
    if not onboarding.apartment:
        return redirect("accounts:onboarding-apartment")
    if onboarding.current_step < OnboardingProgress.Step.CONFIRMATION:
        return redirect("accounts:onboarding-plan")

    if request.method == "POST":
        onboarding.is_complete = True
        onboarding.save(update_fields=["is_complete"])

        _send_welcome_email(request.user)
        messages.success(request, "Willkommen bei BAKY! Ihr Konto ist eingerichtet.")
        return redirect("dashboard:index")

    ctx = _confirmation_context(onboarding)
    if request.headers.get("HX-Request"):
        return render(request, "accounts/_onboarding_confirmation.html", ctx)
    return render(
        request, "accounts/onboarding.html", {**ctx, "step_template": "accounts/_onboarding_confirmation.html"}
    )


def _get_or_create_onboarding(user):
    onboarding, _ = OnboardingProgress.objects.get_or_create(user=user)
    return onboarding


def _checklist_context(onboarding):
    checklist = onboarding.apartment.checklist_template
    items_by_category = {}
    for item in checklist.items:
        items_by_category.setdefault(item["category"], []).append(item)
    return {
        "onboarding": onboarding,
        "checklist": checklist,
        "items_by_category": items_by_category,
        "current_step": 2,
        "total_steps": 4,
    }


def _plan_context(onboarding, form=None):
    if form is None:
        initial_plan = onboarding.selected_plan or "basis"
        form = PlanSelectionForm(initial={"plan": initial_plan})
    return {
        "onboarding": onboarding,
        "form": form,
        "current_step": 3,
        "total_steps": 4,
    }


def _confirmation_context(onboarding):
    plan_display = dict(Subscription.Plan.choices).get(onboarding.selected_plan, onboarding.selected_plan)
    return {
        "onboarding": onboarding,
        "apartment": onboarding.apartment,
        "plan_display": plan_display,
        "checklist_count": len(onboarding.apartment.checklist_template.items),
        "current_step": 4,
        "total_steps": 4,
    }


def _send_verification_email(request, user, token):
    verify_url = request.build_absolute_uri(reverse("accounts:verify-email", args=[token.token]))
    subject = "BAKY — E-Mail-Adresse bestätigen"
    message = render_to_string(
        "accounts/email_verification.txt",
        {"user": user, "verify_url": verify_url},
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])


def _send_welcome_email(user):
    subject = "Willkommen bei BAKY!"
    message = render_to_string("accounts/email_welcome.txt", {"user": user})
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
