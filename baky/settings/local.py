from .base import *  # noqa: F401,F403

DEBUG = True
SECRET_KEY = env("SECRET_KEY", default="django-insecure-dev-only-key-not-for-production")  # noqa: F405
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "0.0.0.0"])  # noqa: F405

# Encrypted model fields — dev-only key (NOT for production)
FIELD_ENCRYPTION_KEY = env(  # noqa: F405
    "FIELD_ENCRYPTION_KEY",
    default="VqoBSMFYSOdCd8o0zDBDArfpQfhoYjLC2rBrqQyK8us=",
)

# Debug Toolbar
INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405
INTERNAL_IPS = ["127.0.0.1", "0.0.0.0"]

# Docker: add gateway IPs so debug toolbar works inside containers
import socket  # noqa: E402

_, _, ips = socket.gethostbyname_ex(socket.gethostname())
INTERNAL_IPS += [ip[: ip.rfind(".")] + ".1" for ip in ips]

# Email: use Mailpit SMTP when EMAIL_HOST is set (Docker), else console
EMAIL_HOST = env("EMAIL_HOST", default="")  # noqa: F405
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_PORT = env.int("EMAIL_PORT", default=1025)  # noqa: F405
    EMAIL_USE_TLS = False
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
