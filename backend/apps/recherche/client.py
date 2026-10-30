"""Client du moteur de recherche (Meilisearch) derrière un protocole minimal.

Le reste de l'application ne dépend que de `MoteurRecherche` ; les tests utilisent
`tests.recherche.fakes.MoteurMemoire`. La clé d'API ne figure jamais dans un message
d'exception ni dans un journal.
"""

import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

import requests
from django.conf import settings
from django.utils.module_loading import import_string

from .exceptions import RechercheIndisponibleError

logger = logging.getLogger(__name__)

MARQUEUR_DEBUT = "\u0002"
MARQUEUR_FIN = "\u0003"
ATTENTE_TACHE_MAX = 30.0  # secondes


@dataclass(frozen=True)
class Hit:
    id: str
    type: str
    objet_id: str
    mission_id: str | None
    titre: str
    sous_titre: str
    extrait: str  # surlignage \u0002…\u0003


class MoteurRecherche(Protocol):
    def configurer(self) -> None: ...
    def indexer(self, documents: list[dict[str, Any]]) -> None: ...
    def retirer(self, ids: list[str]) -> None: ...
    def rechercher(self, q: str, *, filtre: str, limite: int) -> list[Hit]: ...
    def vider(self) -> None: ...
    def sante(self) -> bool: ...


REGLAGES_INDEX: dict[str, Any] = {
    "searchableAttributes": ["titre", "reference", "mission_reference", "sous_titre", "texte"],
    "filterableAttributes": ["type", "mission_id", "audience", "annee"],
    "sortableAttributes": ["date"],
    "localizedAttributes": [{"attributePatterns": ["*"], "locales": ["fra"]}],
    "displayedAttributes": [
        "id",
        "type",
        "objet_id",
        "mission_id",
        "titre",
        "reference",
        "mission_reference",
        "sous_titre",
        "audience",
        "annee",
        "date",
    ],
}


def echapper_filtre(valeur: str) -> str:
    """Échappe antislash puis guillemets pour insérer `valeur` dans un littéral de filtre."""
    return valeur.replace("\\", "\\\\").replace('"', '\\"')


class MeilisearchHttp:
    def __init__(
        self, *, url: str, cle: str, index: str, timeout: float = 3, session: Any = None
    ) -> None:
        self._url = url.rstrip("/")
        self._index = index
        self._timeout = timeout
        self._http = session or requests.Session()
        self._entetes = {"Authorization": f"Bearer {cle}"} if cle else {}

    def _appeler(self, methode: str, chemin: str, json: Any = None) -> Any:
        try:
            reponse = self._http.request(
                methode,
                f"{self._url}{chemin}",
                json=json,
                headers=self._entetes,
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            logger.warning("Recherche indisponible (%s).", type(exc).__name__)
            raise RechercheIndisponibleError from None
        if not reponse.ok:
            logger.warning("Recherche : réponse HTTP %s.", reponse.status_code)
            raise RechercheIndisponibleError
        try:
            return reponse.json() if reponse.content else {}
        except ValueError:
            raise RechercheIndisponibleError from None

    def _attendre(self, tache: dict[str, Any]) -> None:
        uid = tache.get("taskUid")
        if uid is None:
            return
        fin = time.monotonic() + ATTENTE_TACHE_MAX
        while time.monotonic() < fin:
            etat = self._appeler("GET", f"/tasks/{uid}").get("status")
            if etat == "succeeded":
                return
            if etat in ("failed", "canceled"):
                logger.warning("Recherche : tâche %s en état %s.", uid, etat)
                raise RechercheIndisponibleError
            time.sleep(0.05)
        raise RechercheIndisponibleError

    def _chemin(self, suite: str = "") -> str:
        return f"/indexes/{self._index}{suite}"

    def configurer(self) -> None:
        # PATCH crée l'index s'il n'existe pas : idempotent.
        self._attendre(self._appeler("PATCH", self._chemin("/settings"), REGLAGES_INDEX))

    def indexer(self, documents: list[dict[str, Any]]) -> None:
        if documents:
            self._attendre(
                self._appeler("POST", self._chemin("/documents?primaryKey=id"), documents)
            )

    def retirer(self, ids: list[str]) -> None:
        if ids:
            self._attendre(self._appeler("POST", self._chemin("/documents/delete-batch"), ids))

    def rechercher(self, q: str, *, filtre: str, limite: int) -> list[Hit]:
        corps: dict[str, Any] = {
            "q": q,
            "limit": limite,
            "attributesToHighlight": ["titre", "texte"],
            "highlightPreTag": MARQUEUR_DEBUT,
            "highlightPostTag": MARQUEUR_FIN,
            "attributesToCrop": ["texte:30"],
        }
        if filtre:
            corps["filter"] = filtre
        reponse = self._appeler("POST", self._chemin("/search"), corps)
        hits: list[Hit] = []
        for brut in reponse.get("hits", []):
            fmt = brut.get("_formatted", {})
            hits.append(
                Hit(
                    id=str(brut["id"]),
                    type=str(brut.get("type", "")),
                    objet_id=str(brut.get("objet_id", "")),
                    mission_id=brut.get("mission_id"),
                    titre=str(fmt.get("titre", brut.get("titre", ""))),
                    sous_titre=str(brut.get("sous_titre", "")),
                    extrait=str(fmt.get("texte", "")),
                )
            )
        return hits

    def vider(self) -> None:
        self._attendre(self._appeler("DELETE", self._chemin("/documents")))

    def sante(self) -> bool:
        try:
            return bool(self._appeler("GET", "/health").get("status") == "available")
        except RechercheIndisponibleError:
            return False


@lru_cache(maxsize=4)
def _instancier(backend: str, url: str, cle: str, index: str, timeout: float) -> MoteurRecherche:
    classe = import_string(backend)
    moteur_: MoteurRecherche = classe(url=url, cle=cle, index=index, timeout=timeout)
    return moteur_


def moteur() -> MoteurRecherche:
    """Moteur configuré par `settings.RECHERCHE` (instance mise en cache)."""
    r = settings.RECHERCHE
    return _instancier(r["BACKEND"], r["URL"], r["CLE"], r["INDEX"], r["TIMEOUT"])


def reinitialiser_moteur() -> None:
    _instancier.cache_clear()
