"""Accord de l'entité auditée sur les résultats des tests (étape XIII, fiche IFACI)."""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import QuerySet

from apps.core.exceptions import RegleMetierError
from apps.core.services import enregistrer, refuser
from apps.missions.acces import est_responsable_entite
from apps.missions.gardes import STATUTS_FIGES, verrouiller_mission
from apps.missions.models import EtapeMission, Mission, StatutEtape
from apps.referentiel.models import Direction
from apps.users.models import Role, User

from ..models import AccordResultats, PositionAccord

ETAPE_RESULTATS = 13
MSG_DROIT = "Seul l'audité responsable de l'entité peut donner sa position sur les résultats."
MSG_ENTITE = "Cette entité n'est pas auditée par la mission."
MSG_ETAPE = "La position sur les résultats se donne pendant l'étape XIII."
MSG_DESACCORD = "Motivez le désaccord."
MSG_POSITION = "Position inconnue."


@transaction.atomic
def donner_accord_resultats(
    mission: Mission, *, entite: Direction, position: str, commentaire: str, by: User
) -> AccordResultats:
    mission = verrouiller_mission(mission)
    if mission.statut in STATUTS_FIGES:
        raise RegleMetierError(MSG_ETAPE)
    if not mission.entites.filter(pk=entite.pk).exists():
        raise refuser(MSG_ENTITE, entite=MSG_ENTITE)
    if by.role != Role.AUDITE or not est_responsable_entite(by, mission, entite.pk):
        raise PermissionDenied(MSG_DROIT)
    statut = (
        EtapeMission.objects.filter(mission=mission, numero=ETAPE_RESULTATS)
        .values_list("statut", flat=True)
        .first()
    )
    if statut not in (StatutEtape.EN_COURS, StatutEtape.RENVOYEE):
        raise RegleMetierError(MSG_ETAPE)
    if position not in PositionAccord.values:
        raise refuser(MSG_POSITION, position=MSG_POSITION)
    commentaire = commentaire.strip()
    if position == PositionAccord.DESACCORD and not commentaire:
        raise refuser(MSG_DESACCORD, commentaire=MSG_DESACCORD)
    accord = AccordResultats(
        mission=mission, entite=entite, auteur=by, position=position, commentaire=commentaire
    )
    enregistrer(accord, by=by, creation=True)
    return accord


def accords_lisibles(user: User, mission: Mission) -> QuerySet[AccordResultats]:
    """Équipe et RAI : toutes les positions ; l'audité : celles de sa direction."""
    qs = AccordResultats.objects.filter(mission=mission).select_related("entite", "auteur")
    if user.role == Role.AUDITE:
        return qs.filter(entite__code=user.direction_code) if user.direction_code else qs.none()
    return qs


def controle_accord_resultats(etape: EtapeMission) -> list[str]:
    """XIII : chaque entité auditée a donné sa position (accord ou désaccord motivé)."""
    entites = Mission.objects.get(pk=etape.mission_id).entites.order_by("code")
    obtenues = set(
        AccordResultats.objects.filter(mission_id=etape.mission_id).values_list(
            "entite_id", flat=True
        )
    )
    return [
        f"L'entité « {e.libelle} » n'a pas donné sa position sur les résultats des tests."
        for e in entites
        if e.pk not in obtenues
    ]
