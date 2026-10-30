"""Accès à l'API de la communication (D4, D11, D12, D13) : rôles et périmètre de lecture.

Ordre des refus : rôle global (403 ; ADMIN toujours, DG et AUDITE hors des actions de
`dg_actions` / `audite_actions` de la vue) -> mission ou objet invisible (404) -> droit (403) ->
contenu de la requête (400, dont `confirme` absent ou faux) -> règle métier, gel ou fenêtre
d'écriture (422, par les services).
Les droits eux-mêmes viennent de `droits.py` et des services : ce module ne fait que les
appliquer. L'audité et le DG ne voient jamais un rapport avant sa diffusion.
"""

from django.db.models import Q, QuerySet
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.constats.models import Constat
from apps.constats.permissions import constats_lisibles
from apps.missions.acces import missions_visibles, role_dans_mission
from apps.missions.models import Mission, RoleMission
from apps.users.models import Role, User

from .droits import peut_lire_rapport_interne, rapports_diffuses_visibles
from .models import (
    DestinataireDiffusion,
    Rapport,
    RapportProvisoire,
    ReponseRapport,
    StatutRapport,
)

STATUTS_DIFFUSES = (StatutRapport.DIFFUSE, StatutRapport.REMPLACE)


class CommunicationAccessPermission(BasePermission):
    """ADMIN refusé ; DG et AUDITE n'accèdent qu'aux actions que la vue leur ouvre."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not (user and user.is_authenticated and isinstance(user, User)):
            return False
        action = getattr(view, "action", None)
        if user.role == Role.DG:
            return action in getattr(view, "dg_actions", frozenset())
        if user.role == Role.AUDITE:
            return action in getattr(view, "audite_actions", frozenset())
        return user.role in (Role.RAI, Role.AUDITEUR)


def rapports_lisibles(user: User) -> QuerySet[Rapport]:
    """Rapports dont l'existence est connue de `user` (sinon 404).

    DG : les rapports diffusés. Autres : ceux de leurs missions visibles ; le droit de lire un
    rapport avant sa diffusion est contrôlé ensuite (403, `peut_lire`).
    """
    if user.role == Role.DG:
        return rapports_diffuses_visibles(user)
    return Rapport.objects.filter(mission__in=missions_visibles(user))


def peut_lire(user: User, rapport: Rapport) -> bool:
    """Un rapport diffusé se lit à tous ses lecteurs ; avant diffusion : équipe et RAI seulement."""
    if rapport.statut in STATUTS_DIFFUSES:
        return True
    return peut_lire_rapport_interne(user, rapport.mission)


def provisoires_lisibles(user: User) -> QuerySet[RapportProvisoire]:
    """Équipe et audité affecté ; le DG n'y accède pas (rôle refusé en amont)."""
    return RapportProvisoire.objects.filter(mission__in=missions_visibles(user))


def reponses_lisibles(user: User) -> QuerySet[ReponseRapport]:
    """Équipe : toutes celles des missions visibles ; audité : les siennes seulement."""
    base = ReponseRapport.objects.filter(mission__in=missions_visibles(user))
    return base.filter(auteur=user) if user.role == Role.AUDITE else base


def constats_du_provisoire(user: User) -> QuerySet[Constat]:
    """Constats lisibles (l'audité : ceux de sa direction seulement)."""
    return constats_lisibles(user)


def destinataires_lisibles(user: User) -> QuerySet[DestinataireDiffusion]:
    """RAI : toutes les lignes ; chef de mission : celles de ses missions ; autres : la leur,
    une fois le rapport diffusé."""
    if user.role == Role.RAI:
        return DestinataireDiffusion.objects.filter(mission__in=missions_visibles(user))
    sa_ligne = Q(utilisateur=user, rapport__in=rapports_diffuses_visibles(user))
    chef = Q(
        mission_id__in=_missions_dirigees(user),
    )
    if user.role == Role.AUDITEUR:
        return DestinataireDiffusion.objects.filter(sa_ligne | chef)
    return DestinataireDiffusion.objects.filter(sa_ligne)


def _missions_dirigees(user: User) -> QuerySet[Mission]:
    return missions_visibles(user).filter(
        affectations__utilisateur=user,
        affectations__deleted_at__isnull=True,
        affectations__role_mission=RoleMission.CHEF_MISSION,
    )


def audite_affecte(user: User, mission: Mission) -> bool:
    return user.role == Role.AUDITE and role_dans_mission(user, mission) == RoleMission.AUDITE


def peut_telecharger(user: User, mission: Mission) -> bool:
    """RAI, intervenants, audité affecté, DG (le rapport doit en outre être diffusé)."""
    if user.role in (Role.RAI, Role.DG):
        return True
    if user.role == Role.AUDITEUR:
        return peut_lire_rapport_interne(user, mission)
    return audite_affecte(user, mission)
