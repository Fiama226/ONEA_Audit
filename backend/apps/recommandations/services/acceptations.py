"""Acceptation du risque par la direction concernée (D8), confirmée par signature horodatée."""

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.constats.models import Recommandation, StatutConstat
from apps.core.exceptions import RegleMetierError
from apps.core.services import enregistrer, refuser, relire
from apps.missions.acces import est_responsable_entite
from apps.signatures.models import TypeDocumentSignable
from apps.signatures.services import confirmer
from apps.users.models import Role, User

from ..models import AcceptationRisque, Action
from ._fenetres import ouvrir_plan
from .actions import MSG_NON_VALIDE

MSG_DROIT = "Seul l'audité responsable de l'entité du constat peut accepter le risque."
MSG_JUSTIFICATION = "Saisissez la justification de l'acceptation du risque."
MSG_DEJA = "Le risque de cette recommandation est déjà accepté."
MSG_ACTIONS = (
    "Cette recommandation fait l'objet d'actions : supprimez-les avant d'accepter le risque."
)
MSG_RETRAIT = "Seul l'auteur de l'acceptation ou le RAI peut la retirer."


def texte_acceptation(recommandation: Recommandation, justification: str, user: User) -> str:
    """Texte exact confirmé par l'audité (à confirmer avec ONEA)."""
    qui = user.nom_complet + (f", {user.fonction}" if user.fonction else "")
    constat = recommandation.constat
    return (
        f"Je soussigné(e) {qui}, accepte au nom de ma direction le risque lié à la "
        f"recommandation « {recommandation.libelle} » du constat {constat.reference}, "
        f"sans plan d'actions, pour le motif suivant : {justification}"
    )


@transaction.atomic
def accepter_risque(
    recommandation: Recommandation,
    *,
    justification: str,
    by: User,
    adresse_ip: str | None = None,
) -> AcceptationRisque:
    mission = ouvrir_plan(recommandation.mission)
    recommandation = relire(recommandation)
    constat = recommandation.constat
    if (
        by.role != Role.AUDITE
        or constat.entite_id is None
        or not est_responsable_entite(by, mission, constat.entite_id)
    ):
        raise PermissionDenied(MSG_DROIT)
    if constat.statut != StatutConstat.VALIDE:
        raise RegleMetierError(MSG_NON_VALIDE)
    justification = justification.strip()
    if not justification:
        raise refuser(MSG_JUSTIFICATION, justification=MSG_JUSTIFICATION)
    if AcceptationRisque.objects.filter(recommandation=recommandation).exists():
        raise RegleMetierError(MSG_DEJA)
    if Action.objects.filter(recommandation=recommandation).exists():
        raise RegleMetierError(MSG_ACTIONS)
    confirmation = confirmer(
        type_document=TypeDocumentSignable.ACCEPTATION_RISQUE,
        objet=recommandation,
        texte=texte_acceptation(recommandation, justification, by),
        donnees={
            "recommandation": str(recommandation.pk),
            "constat": constat.reference,
            "libelle": recommandation.libelle,
            "justification": justification,
        },
        by=by,
        adresse_ip=adresse_ip,
    )
    acceptation = AcceptationRisque(
        mission=mission,
        recommandation=recommandation,
        justification=justification,
        auteur=by,
        confirmation=confirmation,
    )
    enregistrer(acceptation, by=by, creation=True)
    return acceptation


@transaction.atomic
def retirer_acceptation(acceptation: AcceptationRisque, *, by: User) -> None:
    ouvrir_plan(acceptation.mission)
    acceptation = relire(acceptation)
    if by.role != Role.RAI and acceptation.auteur_id != by.pk:
        raise PermissionDenied(MSG_RETRAIT)
    acceptation.soft_delete(by)
