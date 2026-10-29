"""Document file storage: write-once, private, on the server disk (S3 pluggable).

Files are only reachable through the authenticated API: the storage exposes no URL and
Django defines no MEDIA_URL. All keys are built server-side from UUIDs (never from a
user-supplied file name); keys escaping the root, or crossing a symlink, are refused.

Filesystem writes are atomic and write-once: the content goes to a temporary file in the
destination directory, is fsync-ed, then hard-linked to its final name (``os.link`` fails if
the key exists, so nothing is ever overwritten) and the temporary name is removed.
"""

import contextlib
import hashlib
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, Storage, storages

from apps.core.exceptions import RegleMetierError
from config.documents_settings import (
    FILESYSTEM as FILESYSTEM,
)
from config.documents_settings import (
    S3 as S3,
)
from config.documents_settings import (
    S3_VARIABLES as S3_VARIABLES,
)
from config.documents_settings import (
    configuration_stockage as configuration_stockage,
)

_MO = 1024 * 1024
_TYPE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_EMPREINTE_RE = re.compile(r"^[0-9a-f]{12,128}$")


class FichierExistantError(FileExistsError):
    """A stored file is never rewritten: its key already exists."""


class EspaceInsuffisantError(RegleMetierError):
    """Not enough free disk space on the documents server."""

    def __init__(self) -> None:
        super().__init__(
            "Espace disque insuffisant sur le serveur de documents : contactez l'administrateur."
        )


class StockageIndisponibleError(RegleMetierError):
    """The documents folder could not be written (permissions, I/O error, ...)."""

    def __init__(self) -> None:
        super().__init__(
            "Le serveur de documents est indisponible : réessayez ou contactez l'administrateur."
        )


class StockageEcritureUnique(FileSystemStorage):
    """Filesystem storage that never overwrites, renames or deletes, with private modes."""

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

    def delete(self, name: str) -> None:
        raise NotImplementedError("Suppression interdite : les fichiers sont à écriture unique.")


def stockage_documents() -> Storage:
    """Storage callable usable as ``FileField(storage=...)``."""
    return storages["documents"]


def cle_gabarit(type_document: str, version: int, empreinte: str) -> str:
    type_document = type_document.lower()  # registry codes may be upper case; keys never are
    if (
        not _TYPE_RE.match(type_document)
        or not isinstance(version, int)
        or version < 0
        or not _EMPREINTE_RE.match(empreinte)
    ):
        raise ValueError("Clé de gabarit invalide.")
    return f"gabarits/{type_document}/{version:03d}-{empreinte[:12]}.docx"


def cle_version(document_id: UUID, numero_version: int, extension: Literal["docx", "pdf"]) -> str:
    if (
        not isinstance(document_id, UUID)
        or not isinstance(numero_version, int)
        or numero_version < 1
        or extension not in ("docx", "pdf")
    ):
        raise ValueError("Clé de version invalide.")
    return f"versions/{document_id}/v{numero_version:03d}.{extension}"


def _min_libre_octets() -> int:
    return int(settings.DOCUMENTS_ESPACE_MIN_LIBRE_MO) * _MO


def _dossier_existant(chemin: Path) -> Path:
    while not chemin.exists() and chemin != chemin.parent:
        chemin = chemin.parent
    return chemin


def _chemin_sur(stockage: FileSystemStorage, cle: str) -> Path:
    """Absolute path of ``cle`` under the root; refuses traversal and symlink components."""
    cible = Path(stockage.path(cle))  # safe_join: raises SuspiciousFileOperation on "../"
    racine = Path(stockage.location)
    courant = racine
    for partie in cible.relative_to(racine).parts:
        courant = courant / partie
        if courant.is_symlink():
            raise SuspiciousFileOperation(f"Lien symbolique refusé dans la clé : {cle}")
    return cible


def _fsync_dossier(dossier: Path) -> None:
    if os.name == "nt":  # directories cannot be opened on Windows
        return
    fd = os.open(dossier, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _ecrire_fichier(stockage: FileSystemStorage, cle: str, contenu: bytes) -> str:
    """Write atomically and return the SHA-256 (hex) computed while writing."""
    final = _chemin_sur(stockage, cle)
    libre = shutil.disk_usage(_dossier_existant(Path(stockage.location))).free
    if libre - len(contenu) < _min_libre_octets():
        raise EspaceInsuffisantError
    dossier = final.parent
    temporaire: str | None = None
    try:
        dossier.mkdir(
            parents=True, exist_ok=True, mode=stockage.directory_permissions_mode or 0o750
        )
        _chemin_sur(stockage, cle)  # re-check once the directories exist
        fd, temporaire = tempfile.mkstemp(dir=dossier, prefix=".tmp-")
        empreinte = hashlib.sha256()
        with os.fdopen(fd, "wb") as fichier:
            for debut in range(0, len(contenu), _MO):
                morceau = contenu[debut : debut + _MO]
                empreinte.update(morceau)
                fichier.write(morceau)
            fichier.flush()
            os.fsync(fichier.fileno())
        os.chmod(temporaire, stockage.file_permissions_mode or 0o640)
        try:
            os.link(temporaire, final)  # atomic; fails if the key exists: never overwrites
        except FileExistsError as exc:
            raise FichierExistantError(f"La clé de stockage existe déjà : {cle}") from exc
        _fsync_dossier(dossier)
    except (FichierExistantError, SuspiciousFileOperation, EspaceInsuffisantError):
        raise
    except OSError as exc:
        raise StockageIndisponibleError from exc
    finally:
        if temporaire is not None:
            with contextlib.suppress(OSError):
                os.unlink(temporaire)
    return empreinte.hexdigest()


def ecrire_avec_empreinte(cle: str, contenu: bytes) -> tuple[str, str]:
    """Store ``contenu`` under ``cle`` (write-once); return ``(key, sha256 hex)``."""
    stockage = stockage_documents()
    if isinstance(stockage, FileSystemStorage):
        return cle, _ecrire_fichier(stockage, cle, contenu)
    if stockage.exists(cle):
        raise FichierExistantError(f"La clé de stockage existe déjà : {cle}")
    nom = stockage.save(cle, ContentFile(contenu))
    if nom != cle:  # never accept a silent rename
        raise FichierExistantError(f"La clé de stockage existe déjà : {cle}")
    return cle, hashlib.sha256(contenu).hexdigest()


def ecrire(cle: str, contenu: bytes) -> str:
    """Store ``contenu`` under ``cle`` (write-once) and return the stored key."""
    return ecrire_avec_empreinte(cle, contenu)[0]


def lire(cle: str) -> bytes:
    stockage = stockage_documents()
    if isinstance(stockage, FileSystemStorage):
        _chemin_sur(stockage, cle)
    with stockage.open(cle, "rb") as fichier:
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
