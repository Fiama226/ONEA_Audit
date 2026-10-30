"""Transitions du suivi d'une action (R2), commentaires et changement de responsable (R4).

Toutes les fonctions sont atomiques, verrouillent la mission puis le suivi, vérifient les droits
(`droits.exiger_action`) et journalisent un `EvenementSuivi`.
"""

from django.db import transaction
from django.utils import timezone

from apps.core.services import refuser
from apps.missions.models import AffectationMission, RoleMission
from apps.notifications.models import TypeNotification
from apps.users.models import Role, User

from ..models import EvenementSuivi, StatutSuivi, SuiviAction, TypeEvenementSuivi
from . import cloture, commun

MSG_PREUVE_REQUISE = (
    "Déposez au moins une preuve de mise en œuvre avant de déclarer l'action réalisée."
)


def _pour_compte(
    suivi: SuiviAction, by: User, texte: str, champ: str, **kw: bool
) -> tuple[str, User | None]:
    return commun.texte_pour_compte(suivi, by, texte, champ, **kw)


@transaction.atomic
def demarrer(suivi: SuiviAction, *, by: User, commentaire: str = "") -> SuiviAction:
    s = commun.preparer(suivi, by=by, code="DEMARRER")
    texte, pour = _pour_compte(s, by, commentaire, "commentaire")
    avant = s.statut
    s.demarrer()
    commun.appliquer_transition(
        s,
        by=by,
        type_evenement=TypeEvenementSuivi.DEMARRE,
        texte=texte,
        pour_compte_de=pour,
        statut_avant=avant,
    )
    return s


@transaction.atomic
def declarer_realisee(suivi: SuiviAction, *, commentaire: str, by: User) -> SuiviAction:
    s = commun.preparer(suivi, by=by, code="DECLARER_REALISEE")
    texte, pour = _pour_compte(s, by, commentaire, "commentaire", obligatoire=True)
    if not s.preuves.exists():
        raise refuser(MSG_PREUVE_REQUISE, preuves=MSG_PREUVE_REQUISE)
    avant = s.statut
    s.declarer_realisee()
    s.declaree_par = by
    s.declaree_le = timezone.now()
    evt = commun.appliquer_transition(
        s,
        by=by,
        type_evenement=TypeEvenementSuivi.DECLAREE_REALISEE,
        texte=texte,
        champs=("declaree_par", "declaree_le"),
        pour_compte_de=pour,
        statut_avant=avant,
    )
    commun.prevenir(
        s,
        evt,
        commun.chefs_de_mission(s),
        type_notification=TypeNotification.ACTION_DECLAREE,
        titre="Action déclarée réalisée",
        message=f"À vérifier — {commun.designation(s)}",
        par=by,
    )
    return s


@transaction.atomic
def proposer_abandon(suivi: SuiviAction, *, justification: str, by: User) -> SuiviAction:
    s = commun.preparer(suivi, by=by, code="PROPOSER_ABANDON")
    texte, pour = _pour_compte(s, by, justification, "justification", obligatoire=True)
    avant = s.statut
    s.proposer_abandon()
    s.justification_abandon = texte
    evt = commun.appliquer_transition(
        s,
        by=by,
        type_evenement=TypeEvenementSuivi.ABANDON_PROPOSE,
        texte=texte,
        champs=("justification_abandon",),
        pour_compte_de=pour,
        statut_avant=avant,
    )
    commun.prevenir(
        s,
        evt,
        commun.rai_actifs(),
        type_notification=TypeNotification.ABANDON_PROPOSE,
        titre="Abandon d'une action proposé",
        message=f"À décider — {commun.designation(s)}",
        par=by,
    )
    return s


@transaction.atomic
def verifier(suivi: SuiviAction, *, by: User, commentaire: str = "") -> SuiviAction:
    s = commun.preparer(suivi, by=by, code="VERIFIER")
    avant = s.statut
    s.verifier()
    s.verifiee_par = by
    s.verifiee_le = timezone.now()
    evt = commun.appliquer_transition(
        s,
        by=by,
        type_evenement=TypeEvenementSuivi.VERIFIEE,
        texte=commentaire.strip(),
        champs=("verifiee_par", "verifiee_le"),
        statut_avant=avant,
    )
    commun.prevenir(
        s,
        evt,
        commun.rai_actifs(),
        type_notification=TypeNotification.ACTION_VERIFIEE,
        titre="Action vérifiée",
        message=f"À clôturer — {commun.designation(s)}",
        par=by,
    )
    return s


@transaction.atomic
def rejeter(suivi: SuiviAction, *, motif: str, by: User) -> SuiviAction:
    s = commun.preparer(suivi, by=by, code="REJETER")
    motif = commun.exiger_texte(motif, "motif", "Le motif du rejet est obligatoire.")
    avant = s.statut
    s.rejeter()
    s.motif_dernier_rejet = motif
    s.verifiee_par = None
    s.verifiee_le = None
    if avant == StatutSuivi.ABANDON_PROPOSE:
        s.justification_abandon = ""
    evt = commun.appliquer_transition(
        s,
        by=by,
        type_evenement=TypeEvenementSuivi.REJETEE,
        texte=motif,
        champs=("motif_dernier_rejet", "verifiee_par", "verifiee_le", "justification_abandon"),
        statut_avant=avant,
    )
    commun.prevenir(
        s,
        evt,
        [s.responsable],
        type_notification=TypeNotification.ACTION_REJETEE,
        titre="Action rejetée",
        message=f"Motif : {motif[:300]} — {commun.designation(s)}",
        par=by,
    )
    return s


@transaction.atomic
def cloturer(suivi: SuiviAction, *, by: User, commentaire: str = "") -> SuiviAction:
    s = commun.preparer(suivi, by=by, code="CLOTURER")
    avant = s.statut
    s.cloturer()
    s.cloturee_par = by
    s.cloturee_le = timezone.now()
    evt = commun.appliquer_transition(
        s,
        by=by,
        type_evenement=TypeEvenementSuivi.CLOTUREE,
        texte=commentaire.strip(),
        champs=("cloturee_par", "cloturee_le"),
        statut_avant=avant,
    )
    commun.prevenir(
        s,
        evt,
        [s.responsable],
        type_notification=TypeNotification.ACTION_CLOTUREE,
        titre="Action clôturée",
        message=commun.designation(s),
        par=by,
    )
    cloture.proposer_cloture_si_complete(s.mission)
    return s


@transaction.atomic
def accepter_abandon(suivi: SuiviAction, *, commentaire: str, by: User) -> SuiviAction:
    s = commun.preparer(suivi, by=by, code="ACCEPTER_ABANDON")
    texte = commun.exiger_texte(commentaire, "commentaire", "Le commentaire est obligatoire.")
    avant = s.statut
    s.accepter_abandon()
    s.cloturee_par = by
    s.cloturee_le = timezone.now()
    evt = commun.appliquer_transition(
        s,
        by=by,
        type_evenement=TypeEvenementSuivi.ABANDON_ACCEPTE,
        texte=texte,
        champs=("cloturee_par", "cloturee_le"),
        statut_avant=avant,
    )
    commun.prevenir(
        s,
        evt,
        [s.responsable],
        type_notification=TypeNotification.ABANDON_DECIDE,
        titre="Abandon accepté",
        message=f"{commun.designation(s)}",
        par=by,
    )
    cloture.proposer_cloture_si_complete(s.mission)
    return s


@transaction.atomic
def rouvrir(suivi: SuiviAction, *, motif: str, by: User) -> SuiviAction:
    s = commun.preparer(suivi, by=by, code="ROUVRIR")
    motif = commun.exiger_texte(motif, "motif", "Le motif de la réouverture est obligatoire.")
    avant = s.statut
    s.rouvrir()
    s.cloturee_par = None
    s.cloturee_le = None
    s.verifiee_par = None
    s.verifiee_le = None
    commun.appliquer_transition(
        s,
        by=by,
        type_evenement=TypeEvenementSuivi.ROUVERTE,
        texte=motif,
        champs=("cloturee_par", "cloturee_le", "verifiee_par", "verifiee_le"),
        statut_avant=avant,
    )
    return s


@transaction.atomic
def commenter(suivi: SuiviAction, *, texte: str, by: User) -> EvenementSuivi:
    s = commun.preparer(suivi, by=by, code="COMMENTER")
    texte = commun.exiger_texte(texte, "texte", "Le commentaire est obligatoire.")
    s.derniere_activite_le = timezone.now()
    s.updated_by = by
    from apps.core.audit import actor_scope

    with actor_scope(by):
        s.save(update_fields=["derniere_activite_le", "updated_by", "updated_at"])
        return EvenementSuivi.journaliser(
            s, TypeEvenementSuivi.COMMENTAIRE, par=by, texte=texte, statut_avant=s.statut
        )


@transaction.atomic
def changer_responsable(suivi: SuiviAction, *, responsable: User, by: User) -> SuiviAction:
    s = commun.preparer(suivi, by=by, code="CHANGER_RESPONSABLE")
    msg = "Affectez d'abord cette personne à la mission comme audité."
    affecte = AffectationMission.objects.filter(
        mission_id=s.mission_id,
        utilisateur=responsable,
        role_mission=RoleMission.AUDITE,
    ).exists()
    if responsable.role != Role.AUDITE or not responsable.is_active or not affecte:
        raise refuser(msg, responsable=msg)
    ancien = s.responsable
    if ancien.pk == responsable.pk:
        return s
    s.responsable = responsable
    evt = commun.appliquer_transition(
        s,
        by=by,
        type_evenement=TypeEvenementSuivi.RESPONSABLE_CHANGE,
        texte=f"{ancien.nom_complet} → {responsable.nom_complet}",
        champs=("responsable",),
        statut_avant=s.statut,
        donnees={"ancien_id": ancien.pk, "nouveau_id": responsable.pk},
    )
    commun.prevenir(
        s,
        evt,
        [ancien, responsable],
        type_notification=TypeNotification.RESPONSABLE_CHANGE,
        titre="Responsable d'une action modifié",
        message=commun.designation(s),
        par=by,
    )
    return s
