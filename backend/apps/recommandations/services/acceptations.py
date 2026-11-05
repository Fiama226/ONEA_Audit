"""Acceptation du risque par la direction concernée (D8), confirmée par signature horodatée."""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.constats.models import Recommandation, StatutConstat
from apps.core.exceptions import RegleMetierError
from apps.core.services import enregistrer, refuser, relire
from apps.gouvernance import regles_gouvernance
from apps.missions.acces import est_responsable_entite
from apps.missions.models import StatutMission
from apps.notifications.models import TypeNotification
from apps.notifications.services import notifier
from apps.signatures.models import TypeDocumentSignable
from apps.signatures.services import confirmer
from apps.users.models import Role, User

from ..models import (
    AcceptationRisque,
    Action,
    DecisionAcceptation,
    ValidateurAcceptation,
    ValidationAcceptation,
)
from ._fenetres import ouvrir_plan
from .actions import MSG_NON_VALIDE

MSG_DROIT = "Seul l'audité responsable de l'entité du constat peut accepter le risque."
MSG_JUSTIFICATION = "Saisissez la justification de l'acceptation du risque."
MSG_DEJA = "Le risque de cette recommandation est déjà accepté."
MSG_ACTIONS = (
    "Cette recommandation fait l'objet d'actions : supprimez-les avant d'accepter le risque."
)
MSG_RETRAIT = "Seul l'auteur de l'acceptation ou le RAI peut la retirer."
MSG_SANS_VALIDATION = "Cette acceptation n'attend aucune validation."
MSG_DEJA_DECIDEE = "Cette acceptation a déjà été décidée."
MSG_DROIT_DECISION: dict[str, str] = {
    ValidateurAcceptation.RAI: "Seul le RAI peut valider cette acceptation du risque.",
    ValidateurAcceptation.DG: "Seul le DG peut valider cette acceptation du risque.",
    ValidateurAcceptation.BOARD: (
        "Seul le DG peut enregistrer la décision du Conseil sur cette acceptation du risque."
    ),
}
MSG_MOTIF_DECISION = "Le motif de la décision est obligatoire."
MSG_REFERENCE_CONSEIL = "Indiquez la référence de la délibération du Conseil."
LIBELLE_AUTORITE: dict[str, str] = {
    ValidateurAcceptation.RAI: "du RAI",
    ValidateurAcceptation.DG: "de la Direction générale",
    ValidateurAcceptation.BOARD: "du Conseil",
}
# Rôle qui décide pour chaque autorité (le DG reporte la décision du Conseil).
ROLE_DECIDEUR: dict[str, str] = {
    ValidateurAcceptation.RAI: Role.RAI,
    ValidateurAcceptation.DG: Role.DG,
    ValidateurAcceptation.BOARD: Role.DG,
}


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
    niveau = str(constat.niveau or "")
    validateur = regles_gouvernance.risk_acceptance_validator(niveau)
    acceptation = AcceptationRisque(
        mission=mission,
        recommandation=recommandation,
        justification=justification,
        auteur=by,
        confirmation=confirmation,
        niveau_risque=niveau,
        validation_requise="" if validateur == "NONE" else validateur,
    )
    enregistrer(acceptation, by=by, creation=True)
    if acceptation.validation_requise:
        _notifier_validateurs(acceptation)
    return acceptation


def _notifier_validateurs(acceptation: AcceptationRisque) -> None:
    autorite = acceptation.validation_requise
    mission = acceptation.mission
    constat = acceptation.recommandation.constat
    notifier(
        User.objects.filter(role=ROLE_DECIDEUR[autorite], is_active=True),
        type=TypeNotification.ACCEPTATION_A_VALIDER,
        titre=f"Acceptation de risque à valider : {constat.reference}",
        message=(
            f"La direction auditée accepte le risque du constat {constat.reference} "
            f"(mission {mission.reference}, niveau {constat.get_niveau_display().lower()}). "
            f"Validation attendue {LIBELLE_AUTORITE[autorite]} (règle de gouvernance)."
        ),
        lien="/",
        objet=acceptation,
        cle=f"acceptation-a-valider:{acceptation.pk}",
    )


def acceptations_a_valider(user: User) -> QuerySet[AcceptationRisque]:
    """Acceptations actives qui attendent la décision de `user` (RAI, ou DG pour lui-même et
    pour le Conseil), missions ni clôturées ni annulées."""
    autorites = [a for a, role in ROLE_DECIDEUR.items() if role == user.role]
    if not autorites or not user.is_active:
        return AcceptationRisque.objects.none()
    return (
        AcceptationRisque.objects.filter(validation_requise__in=autorites)
        .exclude(pk__in=ValidationAcceptation.objects.values("acceptation_id"))
        .exclude(mission__statut__in=(StatutMission.CLOTUREE, StatutMission.ANNULEE))
        .select_related("mission", "recommandation__constat", "auteur")
        .order_by("created_at", "pk")
    )


def est_validee(acceptation: AcceptationRisque) -> bool:
    if not acceptation.validation_requise:
        return True
    return ValidationAcceptation.objects.filter(
        acceptation=acceptation, decision=DecisionAcceptation.VALIDEE
    ).exists()


@transaction.atomic
def decider_acceptation(
    acceptation: AcceptationRisque,
    *,
    decision: str,
    motif: str,
    by: User,
    reference_conseil: str = "",
) -> ValidationAcceptation:
    """Décision de l'autorité désignée ; un refus retire l'acceptation (journalisé)."""
    autorite = acceptation.validation_requise
    if autorite and (ROLE_DECIDEUR[autorite] != by.role or not by.is_active):
        raise PermissionDenied(MSG_DROIT_DECISION[autorite])
    ouvrir_plan(acceptation.mission)
    acceptation = relire(acceptation)
    if acceptation.deleted_at is not None:
        raise RegleMetierError("Cette acceptation a été retirée.")
    if not acceptation.validation_requise:
        raise RegleMetierError(MSG_SANS_VALIDATION)
    if ValidationAcceptation.objects.filter(acceptation=acceptation).exists():
        raise RegleMetierError(MSG_DEJA_DECIDEE)
    if decision not in DecisionAcceptation.values:
        msg = "Décision inconnue."
        raise refuser(msg, decision=msg)
    motif = motif.strip()
    if not motif:
        raise refuser(MSG_MOTIF_DECISION, motif=MSG_MOTIF_DECISION)
    reference_conseil = reference_conseil.strip()
    if autorite == ValidateurAcceptation.BOARD and not reference_conseil:
        raise refuser(MSG_REFERENCE_CONSEIL, reference_conseil=MSG_REFERENCE_CONSEIL)
    validation = ValidationAcceptation(
        acceptation=acceptation,
        niveau=autorite,
        decision=decision,
        par=by,
        le=timezone.now(),
        motif=motif,
        reference_conseil=reference_conseil,
    )
    enregistrer(validation, by=by, creation=True)
    if decision == DecisionAcceptation.REFUSEE:
        acceptation.soft_delete(by)
    constat = acceptation.recommandation.constat
    issue = "validée" if decision == DecisionAcceptation.VALIDEE else "refusée"
    notifier(
        [acceptation.auteur],
        type=TypeNotification.ACCEPTATION_DECIDEE,
        titre=f"Acceptation du risque {issue} : {constat.reference}",
        message=(
            f"Votre acceptation du risque (constat {constat.reference}) a été {issue}. "
            f"Motif : {motif}"
        )[:1000],
        lien=f"/missions/{acceptation.mission_id}/plan-actions",
        objet=acceptation,
        cle=f"acceptation-decidee:{acceptation.pk}",
    )
    return validation


@transaction.atomic
def retirer_acceptation(acceptation: AcceptationRisque, *, by: User) -> None:
    ouvrir_plan(acceptation.mission)
    acceptation = relire(acceptation)
    if by.role != Role.RAI and acceptation.auteur_id != by.pk:
        raise PermissionDenied(MSG_RETRAIT)
    acceptation.soft_delete(by)
