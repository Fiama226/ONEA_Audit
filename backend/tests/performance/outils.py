"""Outils communs aux tests de performance : resolution des URL, mesure des requetes et du temps."""

import time
from dataclasses import dataclass
from typing import Any

from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

# Comptes de demonstration : le RAI voit tout, les tableaux de bord dependent du profil.
ROLES = {
    "/api/v1/dashboards/auditee/": "audite1",
    "/api/v1/dashboards/auditor/": "auditeur1",
    "/api/v1/dashboards/dg/": "dg",
    "/api/v1/user-accounts/": "admin",
    "/api/v1/user-accounts/directory-search/": "admin",
    "/api/v1/user-accounts/{id}/": "admin",
}
DEFAUT = "rai"

# Filtres facultatifs ecartes des requetes (ils videraient les listes) : seuls ceux-ci passent.
OBLIGATOIRES = frozenset(
    {"constat", "provisoire", "rapport", "action", "with", "questionnaire", "type", "format"}
)

# Routes `{id}` dont l'identifiant est celui de la mission (ressource unique par mission).
PAR_MISSION = (
    "/api/v1/audit-frameworks/{id}/",
    "/api/v1/audit-frameworks/{id}/snapshot/",
    "/api/v1/orientation-reports/{id}/",
)


@dataclass
class Mesure:
    statut: int
    requetes: int
    ms: float


def mesurer(client: APIClient, url: str) -> Mesure:
    """La premiere requete chauffe les caches (droits, types) ; la seconde est mesuree."""
    client.get(url)
    debut = time.perf_counter()
    with CaptureQueriesContext(connection) as capture:
        reponse = client.get(url)
    return Mesure(reponse.status_code, len(capture), (time.perf_counter() - debut) * 1000)


def _elements(reponse: Any) -> list[dict[str, Any]]:
    """Elements d'une reponse de liste, paginee ou non."""
    if reponse.status_code != 200 or "json" not in reponse.headers.get("Content-Type", ""):
        return []
    donnees = reponse.json()
    resultats = donnees.get("results") if isinstance(donnees, dict) else donnees
    return [e for e in resultats or [] if isinstance(e, dict) and "id" in e]


class Resolveur:
    """Fabrique les URL concretes a partir d'un chemin du schema OpenAPI."""

    def __init__(
        self,
        client: APIClient,
        contexte: dict[str, Any],
        routes: dict[str, frozenset[str]],
        page_size: int = 25,
    ) -> None:
        self.client = client
        self.contexte = contexte
        self.routes = routes
        self.page_size = page_size
        self._ids: dict[str, str | None] = {}

    def _valeurs(self) -> dict[str, str]:
        c = self.contexte
        valeurs = {
            "mission": c["mission"],
            "constat": c["constat"],
            "provisoire": c["provisoire"],
            "rapport": c["rapport"],
            "action": c["action"],
            "processus": c["processus"],
            "with": c["carte"],
            "q": "audit",
            "questionnaire": c["questionnaire"],
            "format": "xlsx",
            "type": "xlsx",
            "annee": "2026",
        }
        return {k: v for k, v in valeurs.items() if v}

    def _requete(self, chemin: str, *, mission: str | None, page_size: int | None = None) -> str:
        """Parametres declares par la route ; `mission` en plus si la liste l'exige (400 sinon)."""
        declares = set(self.routes.get(chemin, ())) & OBLIGATOIRES
        if chemin in ("/api/v1/search/", "/api/v1/user-accounts/directory-search/"):
            declares.add("q")
        if chemin == "/api/v1/auditable-objects/tree/":
            declares.add("processus")
        if mission is not None:
            declares.add("mission")
        if chemin == "/api/v1/audit-log/":
            declares.discard("action")  # filtre de journal (create/update/delete), pas une action
        if "export" not in chemin:  # `type` et `format` ne sont des parametres que des exports
            declares -= {"type", "format"}
        valeurs = {k: v for k, v in self._valeurs().items() if k in declares}
        if chemin.startswith("/api/v1/follow-up/") and "action" in valeurs:
            valeurs["action"] = self.contexte["suivi"]  # le suivi porte l'identifiant d'action
        if mission is not None:
            valeurs["mission"] = mission
        if "{" not in chemin and (page_size or "page_size" in declares):
            valeurs["page_size"] = str(page_size or self.page_size)
        return "&".join(f"{k}={v}" for k, v in valeurs.items())

    def _liste(self, base: str, page_size: int) -> tuple[str, Any]:
        """URL de liste valide et peuplee : sans `mission`, puis avec la mission chargee, puis
        avec une mission de demonstration (entretiens, reunions, etc.)."""
        repli: tuple[str, Any] | None = None
        for mission in (None, self.contexte["mission"], self.contexte["mission_demo"]):
            url = f"{base}?{self._requete(base, mission=mission, page_size=page_size)}"
            reponse = self.client.get(url)
            if reponse.status_code == 400:
                continue
            if _elements(reponse):
                return url, reponse
            repli = repli or (url, reponse)
        return repli or (url, reponse)

    def _premier(self, chemin: str) -> str | None:
        base = chemin.split("{")[0]
        if base not in self._ids:
            _url, reponse = self._liste(base, 1)
            elements = _elements(reponse)
            self._ids[base] = str(elements[0]["id"]) if elements else None
        return self._ids[base]

    def url(self, chemin: str) -> str:
        if "{" not in chemin:
            return self._liste(chemin, self.page_size)[0]
        if "{type_document}" in chemin:
            valeur = self.contexte["type_document"]
        elif chemin.startswith("/api/v1/document-versions/"):
            valeur = self.contexte["version_document"]
        elif chemin in PAR_MISSION:
            valeur = self.contexte["mission"]
        else:
            valeur = self._premier(chemin) or self.contexte["mission"]
        concret = chemin.replace("{id}", str(valeur)).replace("{type_document}", str(valeur))
        return f"{concret}?{self._requete(chemin, mission=None)}"


def contexte_complet(contexte: dict[str, Any], client: APIClient) -> dict[str, Any]:
    """Complete le contexte du semis avec les identifiants du referentiel et des documents."""
    from apps.analyse.models import Questionnaire
    from apps.documents.models import DocumentVersion, FormatNumerotation
    from apps.missions.models import Entretien
    from apps.recommandations.models import Action
    from apps.referentiel.models import CartographieVersion, Processus
    from apps.suivi.models import SuiviAction

    return {
        **contexte,
        "mission_demo": str(Entretien.objects.order_by("created_at").first().mission_id),
        "suivi": str(SuiviAction.objects.order_by("created_at").first().pk),
        "action": str(Action.objects.order_by("created_at").first().pk),
        "processus": str(Processus.objects.order_by("created_at").first().pk),
        "carte": str(CartographieVersion.objects.order_by("created_at").first().pk),
        "questionnaire": str(Questionnaire.objects.order_by("created_at").first().pk),
        "version_document": str(DocumentVersion.objects.order_by("created_at").first().pk),
        "type_document": FormatNumerotation.objects.order_by("created_at").first().type_document,
    }
