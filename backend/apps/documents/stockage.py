"""Document file storage: write-once, private, on the server disk (S3 pluggable).

Files are only reachable through the authenticated API: the storage exposes no URL and
Django defines no MEDIA_URL. All keys are built server-side from UUIDs (never from a
user-supplied file name); Django's storage layer rejects any key escaping the root.
"""

import os
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, Storage, storages

from apps.core.exceptions import RegleMetierError

FILESYSTEM = "filesystem"
S3 = "s3"
_MO = 1024 * 1024

S3_VARIABLES = (
    "DOCUMENTS_S3_BUCKET",
    "DOCUMENTS_S3_ENDPOINT_URL",
    "DOCUMENTS_S3_ACCESS_KEY",
    "DOCUMENTS_S3_SECRET_KEY",
)


class FichierExistantError(FileExistsError):
    """A stored file is never rewritten: its key already exists."""


class EspaceInsuffisantError(RegleMetierError):
    """Not enough free disk space on the documents server."""

    def __init__(self) -> None:
        super().__init__(
            "Espace disque insuffisant sur le serveur de documents : contactez l'administrateur."
        )


class StockageEcritureUnique(FileSystemStorage):
    """Filesystem storage that never overwrites nor renames, with private permissions."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("file_permissions_mode", 0o640)
        kwargs.setdefault("directory_permissions_mode", 0o750)
        super().__init__(*args, **kwargs)

    def get_available_name(self, name: str, max_length: int | None = None) -> str:
        if self.exists(name):
            raise FichierExistantError(f"La clé de stockage existe déjà : {name}")
        return super().get_available_name(name, max_length)

    def url(self, name: str | None) -> str:
        raise NotImplementedError("Aucune URL publique : téléchargez par l'API.")


def configuration_stockage(env: Mapping[str, str]) -> dict[str, Any]:
    """Return the ``STORAGES["documents"]`` entry for the given environment mapping."""
    if env.get("DOCUMENTS_STORAGE", FILESYSTEM) == S3:
        return {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": env.get("DOCUMENTS_S3_BUCKET", ""),
                "endpoint_url": env.get("DOCUMENTS_S3_ENDPOINT_URL", ""),
                "access_key": env.get("DOCUMENTS_S3_ACCESS_KEY", ""),
                "secret_key": env.get("DOCUMENTS_S3_SECRET_KEY", ""),
                "file_overwrite": False,
                "default_acl": None,
                "querystring_auth": True,
            },
        }
    return {
        "BACKEND": "apps.documents.stockage.StockageEcritureUnique",
        "OPTIONS": {"location": env.get("DOCUMENTS_ROOT", "")},
    }


def stockage_documents() -> Storage:
    """Storage callable usable as ``FileField(storage=...)``."""
    return storages["documents"]


def cle_gabarit(type_document: str, version: int, empreinte: str) -> str:
    return f"gabarits/{type_document}/{version:03d}-{empreinte[:12]}.docx"


def cle_version(document_id: UUID, numero_version: int, extension: Literal["docx", "pdf"]) -> str:
    return f"versions/{document_id}/v{numero_version:03d}.{extension}"


def _min_libre_octets() -> int:
    return int(settings.DOCUMENTS_ESPACE_MIN_LIBRE_MO) * _MO


def _dossier_existant(chemin: Path) -> Path:
    while not chemin.exists() and chemin != chemin.parent:
        chemin = chemin.parent
    return chemin


def ecrire(cle: str, contenu: bytes) -> str:
    """Store ``contenu`` under ``cle`` (write-once) and return the stored key."""
    stockage = stockage_documents()
    if isinstance(stockage, FileSystemStorage):
        libre = shutil.disk_usage(_dossier_existant(Path(stockage.location))).free
        if libre - len(contenu) < _min_libre_octets():
            raise EspaceInsuffisantError
    return stockage.save(cle, ContentFile(contenu))


def lire(cle: str) -> bytes:
    with stockage_documents().open(cle, "rb") as fichier:
        contenu: bytes = fichier.read()
    return contenu


def etat_stockage() -> Literal["ok", "faible", "indisponible"]:
    """Health of the documents storage (never raises)."""
    stockage = stockage_documents()
    if not isinstance(stockage, FileSystemStorage):
        return "ok"
    racine = Path(stockage.location)
    try:
        if not racine.is_dir() or not os.access(racine, os.W_OK):
            return "indisponible"
        libre = shutil.disk_usage(racine).free
    except OSError:
        return "indisponible"
    return "faible" if libre < _min_libre_octets() else "ok"
