"""Notifications des intervenants et des audités pendant la mission (D5).

Chaque envoi porte une clé de dédoublonnage : rejouer l'événement ne crée aucune seconde ligne.
L'auteur de l'action n'est jamais notifié. Les comptes inactifs sont ignorés par `notifier`.
"""

from collections.abc import Iterable

from apps.notifications.models import TypeNotification
from apps.notifications.services import notifier
from apps.users.models import User

from .models import AffectationMission, Mission, Reunion, RoleMission


def _lien(mission: Mission, suite: str = "") -> str:
    return f"/missions/{mission.pk}{suite}"


def _sans_auteur(users: Iterable[User], auteur: User) -> list[User]:
    return [u for u in users if u.pk != auteur.pk]


def _utilisateurs(mission: Mission, *, roles: tuple[str, ...] | None = None) -> list[User]:
    affectations = AffectationMission.objects.filter(mission=mission).select_related("utilisateur")
    if roles is not None:
        affectations = affectations.filter(role_mission__in=roles)
    return [a.utilisateur for a in affectations]


def audites(mission: Mission) -> list[User]:
    return _utilisateurs(mission, roles=(RoleMission.AUDITE,))


def notifier_affectation(affectation: AffectationMission, *, by: User) -> None:
    """L'intervenant affecté est prévenu ; l'audité l'est à l'émission de l'ordre de mission."""
    mission = affectation.mission
    utilisateur = affectation.utilisateur
    if utilisateur.pk == by.pk:
        return
    if affectation.role_mission == RoleMission.AUDITE:
        if mission.ordre_mission_emis_le is not None:
            _notifier_ordre(mission, [utilisateur])
        return
    notifier(
        [utilisateur],
        type=TypeNotification.AFFECTATION_MISSION,
        titre="Vous êtes affecté à une mission",
        message=f"{mission.reference} : {mission.titre[:200]} "
        f"({affectation.get_role_mission_display()}).",
        lien=_lien(mission),
        objet=mission,
        cle=f"AFFECTATION:{affectation.pk}",
    )


def _notifier_ordre(mission: Mission, destinataires: Iterable[User]) -> None:
    for user in destinataires:
        notifier(
            [user],
            type=TypeNotification.ORDRE_MISSION_EMIS,
            titre="Ordre de mission émis",
            message=f"{mission.reference} : {mission.titre[:200]}. "
            "La mission est ouverte : consultez-la pour connaître ce qui vous est demandé.",
            lien=_lien(mission),
            objet=mission,
            cle=f"ORDRE_MISSION:{mission.pk}:{user.pk}",
        )


def notifier_ordre_emis(mission: Mission, *, by: User) -> None:
    """Toute l'équipe, audités compris, est informée de l'ouverture de la mission."""
    _notifier_ordre(mission, _sans_auteur(_utilisateurs(mission), by))


def notifier_reunion(reunion: Reunion, participants: Iterable[User], *, by: User) -> None:
    """Convoque les participants (une seule fois chacun) ; l'auteur n'est pas notifié."""
    mission = reunion.mission
    quand = reunion.date.strftime("%d/%m/%Y à %H:%M")
    for user in _sans_auteur(participants, by):
        notifier(
            [user],
            type=TypeNotification.REUNION_CONVOQUEE,
            titre="Vous êtes convoqué à une réunion",
            message=f"{mission.reference} : réunion {reunion.get_type_display().lower()} "
            f"le {quand}.",
            lien=_lien(mission, "/reunions"),
            objet=reunion,
            cle=f"REUNION:{reunion.pk}:{user.pk}",
        )


def notifier_referentiel_a_valider(mission: Mission, *, by: User) -> None:
    """Étape VI démarrée : les audités sont invités à donner leur avis sur le référentiel."""
    for user in _sans_auteur(audites(mission), by):
        notifier(
            [user],
            type=TypeNotification.REFERENTIEL_A_VALIDER,
            titre="Référentiel d'audit à valider",
            message=f"{mission.reference} : votre avis est attendu sur le référentiel d'audit.",
            lien=_lien(mission, "/etapes/6"),
            objet=mission,
            cle=f"REFERENTIEL_VI:{mission.pk}:{user.pk}",
        )
