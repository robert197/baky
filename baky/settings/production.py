from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")  # noqa: F405
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")  # noqa: F405

# Encrypted fields
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY")  # noqa: F405

# Security
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_REDIRECT_EXEMPT = [r"^health/$"]

# Upload limits — inspector photos (HEIF) can be 5-15MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024

# Static files with Whitenoise
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# S3/R2 for media
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")  # noqa: F405
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")  # noqa: F405
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")  # noqa: F405
AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL")  # noqa: F405
AWS_S3_CUSTOM_DOMAIN = env("AWS_S3_CUSTOM_DOMAIN", default="")  # noqa: F405
AWS_DEFAULT_ACL = None
AWS_S3_FILE_OVERWRITE = False
AWS_S3_REGION_NAME = "eu-central-1"
AWS_QUERYSTRING_AUTH = True
AWS_QUERYSTRING_EXPIRE = 86400  # 24 hours

# Email via Resend (through django-anymail)
INSTALLED_APPS += ["anymail"]  # noqa: F405
EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"
ANYMAIL = {
    "RESEND_API_KEY": env("RESEND_API_KEY"),  # noqa: F405
}
SITE_URL = env("SITE_URL")  # noqa: F405

# Sentry
import sentry_sdk  # noqa: E402

sentry_sdk.init(
    dsn=env("SENTRY_DSN", default=""),  # noqa: F405
    release=env("GIT_SHA", default=None),  # noqa: F405
    environment=env("SENTRY_ENVIRONMENT", default="production"),  # noqa: F405
    traces_sample_rate=float(env("SENTRY_TRACES_SAMPLE_RATE", default="0.1")),  # noqa: F405
    send_default_pii=False,
)

# Structured JSON logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "baky": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
