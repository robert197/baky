from pathlib import Path

import environ
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
)
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(env_file)

# Core
SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# Apps
DJANGO_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "django_extensions",
    "django_htmx",
    "storages",
    "django_q",
    "encrypted_model_fields",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.apartments",
    "apps.inspections",
    "apps.reports",
    "apps.public",
    "apps.dashboard",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# Middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "baky.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "baky.wsgi.application"

# Database
DATABASES = {
    "default": env.db("DATABASE_URL", default="sqlite:///db.sqlite3"),
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Auth
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/accounts/redirect/"
LOGOUT_REDIRECT_URL = "/"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "de"
TIME_ZONE = "Europe/Vienna"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media files
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Django-Q2 — retries are handled by retry > timeout (re-queues timed-out tasks).
# Retry limiting is enforced in baky.tasks.on_task_error via attempt_count.
Q_CLUSTER = {
    "name": "baky",
    "workers": 2,
    "recycle": 500,
    "timeout": 120,
    "retry": 180,
    "queue_limit": 50,
    "bulk": 10,
    "orm": "default",
}

# Email
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "BAKY <noreply@baky.at>"

# Google Maps — this key is exposed client-side; restrict it to Places API + your domains in Google Cloud Console
GOOGLE_MAPS_API_KEY = env("GOOGLE_MAPS_API_KEY", default="")

# Encrypted fields — FIELD_ENCRYPTION_KEY must be set in environment or overridden in local/production settings

# Django Unfold Admin
UNFOLD = {
    "SITE_TITLE": "BAKY Admin",
    "SITE_HEADER": "BAKY Admin",
    "SITE_SYMBOL": "apartment",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "DASHBOARD_CALLBACK": "baky.admin_dashboard.dashboard_callback",
    "SIDEBAR": {
        "show_search": True,
        "navigation": [
            {
                "title": _("Dashboard"),
                "items": [
                    {
                        "title": _("Dashboard"),
                        "icon": "dashboard",
                        "link": reverse_lazy("admin:index"),
                    },
                ],
            },
            {
                "title": _("Benutzer"),
                "items": [
                    {
                        "title": _("Benutzer"),
                        "icon": "people",
                        "link": reverse_lazy("admin:accounts_user_changelist"),
                    },
                    {
                        "title": _("Abonnements"),
                        "icon": "credit_card",
                        "link": reverse_lazy("admin:accounts_subscription_changelist"),
                    },
                ],
            },
            {
                "title": _("Wohnungen"),
                "items": [
                    {
                        "title": _("Wohnungen"),
                        "icon": "home",
                        "link": reverse_lazy("admin:apartments_apartment_changelist"),
                    },
                    {
                        "title": _("Checklisten"),
                        "icon": "checklist",
                        "link": reverse_lazy("admin:apartments_checklisttemplate_changelist"),
                    },
                ],
            },
            {
                "title": _("Inspektionen"),
                "items": [
                    {
                        "title": _("Inspektionen"),
                        "icon": "assignment",
                        "link": reverse_lazy("admin:inspections_inspection_changelist"),
                    },
                    {
                        "title": _("Prüfpunkte"),
                        "icon": "fact_check",
                        "link": reverse_lazy("admin:inspections_inspectionitem_changelist"),
                    },
                    {
                        "title": _("Fotos"),
                        "icon": "photo_camera",
                        "link": reverse_lazy("admin:inspections_photo_changelist"),
                    },
                ],
            },
        ],
    },
}
