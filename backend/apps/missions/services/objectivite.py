"""Contrôle d'objectivité des intervenants (Normes IIA 2024, 2.2), selon la règle de gouvernance.

Situations détectées pour un intervenant (chef de mission, auditeur, superviseur) :

1. son compte relève d'une entité auditée par la mission (direction du compte) ;
2. il a été audité d'une de ces entités pendant la durée de refroidissement (affectation en
   tant qu'audité : il y exerçait des responsabilités) ;
3. pour une mission d'assurance, il a conduit une mission de conseil sur une de ces entités
   pendant la durée de refroidissement.

Mode blocage : l'affectation (ou l'émission de l'ordre) est refusée. Mode avertissement :
l'affectation passe, la situation est écrite sur l'affectation (`alerte_objectivite`, tracée
par le journal d'audit) et le RAI est notifié. Règle désactivée : aucun contrôle.
"""

import calendar
from datetime import datetime

from django.utils import timezone

from apps.core.services import enregistrer, refuser
from apps.gouvernance import regles_gouvernance
from apps.notifications.models import TypeNotification
from apps.notifications.services import notifier
from apps.users.models import Role, User

from ..models import (
    ROLES_INTERVENANTS,
    AffectationMission,
    Mission,
    RoleMission,
    StatutMission,
    TypeMission,
)

PREFIXE = "Contrôle d'objectivité (Normes IIA 2.2) : "


def _mois_avant(maintenant: datetime, mois: int) -> datetime:
    annee, reste = divmod(maintenant.month - 1 - mois, 12)
    annee += maintenant.year
    mois_cible = reste + 1
    jour = min(maintenant.day, calendar.monthrange(annee, mois_cible)[1])
    return maintenant.replace(year=annee, month=mois_cible, day=jour)


def _nom(user: User) -> str:
    return user.get_full_name() or user.username


def conflits(
    mission: Mission, utilisateur: User, *, refroidissement: int | None = None
) -> list[str]:
    """Situations qui altèrent l'objectivité de `utilisateur` sur `mission` (vide si aucune)."""
    if refroidissement is None:
        refroidissement = regles_gouvernance.objectivity().refroidissement_mois
    entites = list(mission.entites.all())
    if not entites:
        return []
    messages: list[str] = []
    nom = _nom(utilisateur)
    propre = next((e for e in entites if e.code and e.code == utilisateur.direction_code), None)
    if propre is not None:
        messages.append(f"{nom} relève de l'entité auditée « {propre.libelle} ».")
    if refroidissement <= 0:
        return messages
    depuis = _mois_avant(timezone.now(), refroidissement)
    passees = (
        AffectationMission.objects.filter(
            utilisateur=utilisateur,
            created_at__gte=depuis,
            mission__entites__in=entites,
            mission__deleted_at__isnull=True,
        )
        .exclude(mission=mission)
        .exclude(mission__statut=StatutMission.ANNULEE)
        .select_related("mission")
        .distinct()
        .order_by("created_at")
    )
    for affectation in passees:
        ancienne = affectation.mission
        reference = ancienne.reference or ancienne.titre
        if affectation.role_mission == RoleMission.AUDITE:
            messages.append(
                f"{nom} a été audité(e) de la même entité (mission {reference}) il y a moins de "
                f"{refroidissement} mois."
            )
        elif (
            mission.type == TypeMission.ASSURANCE
            and ancienne.type == TypeMission.CONSEIL
            and affectation.role_mission in ROLES_INTERVENANTS
        ):
            messages.append(
                f"{nom} a conduit une mission de conseil sur la même entité (mission "
                f"{reference}) il y a moins de {refroidissement} mois."
            )
    return messages


def _notifier_rai(mission: Mission, alerte: str, by: User) -> None:
    rais = User.objects.filter(role=Role.RAI, is_active=True).exclude(pk=by.pk)
    notifier(
        rais,
        type=TypeNotification.ALERTE_OBJECTIVITE,
        titre=f"Alerte d'objectivité : {mission.reference or mission.titre}",
        message=alerte[:1000],
        lien=f"/missions/{mission.pk}/equipe",
        objet=mission,
        cle=f"objectivite:{mission.pk}:{timezone.now().isoformat()}",
    )


def controler_affectation(mission: Mission, utilisateur: User, role_mission: str) -> str:
    """Avant d'affecter un intervenant : lève en mode blocage, renvoie l'alerte (ou "")."""
    regle = regles_gouvernance.objectivity()
    if not regle.actif or role_mission not in ROLES_INTERVENANTS:
        return ""
    messages = conflits(mission, utilisateur, refroidissement=regle.refroidissement_mois)
    if not messages:
        return ""
    texte = PREFIXE + " ".join(messages)
    if regle.bloquant:
        raise refuser(texte, utilisateur=texte)
    return texte


def signaler(affectation: AffectationMission, alerte: str, by: User) -> None:
    """Mode avertissement : notifie le RAI de l'alerte posée sur une affectation."""
    if alerte:
        _notifier_rai(affectation.mission, alerte, by)


def controler_equipe(mission: Mission, *, by: User) -> None:
    """À l'émission de l'ordre : refait le contrôle pour tous les intervenants (les entités ont
    pu changer depuis l'affectation). Blocage : refus listant les situations ; avertissement :
    alertes mises à jour sur les affectations."""
    regle = regles_gouvernance.objectivity()
    if not regle.actif:
        return
    affectations = list(
        AffectationMission.objects.filter(
            mission=mission, role_mission__in=ROLES_INTERVENANTS
        ).select_related("utilisateur", "mission")
    )
    alertes = {
        a.pk: conflits(mission, a.utilisateur, refroidissement=regle.refroidissement_mois)
        for a in affectations
    }
    if regle.bloquant:
        messages = [m for a in affectations for m in alertes[a.pk]]
        if messages:
            texte = PREFIXE + " ".join(messages)
            raise refuser(texte, equipe=texte)
        return
    for affectation in affectations:
        texte = PREFIXE + " ".join(alertes[affectation.pk]) if alertes[affectation.pk] else ""
        if texte != affectation.alerte_objectivite:
            affectation.alerte_objectivite = texte
            enregistrer(affectation, by=by)
            signaler(affectation, texte, by)
