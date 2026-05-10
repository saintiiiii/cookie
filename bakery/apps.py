from django.apps import AppConfig


class BakeryConfig(AppConfig):
    name = "bakery"

    def ready(self):
        import bakery.signals  # noqa: F401
