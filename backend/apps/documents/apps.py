import importlib
import pkgutil

from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    name = "apps.documents"
    label = "documents"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # Document types register themselves on import: no need to edit this file.
        from . import generators

        for module in pkgutil.iter_modules(generators.__path__):
            importlib.import_module(f"{generators.__name__}.{module.name}")
