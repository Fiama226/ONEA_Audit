"""Risques de mission (étape IV, D15) : copie figée de la cartographie ou risque nouveau."""

from collections.abc import Callable
from typing import Any

from django.db import transaction
from django.db.models import QuerySet

from apps.core.services import appliquer, enregistrer, refuser, relire
from apps.referentiel.models import Processus, Risque
from apps.referentiel.services import CelluleMatrice, matrice_de
from apps.users.models import User

from ..gardes import exiger_etape_ouverte
from ..models import EtapeMission, Mission, RisqueMission, StatutEtape, StatutMission
from .travaux import verrouiller_travaux

_DETAILS = {"description", "commentaire"}
_MODIFIABLES = {"probabilite", "impact", "commentaire", "libelle", "description"}
_ETAPE_RISQUES = 4

# Gardes appelées avant le retrait d'un risque de mission ; elles lèvent `RegleMetierError` pour
# l'interdire (ex. risque déjà utilisé par l'analyse, lot 5).
GARDES_RETRAIT: list[Callable[[RisqueMission], None]] = []


def _exiger_etape_iv(mission: Mission) -> None:
    """IV doit être EN_COURS ou RENVOYEE ; terminée ou validée : étape close (422)."""
    exiger_etape_ouverte(mission.pk, _ETAPE_RISQUES)
    statut = (
        EtapeMission.objects.filter(mission=mission, numero=_ETAPE_RISQUES)
        .values_list("statut", flat=True)
        .first()
    )
    if statut not in (StatutEtape.EN_COURS, StatutEtape.RENVOYEE):
        raise refuser("Commencez l'étape IV pour sélectionner les risques.")


def _echelle(valeur: int | None, champ: str, libelle: str) -> int:
    if valeur is None:
        message = f"{libelle} est obligatoire."
        raise refuser(message, **{champ: message})
    if not 1 <= valeur <= 5:
        message = f"{libelle} doit être comprise entre 1 et 5."
        raise refuser(message, **{champ: message})
    return valeur


def _controler_processus(mission: Mission, processus: Processus) -> None:
    if not mission.processus.filter(pk=processus.pk).exists():
        message = "Le processus doit être un processus de la mission."
        raise refuser(message, processus=message)


@transaction.atomic
def ajouter_risque_mission(
    mission: Mission,
    *,
    by: User,
    risque_source: Risque | None = None,
    processus: Processus | None = None,
    libelle: str = "",
    probabilite: int | None = None,
    impact: int | None = None,
    **details: Any,
) -> RisqueMission:
    mission = verrouiller_travaux(mission)
    _exiger_etape_iv(mission)
    if risque_source is not None:
        if (
            risque_source.deleted_at is not None
            or risque_source.version_id != mission.cartographie_id
        ):
            message = "Ce risque n'appartient pas à la cartographie de la mission."
            raise refuser(message, risque_source=message)
        _controler_processus(mission, risque_source.processus)
        if RisqueMission.objects.filter(mission=mission, risque_source=risque_source).exists():
            message = "Ce risque est déjà sélectionné."
            raise refuser(message, risque_source=message)
        risque = RisqueMission(
            mission=mission,
            risque_source=risque_source,
            processus=risque_source.processus,
            code_source=risque_source.code,
            libelle=risque_source.libelle,
            description=risque_source.description,
            probabilite=_echelle(
                risque_source.probabilite if probabilite is None else probabilite,
                "probabilite",
                "La probabilité",
            ),
            impact=_echelle(
                risque_source.impact if impact is None else impact, "impact", "L'impact"
            ),
        )
        appliquer(risque, {k: v for k, v in details.items() if k == "commentaire"}, _DETAILS)
    else:
        if processus is None:
            message = "Le processus est obligatoire."
            raise refuser(message, processus=message)
        _controler_processus(mission, processus)
        if not libelle.strip():
            message = "Le libellé est obligatoire."
            raise refuser(message, libelle=message)
        risque = RisqueMission(
            mission=mission,
            processus=processus,
            libelle=libelle.strip(),
            probabilite=_echelle(probabilite, "probabilite", "La probabilité"),
            impact=_echelle(impact, "impact", "L'impact"),
        )
        appliquer(risque, details, _DETAILS)
    enregistrer(risque, by=by, creation=True)
    return risque


@transaction.atomic
def modifier_risque_mission(rm: RisqueMission, *, by: User, **changes: Any) -> RisqueMission:
    mission = verrouiller_travaux(rm.mission)
    _exiger_etape_iv(mission)
    rm = relire(rm)
    if not rm.nouveau:
        for champ in ("libelle", "description"):
            if champ in changes:
                message = "Ce champ ne peut être modifié que pour un risque nouveau."
                raise refuser(message, **{champ: message})
    appliquer(rm, changes, _MODIFIABLES)
    _echelle(rm.probabilite, "probabilite", "La probabilité")
    _echelle(rm.impact, "impact", "L'impact")
    if not rm.libelle.strip():
        message = "Le libellé est obligatoire."
        raise refuser(message, libelle=message)
    enregistrer(rm, by=by)
    rm.refresh_from_db()  # score et niveau sont calculés par la base
    return rm


@transaction.atomic
def retirer_risque_mission(rm: RisqueMission, *, by: User) -> None:
    mission = verrouiller_travaux(rm.mission)
    _exiger_etape_iv(mission)
    rm = relire(rm)
    for garde in GARDES_RETRAIT:
        garde(rm)
    rm.soft_delete(by)


def matrice_mission(mission: Mission) -> list[CelluleMatrice]:
    lignes = RisqueMission.objects.filter(mission=mission).order_by("created_at")
    return matrice_de(
        (p, i, code or f"Nouveau : {libelle[:40]}")
        for p, i, code, libelle in lignes.values_list(
            "probabilite", "impact", "code_source", "libelle"
        )
    )


def risques_proposes() -> QuerySet[RisqueMission]:
    return (
        RisqueMission.objects.filter(risque_source__isnull=True, mission__deleted_at__isnull=True)
        .exclude(mission__statut=StatutMission.ANNULEE)
        .select_related("mission", "processus")
        .order_by("mission__reference", "created_at")
    )
