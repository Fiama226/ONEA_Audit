"""Account administration services (ADMIN only; permissions are enforced by the views).

Every write runs in a transaction, under the audit actor, on a row re-read with
`select_for_update`. No network call is made here: the Keycloak propagation is done by
the caller once the transaction has committed. The in-app account actions (creation,
password reset, login-code removal) never touch Keycloak: their emails go out after the
commit, and a temporary password never reaches the audit trail or the logs.
"""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any

from django.contrib.auth.base_user import BaseUserManager
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.audit import actor_scope
from apps.core.exceptions import RegleMetierError
from apps.referentiel.models import Direction

from .auth_services import generer_mot_de_passe_temporaire, logger_securite, terminer_sessions
from .courriels import envoyer_bienvenue, envoyer_mot_de_passe_reinitialise
from .models import CodeOtp, KeycloakSyncStatut, ObjetOtp, OrigineCompte, Role, User

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

# A temporary password (creation or reset) is only good for this long, and must be changed.
DUREE_MOT_DE_PASSE_TEMPORAIRE = timedelta(hours=72)
CHAMPS_CREATION = frozenset({"username", "email", "first_name", "last_name", "role"}) | (
    PROFILE_FIELDS
)
DONNEES_INVALIDES = "Données invalides."
ROLE_OBLIGATOIRE = "Le rôle est obligatoire."
IDENTIFIANT_OBLIGATOIRE = "L'identifiant est obligatoire."
IDENTIFIANT_PRIS = "Cet identifiant est déjà utilisé."
COURRIEL_PRIS = "Cette adresse de courriel est déjà utilisée par un autre compte."
CREATION_CONCURRENTE = "Un compte avec cet identifiant ou ce matricule vient d'être créé."
REINITIALISATION_DESACTIVE = (
    "Ce compte est désactivé : réactivez-le avant de réinitialiser son mot de passe."
)
PROPRE_MOT_DE_PASSE = "Pour votre propre compte, utilisez « Changer mon mot de passe »."
PROPRE_OTP = "Pour votre propre compte, gérez le code de connexion depuis « Mon compte »."
OTP_DEJA_DESACTIVE = "Le code de connexion par courriel est déjà désactivé sur ce compte."

# Values of `additional_data["action"]` on the audit entries of the account actions.
ACTION_CREATION = "creation_compte"
ACTION_REINITIALISATION = "reinitialisation_mot_de_passe"
ACTION_DESACTIVATION_OTP = "desactivation_otp"


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


@contextmanager
def _action_auditee(user: User, action: str) -> Iterator[None]:
    """Name the business action on the audit entry written by the save(s) in the block."""
    user.action_audit = action
    try:
        yield
    finally:
        user.action_audit = None


def _poser_mot_de_passe_temporaire(user: User, mot_de_passe: str, now: datetime) -> list[str]:
    """Temporary password: must be changed at next login, expires in 72 h, lifts the lock."""
    user.set_password(mot_de_passe)
    user.doit_changer_mot_de_passe = True
    user.mot_de_passe_expire_le = now + DUREE_MOT_DE_PASSE_TEMPORAIRE
    user.echecs_connexion = 0
    user.verrouille_jusqu_a = None
    return [
        "password",
        "doit_changer_mot_de_passe",
        "mot_de_passe_expire_le",
        "echecs_connexion",
        "verrouille_jusqu_a",
    ]


def _valeurs_creation(donnees: Mapping[str, Any]) -> dict[str, str]:
    unknown = set(donnees) - CHAMPS_CREATION
    if unknown:
        raise ValueError(f"Unsupported account fields: {sorted(unknown)}")
    valeurs = {k: str(v).strip() for k, v in donnees.items() if v is not None}
    erreurs: dict[str, list[str]] = {}
    if valeurs.get("role", "") not in Role.values:
        erreurs["role"] = [ROLE_OBLIGATOIRE]
    if not valeurs.get("username"):
        erreurs["username"] = [IDENTIFIANT_OBLIGATOIRE]
    if erreurs:
        raise RegleMetierError(DONNEES_INVALIDES, erreurs)
    if valeurs.get("email"):
        valeurs["email"] = BaseUserManager.normalize_email(valeurs["email"])
    return valeurs


def _verifier_disponibilite(valeurs: dict[str, str]) -> None:
    erreurs: dict[str, list[str]] = {}
    if User.objects.filter(username__iexact=valeurs["username"]).exists():
        erreurs["username"] = [IDENTIFIANT_PRIS]
    email = valeurs.get("email", "")
    # Login accepts the email when exactly one account has it: keep addresses unique.
    if email and User.objects.filter(email__iexact=email).exists():
        erreurs["email"] = [COURRIEL_PRIS]
    matricule = valeurs.get("matricule", "")
    if matricule and User.objects.filter(matricule=matricule).exists():
        erreurs["matricule"] = [MATRICULE_PRIS]
    code = valeurs.get("direction_code", "")
    if code and not direction_existe(code):
        erreurs["direction_code"] = [DIRECTION_INCONNUE]
    if erreurs:
        raise RegleMetierError(DONNEES_INVALIDES, erreurs)


def creer_compte(
    *, donnees: Mapping[str, Any], par: User, envoyer_courriel: bool
) -> tuple[User, str | None]:
    """Create an active local account with a temporary password; the role is mandatory.

    The welcome email carries the password when ``envoyer_courriel`` is set, sending is
    configured, the account has an address and the send succeeds. Only otherwise is the
    password returned, for a single display: it is stored hashed and never readable again.
    """
    valeurs = _valeurs_creation(donnees)
    mot_de_passe = generer_mot_de_passe_temporaire()
    with transaction.atomic(), actor_scope(par):
        _verifier_disponibilite(valeurs)
        user = User(**valeurs, origine=OrigineCompte.ADMINISTRATION, is_active=True)
        _poser_mot_de_passe_temporaire(user, mot_de_passe, timezone.now())
        with _action_auditee(user, ACTION_CREATION):
            try:
                with transaction.atomic():
                    user.save()
            except IntegrityError as exc:
                raise RegleMetierError(CREATION_CONCURRENTE) from exc
    envoye = envoyer_courriel and envoyer_bienvenue(user, mot_de_passe)
    logger_securite.info(
        "Compte créé par l'administration : compte=%s par=%s role=%s courriel_envoye=%s",
        user.pk,
        par.pk,
        user.role,
        envoye,
    )
    return user, (None if envoye else mot_de_passe)


def reinitialiser_mot_de_passe(
    compte: User, *, par: User, envoyer_courriel: bool = True
) -> tuple[str, bool]:
    """Give the account a new temporary password. Returns ``(mot_de_passe, courriel_envoye)``.

    ``mot_de_passe`` is ``""`` when the email went out (the caller never sees it) and the
    clear password otherwise, for a single display. The account is unlocked, pending
    one-time codes are dropped and every open session ends. A disabled account is refused
    (reactivate it first), and so is the caller's own account: changing one's own password
    goes through the current password, which a hijacked session does not know.
    """
    if compte.pk == par.pk:
        raise RegleMetierError(PROPRE_MOT_DE_PASSE)
    mot_de_passe = generer_mot_de_passe_temporaire()
    with transaction.atomic(), actor_scope(par):
        user = _lock(compte)
        if not user.is_active:
            raise RegleMetierError(REINITIALISATION_DESACTIVE)
        champs = _poser_mot_de_passe_temporaire(user, mot_de_passe, timezone.now())
        with _action_auditee(user, ACTION_REINITIALISATION):
            user.save(update_fields=champs)
        CodeOtp.objects.filter(user=user, utilise_le__isnull=True).delete()
    sessions = terminer_sessions(user.pk)
    envoye = envoyer_courriel and envoyer_mot_de_passe_reinitialise(user, mot_de_passe)
    logger_securite.info(
        "Mot de passe réinitialisé par l'administration : compte=%s par=%s "
        "courriel_envoye=%s sessions_terminees=%s",
        user.pk,
        par.pk,
        envoye,
        sessions,
    )
    return ("" if envoye else mot_de_passe), envoye


def desactiver_otp(compte: User, *, par: User) -> User:
    """Turn the login code off for an agent locked out by it (only the owner turns it on).

    Not on the caller's own account: the owner turns it off from "Mon compte", with the
    current password.
    """
    if compte.pk == par.pk:
        raise RegleMetierError(PROPRE_OTP)
    with transaction.atomic(), actor_scope(par):
        user = _lock(compte)
        if not user.otp_connexion_actif:
            raise RegleMetierError(OTP_DEJA_DESACTIVE)
        user.otp_connexion_actif = False
        with _action_auditee(user, ACTION_DESACTIVATION_OTP):
            user.save(update_fields=["otp_connexion_actif"])
        CodeOtp.objects.filter(user=user, objet=ObjetOtp.LOGIN, utilise_le__isnull=True).delete()
    logger_securite.info(
        "Code de connexion par courriel désactivé par l'administration : compte=%s par=%s",
        user.pk,
        par.pk,
    )
    return user


def actions_compte(compte: User, par: User) -> dict[str, bool]:
    lie = compte.keycloak_id is not None
    autre = compte.pk != par.pk
    return {
        "modifier_profil": True,
        "desactiver": compte.is_active and autre,
        "reactiver": not compte.is_active,
        "resynchroniser_profil": compte.profil_gere_localement,
        "relancer_synchro_keycloak": lie
        and compte.keycloak_sync_statut
        in (KeycloakSyncStatut.EN_ATTENTE, KeycloakSyncStatut.ECHEC),
        "reinitialiser_mot_de_passe": compte.is_active and autre,
        "desactiver_otp": compte.otp_connexion_actif and autre,
    }
