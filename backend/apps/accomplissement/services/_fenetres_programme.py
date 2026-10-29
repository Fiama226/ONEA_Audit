"""Fenêtres d'écriture et droits du programme de travail (VIII, IX) et des compléments (XII).

Ordre de verrouillage (identique à celui du moteur d'étapes du lot 3) : mission, puis lignes
d'étape, puis entité. Chaque service commence par `verrouiller`, vérifie les droits, puis la
fenêtre de l'étape visée avec `exiger_fenetre`.
"""

from enum import StrEnum
from uuid import UUID

from apps.analyse.gardes import exiger_actives
from apps.missions.gardes import exiger_etape_ouverte
from apps.missions.models import EtapeMission, Mission
from apps.missions.permissions import exiger, exiger_contribution
from apps.missions.services.etapes import contexte_actions
from apps.missions.services.travaux import verrouiller_travaux
from apps.users.models import User

from .. import droits

ETAPES_VERROUILLEES = (
    droits.ETAPE_CONTENU,
    droits.ETAPE_RESSOURCES,
    droits.ETAPE_COMPLEMENTAIRES,
)
MESSAGES: dict[int, str] = {
    droits.ETAPE_CONTENU: "Commencez l'étape VIII pour établir le programme de travail.",
    droits.ETAPE_RESSOURCES: (
        "Commencez l'étape IX pour affecter les auditeurs et planifier les charges."
    ),
    droits.ETAPE_COMPLEMENTAIRES: ("Commencez l'étape XII pour ajouter ou abandonner un test."),
}


class Droit(StrEnum):
    CONTENU = "contenu"
    RESSOURCES = "ressources"
    COMPLEMENTAIRES = "complementaires"


def verrouiller(mission: Mission) -> Mission:
    """Verrouille la mission (refuse figée / pas lancée), puis les lignes des étapes 8, 9, 12."""
    verrouillee = verrouiller_travaux(mission)
    list(
        EtapeMission.objects.select_for_update()
        .filter(mission=verrouillee, numero__in=ETAPES_VERROUILLEES)
        .order_by("numero")
        .values_list("pk", flat=True)
    )
    return verrouillee


def exiger_droit(user: User, mission: Mission, droit: Droit) -> None:
    """403 si `user` n'a pas le droit d'écriture demandé (source : `droits.profil`)."""
    if droit == Droit.CONTENU:
        exiger_contribution(user, mission)
        return
    _, ressources, complementaires = droits.profil(user, contexte_actions(mission, user))
    exiger(ressources if droit == Droit.RESSOURCES else complementaires)


def exiger_fenetre(mission_id: UUID, numero: int) -> None:
    """Étape non close (`EtapeCloseError`) et en cours ou renvoyée (message « Commencez... »)."""
    exiger_etape_ouverte(mission_id, numero)
    exiger_actives(mission_id, une_de=(numero,), message=MESSAGES[numero])
