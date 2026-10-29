"""Pure helpers for the documents settings (no application code, no Django app registry).

Imported by ``config.settings.*`` and re-exported by ``apps.documents.stockage``.
"""

import posixpath
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from django.core.exceptions import ImproperlyConfigured

FILESYSTEM = "filesystem"
S3 = "s3"
S3_VARIABLES = (
    "DOCUMENTS_S3_BUCKET",
    "DOCUMENTS_S3_ENDPOINT_URL",
    "DOCUMENTS_S3_ACCESS_KEY",
    "DOCUMENTS_S3_SECRET_KEY",
)


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
                # No pre-signed URL is ever handed out: downloads go through the API.
                "querystring_auth": False,
            },
        }
    return {
        "BACKEND": "apps.documents.stockage.StockageEcritureUnique",
        "OPTIONS": {"location": env.get("DOCUMENTS_ROOT", "")},
    }


def _posix(chemin: str) -> PurePosixPath:
    return PurePosixPath(posixpath.normpath(chemin.replace("\\", "/")))


def _est_sous(chemin: PurePosixPath, parent: PurePosixPath) -> bool:
    return chemin == parent or parent in chemin.parents


def valider_documents_root(documents_root: str, *, repo_root: str, code_dir: str | None) -> None:
    """Refuse a production DOCUMENTS_ROOT that is relative or inside the code.

    ``repo_root`` is skipped when it is the filesystem root: in the image the code is copied
    to ``/app`` so its parent is ``/`` and every absolute path would otherwise be "inside".
    """
    if not documents_root or not (
        documents_root.startswith("/") or Path(documents_root).is_absolute()
    ):
        raise ImproperlyConfigured("DOCUMENTS_ROOT must be an absolute path")
    racine = _posix(documents_root)
    if racine == racine.parent:
        raise ImproperlyConfigured("DOCUMENTS_ROOT must not be the filesystem root")
    interdits = [PurePosixPath("/app")]
    if code_dir:
        interdits.append(_posix(code_dir))
    depot = _posix(repo_root)
    if depot != depot.parent:  # repository at "/" (container): no in-repository check
        interdits.append(depot)
    for interdit in interdits:
        if _est_sous(racine, interdit):
            raise ImproperlyConfigured(
                f"DOCUMENTS_ROOT must be outside the application code and repository ({interdit})"
            )
