"""Briques communes des services de suivi : verrous, règle du retard, notifications.

Ordre de verrouillage de toute écriture : mission, puis ligne de suivi (HANDOFF §5).
"""

from collections.abc import Iterable
from datetime import date

from django.db.models import Q
from django.http import Http404
from django.utils import timezone

from apps.core.audit import actor_scope
from apps.core.services import refuser
from apps.missions.gardes import verrouiller_mission
from apps.missions.models import AffectationMission, RoleMission
from apps.notifications.services import notifier
from apps.users.models import Role, User

from .. import droits
from ..models import STATUTS_RELANCABLES, EvenementSuivi, SuiviAction


def aujourd_hui() -> date:
    return timezone.localdate()


def en_retard(suivi: SuiviAction, aujourd_hui: date) -> bool:
    """Relançable et échéance dépassée : le jour de l'échéance n'est pas un retard (R2)."""
    return suivi.statut in STATUTS_RELANCABLES and suivi.echeance < aujourd_hui


def jours_retard(suivi: SuiviAction, aujourd_hui: date) -> int | None:
    return (aujourd_hui - suivi.echeance).days if en_retard(suivi, aujourd_hui) else None


def EXPR_EN_RETARD(aujourd_hui: date, prefixe: str = "") -> Q:  # noqa: N802
    """Même règle que `en_retard`, pour les QuerySets ; `prefixe` : chemin depuis un autre modèle
    (ex. `suivis__`). Source unique du retard : l'API et les agrégats la partagent."""
    return Q(**{f"{prefixe}statut__in": STATUTS_RELANCABLES, f"{prefixe}echeance__lt": aujourd_hui})


def verrouiller_suivi(suivi: SuiviAction) -> SuiviAction:
    """Relit le suivi sous verrou (transaction requise), après la mission."""
    verrouille: SuiviAction | None = (
        SuiviAction.objects.select_for_update().filter(pk=suivi.pk).first()
    )
    if verrouille is None:
        raise Http404("Action introuvable.")
    return verrouille


def preparer(suivi: SuiviAction, *, by: User, code: str) -> SuiviAction:
    """Verrouille mission puis suivi, contrôle les droits et l'état ; renvoie le suivi frais."""
    verrouiller_mission(suivi.mission_id)
    verrouille = verrouiller_suivi(suivi)
    droits.exiger_action(by, verrouille, code)
    return verrouille


def exiger_texte(valeur: str, champ: str, message: str) -> str:
    texte = (valeur or "").strip()
    if not texte:
        raise refuser(message, **{champ: message})
    return texte


def texte_pour_compte(
    suivi: SuiviAction, by: User, commentaire: str, champ: str, *, obligatoire: bool = False
) -> tuple[str, User | None]:
    """R3 : le RAI qui agit pour le responsable doit commenter ; l'événement le trace."""
    texte = (commentaire or "").strip()
    if by.role == Role.RAI and suivi.responsable_id != by.pk:
        texte = exiger_texte(
            texte, champ, "Précisez pourquoi vous saisissez cette opération pour le responsable."
        )
        responsable = suivi.responsable
        return (
            f"Saisi par le RAI pour le compte de {responsable.nom_complet} : {texte}",
            responsable,
        )
    if obligatoire:
        texte = exiger_texte(texte, champ, "Ce champ est obligatoire.")
    return texte, None


def appliquer_transition(
    suivi: SuiviAction,
    *,
    by: User,
    type_evenement: str,
    texte: str = "",
    champs: Iterable[str] = (),
    pour_compte_de: User | None = None,
    donnees: dict[str, object] | None = None,
    statut_avant: str = "",
) -> EvenementSuivi:
    """Sauvegarde le suivi (champs modifiés) puis journalise l'événement."""
    suivi.derniere_activite_le = timezone.now()
    suivi.updated_by = by
    with actor_scope(by):
        suivi.save(
            update_fields=[
                "statut",
                "derniere_activite_le",
                "updated_by",
                "updated_at",
                *champs,
            ]
        )
        return EvenementSuivi.journaliser(
            suivi,
            type_evenement,
            par=by,
            texte=texte,
            donnees=donnees,
            statut_avant=statut_avant,
            pour_compte_de=pour_compte_de,
        )


def lien(suivi: SuiviAction) -> str:
    return f"/recommandations/actions/{suivi.pk}"


def rai_actifs() -> list[User]:
    return list(User.objects.filter(role=Role.RAI, is_active=True, desactive_le__isnull=True))


def chefs_de_mission(suivi: SuiviAction) -> list[User]:
    affectations = AffectationMission.objects.filter(
        mission_id=suivi.mission_id, role_mission=RoleMission.CHEF_MISSION
    ).select_related("utilisateur")
    return [a.utilisateur for a in affectations]


def prevenir(
    suivi: SuiviAction,
    evenement: EvenementSuivi,
    destinataires: Iterable[User],
    *,
    type_notification: str,
    titre: str,
    message: str,
    par: User | None,
) -> int:
    """R10 : notification dans la transaction ; l'auteur de l'événement n'est jamais notifié."""
    cibles = [u for u in destinataires if par is None or u.pk != par.pk]
    return notifier(
        cibles,
        type=type_notification,
        titre=titre,
        message=message,
        lien=lien(suivi),
        objet=suivi,
        cle=f"{type_notification}:{evenement.pk}",
    )


def designation(suivi: SuiviAction) -> str:
    """Référence de mission et libellé de l'action, sans texte de constat (R9)."""
    libelle = suivi.action.libelle
    court = libelle if len(libelle) <= 120 else f"{libelle[:119]}…"
    return f"{suivi.mission.reference} : {court}"
