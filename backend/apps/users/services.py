"""Account administration services (ADMIN only; permissions are enforced by the views).

Every write runs in a transaction, under the audit actor, on a row re-read with
`select_for_update`. No network call is made here: the Keycloak propagation is done by
the caller once the transaction has committed.
"""

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.audit import actor_scope
from apps.core.exceptions import RegleMetierError
from apps.referentiel.models import Direction

from .models import KeycloakSyncStatut, Role, User

PROFILE_FIELDS = frozenset({"matricule", "direction_code", "fonction"})
# Fields coming from the directory claims; editing one makes the profile local (D4).
SYNCED_FIELDS = frozenset({"direction_code", "fonction"})

COMPTE_PERSONNEL = "Vous ne pouvez pas désactiver votre propre compte."
DERNIER_ADMIN = "Impossible de désactiver le dernier administrateur actif de la plateforme."
DEJA_DESACTIVE = "Ce compte est déjà désactivé."
DEJA_ACTIF = "Ce compte est déjà actif."
DEJA_SYNCHRONISE = "Le profil est déjà synchronisé avec l'annuaire."
MATRICULE_PRIS = "Ce matricule est déjà attribué à un autre utilisateur."
DIRECTION_INCONNUE = (
    "Direction inconnue : choisissez une direction ou un département du référentiel."
)

_MAX_LENGTHS = {"matricule": 32, "fonction": 128}


def mettre_a_jour_tutoriel(user: User, *, action: str, version: int) -> User:
    """Mémorise l'état du tutoriel d'accueil de l'utilisateur lui-même (donnée de confort,
    hors piste d'audit métier). `terminer` et `ignorer` sont équivalents côté serveur."""
    with transaction.atomic():
        compte = _lock(user)
        if action == "reinitialiser":
            compte.tutoriel_version_vue = None
            compte.tutoriel_termine_le = None
        else:
            compte.tutoriel_version_vue = version
            compte.tutoriel_termine_le = timezone.now()
        compte.save(update_fields=["tutoriel_version_vue", "tutoriel_termine_le"])
    return compte


def direction_existe(code: str) -> bool:
    return bool(code) and Direction.objects.filter(code=code, deleted_at__isnull=True).exists()


def _lock(compte: User) -> User:
    return User.objects.select_for_update().get(pk=compte.pk)


def _mark_pending(user: User, fields: list[str]) -> None:
    """Flag the account for propagation to Keycloak (only when it is linked)."""
    if user.keycloak_id is not None:
        user.keycloak_sync_statut = KeycloakSyncStatut.EN_ATTENTE
        user.keycloak_sync_erreur = ""
        user.keycloak_sync_tentatives = 0
        user.keycloak_sync_manuel = False
        fields += [
            "keycloak_sync_statut",
            "keycloak_sync_erreur",
            "keycloak_sync_tentatives",
            "keycloak_sync_manuel",
        ]


def modifier_profil(compte: User, *, changes: dict[str, str], by: User) -> User:
    unknown = set(changes) - PROFILE_FIELDS
    if unknown:
        raise ValueError(f"Unsupported profile fields: {sorted(unknown)}")
    values = {k: v.strip() for k, v in changes.items()}
    for field, limit in _MAX_LENGTHS.items():
        if field in values and len(values[field]) > limit:
            raise RegleMetierError(
                "Données invalides.",
                {field: [f"Assurez-vous que ce champ comporte au plus {limit} caractères."]},
            )
    with transaction.atomic(), actor_scope(by):
        user = _lock(compte)
        if "direction_code" in values:
            new_code = values["direction_code"]
            if new_code != user.direction_code and new_code and not direction_existe(new_code):
                raise RegleMetierError(
                    "Données invalides.", {"direction_code": [DIRECTION_INCONNUE]}
                )
        fields: list[str] = []
        for field, value in values.items():
            if getattr(user, field) != value:
                if field in SYNCED_FIELDS:
                    user.profil_gere_localement = True
                    if "profil_gere_localement" not in fields:
                        fields.append("profil_gere_localement")
                setattr(user, field, value)
                fields.append(field)
        if fields:
            try:
                with transaction.atomic():
                    user.save(update_fields=fields)
            except IntegrityError as exc:
                raise RegleMetierError(
                    "Données invalides.", {"matricule": [MATRICULE_PRIS]}
                ) from exc
        return user


def desactiver(compte: User, *, motif: str, by: User) -> User:
    with transaction.atomic(), actor_scope(by):
        # Lock every active admin plus the target, in pk order, so that two crossed
        # deactivations serialize instead of both succeeding.
        locked = list(
            User.objects.select_for_update()
            .filter(Q(role=Role.ADMIN, is_active=True) | Q(pk=compte.pk))
            .order_by("pk")
        )
        user = next(u for u in locked if u.pk == compte.pk)
        if user.pk == by.pk:
            raise RegleMetierError(COMPTE_PERSONNEL)
        if not user.is_active:
            raise RegleMetierError(DEJA_DESACTIVE)
        if user.role == Role.ADMIN and not any(
            u.pk != user.pk and u.role == Role.ADMIN and u.is_active for u in locked
        ):
            raise RegleMetierError(DERNIER_ADMIN)
        user.is_active = False
        user.desactive_le = timezone.now()
        user.desactive_par = by
        user.motif_desactivation = motif.strip()
        fields = ["is_active", "desactive_le", "desactive_par", "motif_desactivation"]
        _mark_pending(user, fields)
        user.save(update_fields=fields)
        return user


def reactiver(compte: User, *, by: User) -> User:
    with transaction.atomic(), actor_scope(by):
        user = _lock(compte)
        if user.is_active:
            raise RegleMetierError(DEJA_ACTIF)
        user.is_active = True
        user.desactive_le = None
        user.desactive_par = None
        user.motif_desactivation = ""
        fields = ["is_active", "desactive_le", "desactive_par", "motif_desactivation"]
        _mark_pending(user, fields)
        user.save(update_fields=fields)
        return user


def resynchroniser_profil(compte: User, *, by: User) -> User:
    """Give direction and function back to the directory (applied at next login)."""
    with transaction.atomic(), actor_scope(by):
        user = _lock(compte)
        if not user.profil_gere_localement:
            raise RegleMetierError(DEJA_SYNCHRONISE)
        user.profil_gere_localement = False
        user.save(update_fields=["profil_gere_localement"])
        return user


def actions_compte(compte: User, par: User) -> dict[str, bool]:
    lie = compte.keycloak_id is not None
    return {
        "modifier_profil": True,
        "desactiver": compte.is_active and compte.pk != par.pk,
        "reactiver": not compte.is_active,
        "resynchroniser_profil": compte.profil_gere_localement,
        "relancer_synchro_keycloak": lie
        and compte.keycloak_sync_statut
        in (KeycloakSyncStatut.EN_ATTENTE, KeycloakSyncStatut.ECHEC),
    }
