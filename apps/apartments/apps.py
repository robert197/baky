from django.apps import AppConfig


class ApartmentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.apartments"
    verbose_name = "Apartments"

    def ready(self):
        import apps.apartments.signals  # noqa: F401
