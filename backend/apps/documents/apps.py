import importlib
import pkgutil
from pathlib import Path

from django.apps import AppConfig
from django.conf import settings


class DocumentsConfig(AppConfig):
    name = "apps.documents"
    label = "documents"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # Dev only (DOCUMENTS_CREER_DOSSIER): production never creates the folder, the health
        # endpoint reports it as unavailable instead.
        if settings.DOCUMENTS_CREER_DOSSIER and settings.DOCUMENTS_STORAGE == "filesystem":
            Path(settings.DOCUMENTS_ROOT).mkdir(parents=True, exist_ok=True)

        # Document types register themselves on import: no need to edit this file.
        from . import generators

        for module in pkgutil.iter_modules(generators.__path__):
            importlib.import_module(f"{generators.__name__}.{module.name}")
