from .base import *  # noqa: F401,F403

DEBUG = True
SECRET_KEY = env("SECRET_KEY", default="django-insecure-dev-only-key-not-for-production")  # noqa: F405
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "0.0.0.0"])  # noqa: F405

# Debug Toolbar
INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405
INTERNAL_IPS = ["127.0.0.1", "0.0.0.0"]

# Console email
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
