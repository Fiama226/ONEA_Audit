"""Account administration services: the ADMIN role, or rights delegated by an admin.

The rights are checked here too, not only by the views (commands call these services):
see `delegation` for the rules (a delegate never touches an ADMIN, another manager or
himself, never assigns the ADMIN role, never changes a delegation). Every right is re-read
from the database under the transaction, after the target row is locked.

Every write runs in a transaction, under the audit actor, on a row re-read with
`select_for_update`. No network call is made here: the Keycloak propagation is done by
the caller once the transaction has committed. The in-app account actions (creation,
password reset, login-code removal, email/name/role edits) never touch Keycloak: their
emails go out after the commit, and a temporary password never reaches the audit trail or
the logs.
"""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any

from django.contrib.auth.base_user import BaseUserManager
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.audit import actor_scope
from apps.core.exceptions import RegleMetierError
from apps.referentiel.models import Direction

from .auth_services import generer_mot_de_passe_temporaire, logger_securite, terminer_sessions
from .courriels import envoyer_bienvenue, envoyer_mot_de_passe_reinitialise
from .delegation import (
    ACTIONS,
    DROIT_REFUSE,
    Action,
    droits_sur,
    etat_sur,
    exiger,
    exiger_administrateur,
    exiger_attribution_role,
)
from .models import (
    CodeOtp,
    DelegationGestionComptes,
    KeycloakSyncStatut,
    ObjetOtp,
    OrigineCompte,
    Role,
    User,
)

PROFILE_FIELDS = frozenset(
    {"matricule", "direction_code", "fonction", "email", "first_name", "last_name"}
)
# Right needed to change each profile field of an existing account. Names, matricule and
# function: the right to create accounts. The email is the password-recovery channel, so
# changing it is worth a password reset. The direction scopes what an audité can read,
# like a role.
DROIT_PAR_CHAMP: dict[str, Action] = {
    "first_name": "creer",
    "last_name": "creer",
    "matricule": "creer",
    "fonction": "creer",
    "email": "reinitialiser",
    "direction_code": "roles",
}
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

_MAX_LENGTHS = {
    "matricule": 32,
    "fonction": 128,
    "email": 254,
    "first_name": 150,
    "last_name": 150,
}
COURRIEL_INVALIDE = "Saisissez une adresse de courriel valide."
COURRIEL_REQUIS_OTP = (
    "Le code de connexion par courriel est actif sur ce compte : l'adresse ne peut pas être vidée."
)
IDENTIFIANT_AROBASE = (
    "L'identifiant ne doit pas contenir « @ » : la connexion par adresse de courriel est "
    "déjà possible."
)
ROLE_INVALIDE = "Choisissez un rôle dans la liste."
ROLE_INCHANGE = "Ce compte a déjà ce rôle."
PROPRE_ROLE = "Vous ne pouvez pas modifier votre propre rôle."
DERNIER_ADMIN_ROLE = (
    "Impossible de retirer le rôle Administrateur au dernier administrateur actif de la plateforme."
)
DELEGATION_INACTIF = "Ce compte est désactivé : réactivez-le avant de lui déléguer des droits."
DELEGATION_ADMIN = (
    "Un administrateur dispose déjà de tous les droits : aucune délégation ne lui est accordée."
)

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
ACTION_CHANGEMENT_ROLE = "changement_role"


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


def _verrouiller(
    compte: User, acteur: User, *, admins_actifs: bool = False
) -> tuple[User, list[User]]:
    """Lock the target and the actor (plus every active admin when asked), in pk order.

    Locking the actor's row makes a concurrent revocation, deactivation or demotion of the
    actor (which locks that same row) either finish first, and then be seen by the rights
    check that follows, or wait for this action. One statement in pk order: no deadlock
    between two crossed actions.
    """
    filtre = Q(pk__in=[pk for pk in (compte.pk, acteur.pk) if pk is not None])
    if admins_actifs:
        filtre |= Q(role=Role.ADMIN, is_active=True)
    locked = list(User.objects.select_for_update().filter(filtre).order_by("pk"))
    return next(u for u in locked if u.pk == compte.pk), locked


def _valeur_comparable(user: User, champ: str) -> str:
    """Stored value as it would be submitted: a legacy address with an uppercase domain
    re-sent unchanged is not a change."""
    valeur = str(getattr(user, champ))
    if champ == "email" and valeur:
        return BaseUserManager.normalize_email(valeur.strip())
    return valeur


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


def _valeurs_profil(changes: Mapping[str, str]) -> dict[str, str]:
    unknown = set(changes) - PROFILE_FIELDS
    if unknown:
        raise ValueError(f"Unsupported profile fields: {sorted(unknown)}")
    values = {k: str(v).strip() for k, v in changes.items()}
    for field, limit in _MAX_LENGTHS.items():
        if field in values and len(values[field]) > limit:
            raise RegleMetierError(
                DONNEES_INVALIDES,
                {field: [f"Assurez-vous que ce champ comporte au plus {limit} caractères."]},
            )
    if values.get("email"):
        try:
            validate_email(values["email"])
        except ValidationError as exc:
            raise RegleMetierError(DONNEES_INVALIDES, {"email": [COURRIEL_INVALIDE]}) from exc
        values["email"] = BaseUserManager.normalize_email(values["email"])
    return values


def _courriel_pris(email: str, *, sauf: int | None = None) -> bool:
    """An address used by another account, as its email or as its username.

    Login tries the exact username first, then the email: an address equal to someone
    else's username would never reach its own account (case-insensitive on both sides).
    """
    autres = User.objects.exclude(pk=sauf) if sauf is not None else User.objects.all()
    return autres.filter(Q(email__iexact=email) | Q(username__iexact=email)).exists()


def modifier_profil(compte: User, *, changes: Mapping[str, str], by: User) -> User:
    """Edit profile and identity fields; each changed field needs its own right.

    A field sent with its current value needs no right (a whole form sent back as is).
    Changing the email drops the account's pending one-time codes: a code already sent to
    the old address must not open the account any more.
    """
    values = _valeurs_profil(changes)
    with transaction.atomic(), actor_scope(by):
        user, _ = _verrouiller(compte, by)
        modifies = {f: v for f, v in values.items() if _valeur_comparable(user, f) != v}
        droits = droits_sur(by, user)
        if modifies:
            autorise = all(droits[DROIT_PAR_CHAMP[f]] for f in modifies)
        else:
            autorise = any(droits[a] for a in set(DROIT_PAR_CHAMP.values()))
        if not autorise:
            raise PermissionDenied(DROIT_REFUSE)
        new_code = modifies.get("direction_code")
        if new_code and not direction_existe(new_code):
            raise RegleMetierError(DONNEES_INVALIDES, {"direction_code": [DIRECTION_INCONNUE]})
        if "email" in modifies:
            email = modifies["email"]
            if not email and user.otp_connexion_actif:
                raise RegleMetierError(DONNEES_INVALIDES, {"email": [COURRIEL_REQUIS_OTP]})
            if email and _courriel_pris(email, sauf=user.pk):
                raise RegleMetierError(DONNEES_INVALIDES, {"email": [COURRIEL_PRIS]})
        fields: list[str] = []
        for field, value in modifies.items():
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
                raise RegleMetierError(DONNEES_INVALIDES, {"matricule": [MATRICULE_PRIS]}) from exc
        if "email" in modifies:
            CodeOtp.objects.filter(user=user, utilise_le__isnull=True).delete()
    if "email" in modifies:
        # The addresses themselves stay in the audit trail only, not in the logs.
        logger_securite.info(
            "Adresse de courriel d'un compte modifiée : compte=%s par=%s", user.pk, by.pk
        )
    return user


def desactiver(compte: User, *, motif: str, by: User) -> User:
    with transaction.atomic(), actor_scope(by):
        # Lock every active admin plus the target and the actor, in pk order, so that two
        # crossed deactivations serialize instead of both succeeding.
        user, locked = _verrouiller(compte, by, admins_actifs=True)
        exiger(by, "desactiver", user)
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
        # A disabled account keeps no delegated right: a reactivation restores none.
        _revoquer_delegation(user, by)
        return user


def reactiver(compte: User, *, by: User) -> User:
    with transaction.atomic(), actor_scope(by):
        user, _ = _verrouiller(compte, by)
        exiger(by, "desactiver", user)
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
    exiger_administrateur(by, DROIT_REFUSE)
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
    elif "@" in valeurs["username"]:
        # Login tries the username before the email: "x@y" would shadow that address.
        erreurs["username"] = [IDENTIFIANT_AROBASE]
    if erreurs:
        raise RegleMetierError(DONNEES_INVALIDES, erreurs)
    if valeurs.get("email"):
        valeurs["email"] = BaseUserManager.normalize_email(valeurs["email"])
    return valeurs


def _verifier_disponibilite(valeurs: dict[str, str]) -> None:
    erreurs: dict[str, list[str]] = {}
    username = valeurs["username"]
    # Neither an existing username nor an existing email: login resolves both.
    if User.objects.filter(Q(username__iexact=username) | Q(email__iexact=username)).exists():
        erreurs["username"] = [IDENTIFIANT_PRIS]
    email = valeurs.get("email", "")
    # Login accepts the email when exactly one account has it: keep addresses unique.
    if email and _courriel_pris(email):
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
    exiger(par, "creer")
    valeurs = _valeurs_creation(donnees)
    exiger_attribution_role(par, valeurs["role"])
    mot_de_passe = generer_mot_de_passe_temporaire()
    with transaction.atomic(), actor_scope(par):
        # Re-checked under the actor's lock: a revocation committed meanwhile is respected.
        list(User.objects.select_for_update().filter(pk=par.pk))
        exiger(par, "creer")
        exiger_attribution_role(par, valeurs["role"])
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
        user, _ = _verrouiller(compte, par)
        exiger(par, "reinitialiser", user)
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
        user, _ = _verrouiller(compte, par)
        exiger(par, "reinitialiser", user)
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


def _revoquer_delegation(user: User, par: User) -> None:
    """Drop every delegated right of the account (in the caller's transaction, audited)."""
    delegation = DelegationGestionComptes.objects.select_for_update().filter(user=user).first()
    if delegation is None or not any(getattr(delegation, a) for a in ACTIONS):
        return
    for action in ACTIONS:
        setattr(delegation, action, False)
    delegation.accorde_par = par
    delegation.accorde_le = timezone.now()
    delegation.save()


def changer_role(compte: User, *, role: str, par: User) -> User:
    """Give the account another role. Only an ADMIN gives the ADMIN role; nobody changes
    his own role; the last active ADMIN keeps his. A promotion to ADMIN drops the
    delegated rights (useless to an admin, and they must not come back on a demotion).
    The new role applies on the account's next request (it is read on each one)."""
    if role not in Role.values:
        raise RegleMetierError(DONNEES_INVALIDES, {"role": [ROLE_INVALIDE]})
    exiger_attribution_role(par, role)
    with transaction.atomic(), actor_scope(par):
        # Same lock order as `desactiver`: every active admin, the target and the actor.
        user, locked = _verrouiller(compte, par, admins_actifs=True)
        exiger_attribution_role(par, role)
        exiger(par, "roles", user)
        if user.pk == par.pk:
            raise RegleMetierError(PROPRE_ROLE)
        if user.role == role:
            raise RegleMetierError(ROLE_INCHANGE)
        if (
            user.role == Role.ADMIN
            and user.is_active
            and not any(u.pk != user.pk and u.role == Role.ADMIN and u.is_active for u in locked)
        ):
            raise RegleMetierError(DERNIER_ADMIN_ROLE)
        ancien = user.role
        user.role = role
        user.role_provisoire = False
        with _action_auditee(user, ACTION_CHANGEMENT_ROLE):
            user.save(update_fields=["role", "role_provisoire"])
        if role == Role.ADMIN:
            _revoquer_delegation(user, par)
    logger_securite.info(
        "Rôle d'un compte modifié : compte=%s par=%s ancien=%s nouveau=%s",
        user.pk,
        par.pk,
        ancien,
        role,
    )
    return user


def delegation_de(compte: User) -> DelegationGestionComptes:
    """The account's delegation, or an unsaved all-false one when it never had any."""
    delegation = (
        DelegationGestionComptes.objects.select_related("accorde_par").filter(user=compte).first()
    )
    return delegation or DelegationGestionComptes(user=compte)


def definir_delegation(
    compte: User, *, droits: Mapping[str, bool], par: User
) -> DelegationGestionComptes:
    """Set the four delegated rights of a non-ADMIN account (ADMIN only, audited).

    Takes effect on the delegate's next request. A call that changes nothing writes
    nothing; an all-false call on an account without delegation creates no row.
    """
    if set(droits) != set(ACTIONS):
        raise ValueError(f"Expected exactly the rights {list(ACTIONS)}, got {sorted(droits)}")
    exiger_administrateur(par)
    valeurs = {action: bool(droits[action]) for action in ACTIONS}
    with transaction.atomic(), actor_scope(par):
        user, _ = _verrouiller(compte, par)
        exiger_administrateur(par)
        if user.role == Role.ADMIN:
            raise RegleMetierError(DELEGATION_ADMIN)
        if not user.is_active and any(valeurs.values()):
            raise RegleMetierError(DELEGATION_INACTIF)
        delegation = DelegationGestionComptes.objects.select_for_update().filter(user=user).first()
        if delegation is None:
            delegation = DelegationGestionComptes(user=user)
            if not any(valeurs.values()):
                return delegation
        elif all(getattr(delegation, a) == v for a, v in valeurs.items()):
            return delegation
        for action, valeur in valeurs.items():
            setattr(delegation, action, valeur)
        delegation.accorde_par = par
        delegation.accorde_le = timezone.now()
        delegation.save()
    logger_securite.info(
        "Délégation de gestion des comptes modifiée : compte=%s par=%s droits=%s",
        user.pk,
        par.pk,
        ",".join(a for a in ACTIONS if valeurs[a]) or "aucun",
    )
    return delegation


def actions_compte(compte: User, par: User) -> dict[str, bool]:
    """What ``par`` may do on ``compte`` (drives the buttons of the account page)."""
    admin, droits = etat_sur(par, compte)
    lie = compte.keycloak_id is not None
    autre = compte.pk != par.pk
    return {
        "modifier_profil": droits["creer"],
        "desactiver": compte.is_active and autre and droits["desactiver"],
        "reactiver": not compte.is_active and droits["desactiver"],
        "resynchroniser_profil": admin and compte.profil_gere_localement,
        "relancer_synchro_keycloak": admin
        and lie
        and compte.keycloak_sync_statut
        in (KeycloakSyncStatut.EN_ATTENTE, KeycloakSyncStatut.ECHEC),
        "reinitialiser_mot_de_passe": compte.is_active and autre and droits["reinitialiser"],
        "desactiver_otp": compte.otp_connexion_actif and autre and droits["reinitialiser"],
        "modifier_courriel": droits["reinitialiser"],
        "modifier_direction": droits["roles"],
        "changer_role": autre and droits["roles"],
    }
