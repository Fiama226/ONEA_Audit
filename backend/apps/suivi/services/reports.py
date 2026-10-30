"""Demandes de report d'échéance (R5) : demande, acceptation, refus.

Ordre de verrouillage : mission, puis suivi, puis demande. Accepter un report change l'échéance
courante et ouvre de fait un nouveau cycle de relances (la clé d'idempotence d'une relance
contient l'échéance de référence).
"""

import datetime
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.audit import actor_scope
from apps.core.services import enregistrer, refuser, relire
from apps.missions.gardes import verrouiller_mission
from apps.notifications.models import TypeNotification
from apps.notifications.services import notifier
from apps.users.models import Role, User

from .. import droits
from ..models import (
    DemandeReport,
    EvenementSuivi,
    StatutDemandeReport,
    StatutSuivi,
    SuiviAction,
    TypeEvenementSuivi,
)
from ._compte import pour_compte

MSG_MOTIF = "Le motif est obligatoire."
MSG_COMMENTAIRE = "Le commentaire est obligatoire."
MSG_POSTERIEURE = "La nouvelle échéance doit être postérieure à l'échéance actuelle."
MSG_EN_ATTENTE = "Une demande de report est déjà en attente pour cette action."
MSG_STATUT = "Un report ne peut être demandé que pour une action à lancer ou en cours."
MSG_STATUT_ACCEPTATION = (
    "Cette action n'est plus à lancer ni en cours : le report ne peut être accepté."
)
MSG_DEJA_DECIDEE = "Cette demande de report a déjà été traitée."
STATUTS_REPORTABLES: frozenset[str] = frozenset({StatutSuivi.A_LANCER, StatutSuivi.EN_COURS})


def _lien(suivi: SuiviAction) -> str:
    return f"/suivi/actions/{suivi.pk}"


def _verrouiller(suivi: SuiviAction) -> SuiviAction:
    verrouiller_mission(suivi.mission_id)
    return relire(suivi)


def _message(suivi: SuiviAction, debut: str) -> str:
    action = str(suivi.action.libelle)[:600]
    return f"{debut} Mission {suivi.mission.reference}, action : {action}."[:1000]


def _rai_actifs() -> list[User]:
    return list(User.objects.filter(role=Role.RAI, is_active=True, desactive_le__isnull=True))


def demander_report(
    suivi: SuiviAction, *, nouvelle_echeance: datetime.date, motif: str, by: User
) -> DemandeReport:
    droits.exiger_operer_pour_responsable(by, suivi)
    motif = motif.strip()
    if not motif:
        raise refuser(MSG_MOTIF, motif=MSG_MOTIF)
    with transaction.atomic():
        suivi = _verrouiller(suivi)
        droits.exiger_operer_pour_responsable(by, suivi)  # de nouveau, sous verrou
        if suivi.statut not in STATUTS_REPORTABLES:
            raise refuser(MSG_STATUT)
        if nouvelle_echeance <= suivi.echeance:
            raise refuser(MSG_POSTERIEURE, nouvelle_echeance=MSG_POSTERIEURE)
        if DemandeReport.objects.filter(
            suivi=suivi, statut=StatutDemandeReport.EN_ATTENTE
        ).exists():
            raise refuser(MSG_EN_ATTENTE)
        texte, pour = pour_compte(suivi, by, motif)
        demande = DemandeReport(
            suivi=suivi,
            mission_id=suivi.mission_id,
            echeance_actuelle=suivi.echeance,
            nouvelle_echeance=nouvelle_echeance,
            motif=motif,
            demandee_par=by,
        )
        enregistrer(demande, by=by, creation=True)
        EvenementSuivi.journaliser(
            suivi,
            TypeEvenementSuivi.REPORT_DEMANDE,
            par=by,
            pour_compte_de=pour,
            texte=texte,
            statut_avant=suivi.statut,
            donnees={
                "demande": str(demande.pk),
                "echeance_actuelle": suivi.echeance.isoformat(),
                "nouvelle_echeance": nouvelle_echeance.isoformat(),
            },
        )
        notifier(
            _rai_actifs(),
            type=TypeNotification.REPORT_DEMANDE,
            titre="Report d'échéance demandé",
            message=_message(suivi, f"Nouvelle échéance demandée : {nouvelle_echeance:%d/%m/%Y}."),
            lien=_lien(suivi),
            objet=demande,
            cle=f"report-demande-{demande.pk}",
        )
    return demande


def _decider(
    demande: DemandeReport,
    *,
    by: User,
    commentaire: str,
    accepter: bool,
) -> tuple[DemandeReport, SuiviAction]:
    """Sous verrous : relit la demande, la clôt et renvoie le suivi verrouillé."""
    suivi = _verrouiller(demande.suivi)
    demande = relire(demande)
    droits.exiger_decideur_report(by)
    if demande.statut != StatutDemandeReport.EN_ATTENTE:
        raise refuser(MSG_DEJA_DECIDEE)
    if accepter:
        if suivi.statut not in STATUTS_REPORTABLES:
            raise refuser(MSG_STATUT_ACCEPTATION)
        if demande.nouvelle_echeance <= suivi.echeance:
            raise refuser(MSG_POSTERIEURE)
    demande.statut = StatutDemandeReport.ACCEPTEE if accepter else StatutDemandeReport.REFUSEE
    demande.decidee_par = by
    demande.decidee_le = timezone.now()
    demande.commentaire_decision = commentaire
    enregistrer(demande, by=by)
    return demande, suivi


def accepter_report(demande: DemandeReport, *, by: User, commentaire: str = "") -> DemandeReport:
    droits.exiger_decideur_report(by)
    with transaction.atomic():
        demande, suivi = _decider(demande, by=by, commentaire=commentaire.strip(), accepter=True)
        avant = suivi.echeance
        suivi.echeance = demande.nouvelle_echeance
        suivi.nombre_reports += 1
        suivi.derniere_activite_le = timezone.now()
        suivi.updated_by = by
        with actor_scope(by):
            suivi.save(
                update_fields=[
                    "echeance",
                    "nombre_reports",
                    "derniere_activite_le",
                    "updated_by",
                    "updated_at",
                ]
            )
        _suite(demande, suivi, by, commentaire.strip(), TypeEvenementSuivi.REPORT_ACCEPTE, avant)
    return demande


def refuser_report(demande: DemandeReport, *, commentaire: str, by: User) -> DemandeReport:
    droits.exiger_decideur_report(by)
    commentaire = commentaire.strip()
    if not commentaire:
        raise refuser(MSG_COMMENTAIRE, commentaire=MSG_COMMENTAIRE)
    with transaction.atomic():
        demande, suivi = _decider(demande, by=by, commentaire=commentaire, accepter=False)
        _suite(demande, suivi, by, commentaire, TypeEvenementSuivi.REPORT_REFUSE, suivi.echeance)
    return demande


def _suite(
    demande: DemandeReport,
    suivi: SuiviAction,
    by: User,
    commentaire: str,
    type_evenement: str,
    echeance_avant: datetime.date,
) -> None:
    """Événement du journal et notification du responsable (R10)."""
    donnees: dict[str, Any] = {
        "demande": str(demande.pk),
        "echeance_avant": echeance_avant.isoformat(),
        "echeance_apres": suivi.echeance.isoformat(),
    }
    EvenementSuivi.journaliser(
        suivi,
        type_evenement,
        par=by,
        texte=commentaire,
        statut_avant=suivi.statut,
        donnees=donnees,
    )
    accepte = type_evenement == TypeEvenementSuivi.REPORT_ACCEPTE
    debut = (
        f"Report accepté : nouvelle échéance le {suivi.echeance:%d/%m/%Y}."
        if accepte
        else "Report refusé."
    )
    notifier(
        [suivi.responsable],
        type=TypeNotification.REPORT_DECIDE,
        titre="Report d'échéance accepté" if accepte else "Report d'échéance refusé",
        message=_message(suivi, debut),
        lien=_lien(suivi),
        objet=demande,
        cle=f"report-decide-{demande.pk}",
    )
