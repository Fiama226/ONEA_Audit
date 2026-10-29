"""Contrat de stockage des pièces justificatives (preuves d'audit).

Le contrat `StockageFichiers` n'expose ni suppression ni écrasement : une preuve n'est jamais
effacée. L'implémentation par défaut, `StockageDisque`, écrit sur le disque du serveur
(`settings.STOCKAGE_PREUVES`), jamais dans le dépôt et jamais sous une URL publique. Les clés
sont générées ici (UUID), jamais dérivées d'un nom fourni par l'utilisateur.

Écriture atomique et à usage unique : le contenu va dans un fichier temporaire du même
répertoire (hachage SHA-256 calculé pendant l'écriture), est synchronisé (`fsync`) puis lié à
son nom définitif par `os.link`, qui échoue si la clé existe déjà (aucune réécriture possible) ;
le nom temporaire est ensuite retiré. Sous Windows (développement), les modes POSIX sont ignorés.
"""

import contextlib
import hashlib
import os
import re
import tempfile
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, BinaryIO, Protocol

from django.conf import settings
from django.utils.module_loading import import_string

from apps.core.exceptions import RegleMetierError

BLOC = 1024 * 1024  # blocs de 1 Mio
_SEGMENT = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class StockageError(RegleMetierError):
    """Erreur du stockage des preuves."""


class FichierTropVolumineuxError(StockageError):
    def __init__(self) -> None:
        super().__init__("Le fichier dépasse la taille maximale de 50 Mo.")


class FichierIntrouvableError(StockageError):
    def __init__(self) -> None:
        super().__init__("Le fichier de cette pièce est introuvable : contactez l'administrateur.")


@dataclass(frozen=True)
class FichierStocke:
    cle: str  # générée par le stockage, jamais issue du nom client
    taille: int
    sha256: str  # hexadécimal minuscule, calculé pendant l'écriture


class StockageFichiers(Protocol):
    def deposer(self, flux: BinaryIO, *, prefixe: str, taille_max: int) -> FichierStocke: ...

    def ouvrir(self, cle: str) -> BinaryIO: ...  # lecture seule ; FichierIntrouvableError

    def existe(self, cle: str) -> bool: ...

    def cles(self) -> Iterator[str]: ...  # lecture seule : toutes les clés stockées


def _segments_prefixe(prefixe: str) -> list[str]:
    segments = prefixe.split("/")
    if not prefixe or not all(_SEGMENT.fullmatch(s) for s in segments):
        raise StockageError("Préfixe de stockage invalide.")
    return segments


def _fsync_dossier(dossier: Path) -> None:
    if os.name == "nt":  # pas de fsync de répertoire sous Windows
        return
    fd = os.open(dossier, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class StockageDisque:
    """Stockage sur le disque du serveur, à écriture unique, droits 0640 / 0750."""

    def __init__(self, racine: str | Path) -> None:
        self.racine = Path(racine)

    def _dossier(self, segments: list[str]) -> Path:
        dossier = self.racine
        for segment in segments:
            dossier = dossier / segment
            if dossier.is_symlink():
                raise StockageError("Préfixe de stockage invalide.")
            if not dossier.exists():
                dossier.mkdir(mode=0o750, parents=False, exist_ok=True)
                with contextlib.suppress(OSError):
                    dossier.chmod(0o750)
        return dossier

    def deposer(self, flux: BinaryIO, *, prefixe: str, taille_max: int) -> FichierStocke:
        segments = _segments_prefixe(prefixe)
        self.racine.mkdir(mode=0o750, parents=True, exist_ok=True)
        dossier = self._dossier(segments)
        empreinte = hashlib.sha256()
        taille = 0
        fd, nom_temporaire = tempfile.mkstemp(dir=dossier, prefix=".depot-")
        temporaire = Path(nom_temporaire)
        try:
            with os.fdopen(fd, "wb") as sortie:
                while bloc := flux.read(BLOC):
                    taille += len(bloc)
                    if taille > taille_max:
                        raise FichierTropVolumineuxError
                    empreinte.update(bloc)
                    sortie.write(bloc)
                sortie.flush()
                os.fsync(sortie.fileno())
            with contextlib.suppress(OSError):
                temporaire.chmod(0o640)
            identifiant = str(uuid.uuid4())
            os.link(temporaire, dossier / identifiant)  # échoue si la clé existe : jamais réécrite
            _fsync_dossier(dossier)
        finally:
            temporaire.unlink(missing_ok=True)
        return FichierStocke(
            cle=f"{prefixe}/{identifiant}", taille=taille, sha256=empreinte.hexdigest()
        )

    def _chemin(self, cle: str) -> Path:
        *segments, identifiant = cle.split("/")
        if not segments or not _UUID.fullmatch(identifiant):
            raise FichierIntrouvableError
        try:
            _segments_prefixe("/".join(segments))
        except StockageError:
            raise FichierIntrouvableError from None
        chemin = self.racine.joinpath(*segments, identifiant)
        parent = self.racine
        for segment in segments:
            parent = parent / segment
            if parent.is_symlink():
                raise FichierIntrouvableError
        return chemin

    def ouvrir(self, cle: str) -> BinaryIO:
        chemin = self._chemin(cle)
        try:
            return chemin.open("rb")
        except OSError:
            raise FichierIntrouvableError from None

    def existe(self, cle: str) -> bool:
        try:
            return self._chemin(cle).is_file()
        except FichierIntrouvableError:
            return False

    def cles(self) -> Iterator[str]:
        """Clés de tous les fichiers stockés (fichiers temporaires de dépôt et liens exclus)."""
        if not self.racine.is_dir():
            return
        for chemin in sorted(self.racine.rglob("*")):
            if chemin.is_symlink() or not chemin.is_file() or chemin.name.startswith(".depot-"):
                continue
            yield chemin.relative_to(self.racine).as_posix()


@lru_cache(maxsize=8)
def _instancier(backend: str, options: tuple[tuple[str, Any], ...]) -> StockageFichiers:
    classe = import_string(backend)
    instance: StockageFichiers = classe(**{k.lower(): v for k, v in options})
    return instance


def stockage_preuves() -> StockageFichiers:
    """Instancie `settings.STOCKAGE_PREUVES` (instances mises en cache par configuration)."""
    config = settings.STOCKAGE_PREUVES
    options = tuple(sorted((k, str(v)) for k, v in config.get("OPTIONS", {}).items()))
    return _instancier(config["BACKEND"], options)


def empreinte_fichier(stockage: StockageFichiers, cle: str) -> str:
    """SHA-256 du fichier stocké, relu en flux (blocs de 1 Mio)."""
    empreinte = hashlib.sha256()
    with stockage.ouvrir(cle) as flux:
        while bloc := flux.read(BLOC):
            empreinte.update(bloc)
    return empreinte.hexdigest()
