# ruff: noqa: F811, F401
"""Matrice rôle x route des deux apps du lot 7 (D13) : refus de rôle, visibilité, droits.

Ordre des refus : rôle global 403 -> mission ou objet invisible 404 -> droit 403 -> corps 400
-> règle métier 422. ADMIN : 403 partout, sauf `signature-settings`.
"""

from collections.abc import Callable
from typing import Any

import pytest

from apps.communication.models import Rapport, RapportProvisoire
from tests.accomplissement.fixtures_api import client_de
from tests.communication.conftest import (
    constat,
    constat_valide,
    mission_en_communication,
    rai,
    rapport_redige,
)
from tests.communication.factories import RapportProvisoireFactory
from tests.communication.fixtures_api import (
    DESTINATAIRES,
    PROVISOIRES,
    RAPPORTS,
    REPONSES,
    EquipeRapport,
    equipe,
)
from tests.communication.support_t8 import admin, dg
from tests.missions.conftest import audite_affecte, auditeur_mission, chef, mission_lancee

pytestmark = pytest.mark.django_db

ROLES = ("rai", "chef", "auditeur", "audite", "non_affecte", "audite_non_affecte", "admin", "dg")
# Colonne = ordre de ROLES.
Appel = tuple[str, Callable[[Rapport, RapportProvisoire, EquipeRapport], tuple[str, Any]]]


def _corps_reponse(p: RapportProvisoire, e: EquipeRapport) -> dict[str, Any]:
    return {
        "provisoire": str(p.pk),
        "constat": str(e.mission.pk),  # sans objet : le refus précède toute lecture du constat
        "commentaire": "Réponse.",
        "confirme": True,
    }


ROUTES: dict[str, tuple[str, str, Callable[..., Any] | None, list[int]]] = {
    # nom: (méthode, URL avec {r} rapport, {p} provisoire, {m} mission), corps, statuts par rôle)
    "reports-list": (
        "get",
        RAPPORTS + "?mission={m}",
        None,
        [200, 200, 200, 200, 404, 404, 403, 200],
    ),
    "reports-detail": ("get", RAPPORTS + "{r}/", None, [200, 200, 200, 403, 404, 404, 403, 404]),
    "reports-preview": (
        "get",
        RAPPORTS + "{r}/preview/",
        None,
        [200, 200, 200, 403, 404, 403, 403, 403],
    ),
    "reports-create": (
        "post",
        RAPPORTS,
        lambda r, p, e: {"mission": str(e.mission.pk)},
        [422, 422, 422, 403, 404, 403, 403, 403],
    ),
    "reports-patch": (
        "patch",
        RAPPORTS + "{r}/",
        lambda r, p, e: {},
        [200, 200, 200, 403, 404, 403, 403, 403],
    ),
    "reports-submit": (
        "post",
        RAPPORTS + "{r}/submit/",
        None,
        [403, 422, 403, 403, 404, 403, 403, 403],
    ),
    "reports-validate": (
        "post",
        RAPPORTS + "{r}/validate/",
        lambda r, p, e: {},
        [400, 403, 403, 403, 404, 403, 403, 403],
    ),
    "reports-return": (
        "post",
        RAPPORTS + "{r}/return/",
        lambda r, p, e: {},
        [400, 403, 403, 403, 404, 403, 403, 403],
    ),
    "reports-distribute": (
        "post",
        RAPPORTS + "{r}/distribute/",
        lambda r, p, e: {},
        [422, 403, 403, 403, 404, 403, 403, 403],
    ),
    "reports-correct": (
        "post",
        RAPPORTS + "{r}/correct/",
        lambda r, p, e: {},
        [400, 403, 403, 403, 404, 403, 403, 403],
    ),
    "reports-acknowledge": (
        "post",
        RAPPORTS + "{r}/acknowledge/",
        None,
        [403, 403, 403, 403, 404, 404, 403, 404],
    ),
    "reports-transmit-draft": (
        "post",
        RAPPORTS + "{r}/transmit-draft/",
        lambda r, p, e: {},
        [422, 422, 403, 403, 404, 403, 403, 403],
    ),
    "reports-validation-text": (
        "get",
        RAPPORTS + "{r}/validation-text/",
        None,
        [422, 403, 403, 403, 404, 403, 403, 403],
    ),
    "reports-download": (
        "get",
        RAPPORTS + "{r}/download/",
        None,
        [404, 404, 404, 404, 404, 404, 403, 404],
    ),
    "drafts-list": (
        "get",
        PROVISOIRES + "?mission={m}",
        None,
        [200, 200, 200, 200, 404, 404, 403, 403],
    ),
    "drafts-detail": ("get", PROVISOIRES + "{p}/", None, [200, 200, 200, 200, 404, 404, 403, 403]),
    "responses-list": (
        "get",
        REPONSES + "?provisoire={p}",
        None,
        [200, 200, 200, 200, 404, 404, 403, 403],
    ),
    "recipients-list": (
        "get",
        DESTINATAIRES + "?rapport={r}",
        None,
        [200, 200, 200, 200, 404, 404, 403, 404],
    ),
    "recipients-create": (
        "post",
        DESTINATAIRES,
        lambda r, p, e: {"rapport": str(r.pk), "nom_externe": "Tiers", "categorie": "AUTRE"},
        [201, 403, 403, 403, 403, 403, 403, 403],
    ),
}


@pytest.mark.parametrize("nom", ROUTES)
@pytest.mark.parametrize("qui", ROLES)
def test_matrice_droits_lot7(
    equipe: EquipeRapport, rapport_redige: Rapport, nom: str, qui: str
) -> None:
    provisoire = RapportProvisoireFactory(rapport=rapport_redige)
    methode, modele, corps, statuts = ROUTES[nom]
    url = modele.format(r=rapport_redige.pk, p=provisoire.pk, m=equipe.mission.pk)
    donnees = corps(rapport_redige, provisoire, equipe) if corps else None
    client = client_de(equipe.users[qui])
    reponse = (
        getattr(client, methode)(url, donnees, format="json")
        if methode != "get"
        else client.get(url)
    )
    assert reponse.status_code == statuts[ROLES.index(qui)], (nom, qui, reponse.content[:200])


@pytest.mark.parametrize(
    "qui", ["rai", "chef", "auditeur", "audite", "non_affecte", "audite_non_affecte", "admin", "dg"]
)
def test_reponse_et_texte_reserves_a_l_audite(
    equipe: EquipeRapport, rapport_redige: Rapport, qui: str
) -> None:
    """Hors audité : 403 avant toute lecture (404 si l'audité n'est pas affecté)."""
    provisoire = RapportProvisoireFactory(rapport=rapport_redige)
    attendu = {"audite": None, "audite_non_affecte": 404}.get(qui, 403)
    client = client_de(equipe.users[qui])
    creation = client.post(REPONSES, _corps_reponse(provisoire, equipe), format="json")
    texte = client.get(f"{REPONSES}texte/?provisoire={provisoire.pk}&constat={equipe.mission.pk}")
    if attendu is not None:
        assert creation.status_code == attendu, qui
        assert texte.status_code == attendu, qui
    else:
        # l'audité affecté atteint la route : constat sans objet -> 404, jamais 403 ni 500
        assert creation.status_code == 404 and texte.status_code == 404


def test_signature_settings_ouvert_a_l_admin(equipe: EquipeRapport) -> None:
    assert client_de(equipe.users["admin"]).get("/api/v1/signature-settings/").status_code == 200
    assert client_de(equipe.users["dg"]).get("/api/v1/signature-settings/").status_code == 403
