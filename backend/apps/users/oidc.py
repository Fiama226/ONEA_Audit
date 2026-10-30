import base64
import binascii
import hashlib
import json
import logging
import time
import uuid
from collections.abc import Mapping
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import SuspiciousOperation
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from .models import KeycloakSyncStatut, OrigineCompte, Role, User
from .services import SYNCED_FIELDS

logger = logging.getLogger(__name__)

# Highest privilege first. Anything not listed (offline_access, uma_authorization,
# default-roles-onea, ...) is ignored.
ROLE_PRIORITY: tuple[Role, ...] = (Role.ADMIN, Role.RAI, Role.AUDITEUR, Role.DG, Role.AUDITE)
MAX_CREATE_ATTEMPTS = 5


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _parse_uuid(value: object) -> uuid.UUID | None:
    if not isinstance(value, str):
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def userinfo_cache_key(access_token: str) -> str:
    """Cle de cache D5 : empreinte SHA-256 du jeton, jamais le jeton en clair."""
    return "oidc:userinfo:" + hashlib.sha256(access_token.encode()).hexdigest()


def _token_expiry(token: str) -> float | None:
    """`exp` du jeton (sans verification de signature : Keycloak l'a validee via userinfo)."""
    parts = token.split(".")
    if len(parts) != 3:  # noqa: PLR2004
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
    except (binascii.Error, ValueError):
        return None
    exp = payload.get("exp") if isinstance(payload, dict) else None
    return float(exp) if isinstance(exp, int | float) and not isinstance(exp, bool) else None


def userinfo_cache_ttl(access_token: str) -> int:
    """min(duree configuree, exp - maintenant) ; 0 = ne pas mettre en cache."""
    exp = _token_expiry(access_token)
    if exp is None:
        return 0
    return max(0, min(int(settings.OIDC_USERINFO_CACHE_SECONDES), int(exp - time.time())))


def purge_userinfo(access_token: str) -> None:
    try:
        cache.delete(userinfo_cache_key(access_token))
    except Exception:  # noqa: BLE001
        logger.warning("Purge du cache userinfo impossible")


def _role_names(claims: Mapping[str, Any]) -> set[str]:
    raw = claims.get("roles")
    items: list[object] = [raw] if isinstance(raw, str) else raw if isinstance(raw, list) else []
    return {item for item in items if isinstance(item, str)}


class OneaOIDCBackend(OIDCAuthenticationBackend):  # type: ignore[misc]
    """Maps Keycloak userinfo claims onto the local User.

    The role is derived ONLY from the claims returned by the verified userinfo
    endpoint, never from anything supplied by the request.
    """

    def get_userinfo(self, access_token: str, id_token: Any, payload: Any) -> Any:
        """Userinfo avec cache D5 : seules les reponses reussies sont conservees ; une
        erreur (401, 5xx, reseau) se propage sans rien mettre en cache. Un cache en panne
        n'empeche jamais l'authentification."""
        key = userinfo_cache_key(access_token)
        try:
            hit = cache.get(key)
        except Exception:  # noqa: BLE001
            logger.warning("Cache userinfo indisponible (lecture)")
            hit = None
        if isinstance(hit, dict):
            return hit
        claims = super().get_userinfo(access_token, id_token, payload)
        ttl = userinfo_cache_ttl(access_token)
        if ttl > 0 and isinstance(claims, dict):
            try:
                cache.set(key, claims, ttl)
            except Exception:  # noqa: BLE001
                logger.warning("Cache userinfo indisponible (ecriture)")
        return claims

    def verify_claims(self, claims: Mapping[str, Any]) -> bool:
        # A stable UUID subject is mandatory (it is the account key); email is optional.
        return _parse_uuid(claims.get("sub")) is not None

    def get_or_create_user(self, access_token: str, id_token: Any, payload: Any) -> User | None:
        try:
            user: User | None = super().get_or_create_user(access_token, id_token, payload)
        except SuspiciousOperation as exc:
            logger.warning("OIDC login refused: %s", exc)
            raise
        if user is not None and user.premiere_connexion_le is None and user.is_active:
            # Atomic "set once"; a refused (inactive) account stays "pending first login".
            now = timezone.now()
            done = User.objects.filter(pk=user.pk, premiere_connexion_le__isnull=True).update(
                premiere_connexion_le=now
            )
            if done:
                user.premiere_connexion_le = now
            else:
                user.refresh_from_db(fields=["premiere_connexion_le"])
        return user

    def get_role_from_claims(self, claims: Mapping[str, Any]) -> Role:
        names = _role_names(claims)
        for role in ROLE_PRIORITY:
            if role.value in names:
                return role
        return Role.AUDITE

    def filter_users_by_claims(self, claims: Mapping[str, Any]) -> QuerySet[User]:
        users = User.objects.all()
        # (1) Stable Keycloak identifier.
        kc_id = _parse_uuid(claims.get("sub"))
        if kc_id is not None:
            by_id = users.filter(keycloak_id=kc_id)
            if by_id.exists():
                return by_id
        by_username = self._preprovisioned_by_username(users, claims)
        by_email = self._unbound_by_email(users, claims)
        # (2) Pre-provisioned account matching the Keycloak username, then (3) the
        # verified-email rule.
        if by_username is not None:
            if by_email is not None and by_email.pk != by_username.pk:
                logger.warning("OIDC username and email designate different local accounts")
            return users.filter(pk=by_username.pk)
        if by_email is not None:
            return users.filter(pk=by_email.pk)
        return users.none()

    def _preprovisioned_by_username(
        self, users: QuerySet[User], claims: Mapping[str, Any]
    ) -> User | None:
        username = _text(claims.get("preferred_username"))
        if not username:
            return None
        matches = list(
            users.filter(
                username__iexact=username,
                origine__in=(OrigineCompte.ANNUAIRE, OrigineCompte.CSV),
                keycloak_id__isnull=True,
                is_staff=False,
                is_superuser=False,
            )[:2]
        )
        return matches[0] if len(matches) == 1 else None

    def _unbound_by_email(self, users: QuerySet[User], claims: Mapping[str, Any]) -> User | None:
        email = _text(claims.get("email"))
        # Email fallback only for a verified email (a self-declared one would allow
        # account takeover) and only to bind a still-unbound, non-privileged account.
        if not email or claims.get("email_verified") is not True:
            return None
        matches = list(users.filter(email__iexact=email)[:2])
        if len(matches) > 1:
            logger.warning("OIDC email matches several local accounts; not binding")
            return None
        if not matches:
            return None
        local = matches[0]
        if local.keycloak_id is not None or local.is_staff or local.is_superuser:
            return None
        return local

    def _base_username(self, claims: Mapping[str, Any]) -> str:
        base = _text(claims.get("preferred_username")) or _text(claims.get("email")).split("@")[0]
        return (base or "user")[:140]

    def _claim_values(self, claims: Mapping[str, Any]) -> dict[str, Any]:
        values: dict[str, Any] = {
            "first_name": _text(claims.get("given_name"))[:150],
            "last_name": _text(claims.get("family_name"))[:150],
            "direction_code": _text(claims.get("direction"))[:16],
            "fonction": _text(claims.get("fonction"))[:128],
            # Keycloak is the source of truth: always re-sync, even when the claim
            # is empty or missing, so that removing a role there takes effect (and
            # may downgrade a local ADMIN to AUDITE).
            "role": self.get_role_from_claims(claims).value,
        }
        kc_id = _parse_uuid(claims.get("sub"))
        if kc_id is not None:
            values["keycloak_id"] = kc_id
        email = _text(claims.get("email"))
        if email:
            values["email"] = email
        return values

    def _insert_user(self, claims: Mapping[str, Any], username: str) -> User:
        user = User(username=username, is_active=True, **self._claim_values(claims))
        user.set_unusable_password()
        user.save()
        return user

    def create_user(self, claims: Mapping[str, Any]) -> User:
        base = self._base_username(claims)
        for attempt in range(MAX_CREATE_ATTEMPTS):
            username = base if attempt == 0 else f"{base[:130]}-{uuid.uuid4().hex[:8]}"
            try:
                with transaction.atomic():
                    return self._insert_user(claims, username)
            except IntegrityError:
                # Either a concurrent first login created the same identity (return
                # the winner) or the username is taken (retry with a suffix).
                winner = self.filter_users_by_claims(claims).first()
                if winner is not None:
                    return self.update_user(winner, claims)
        raise SuspiciousOperation("Could not create the local user")

    def update_user(self, user: User, claims: Mapping[str, Any]) -> User:
        if user.keycloak_id is None and _parse_uuid(claims.get("sub")) is not None:
            # Linking: re-read the row under lock so that a concurrent deactivation
            # (which decides on the keycloak_id it sees) is serialized with this write.
            with transaction.atomic():
                fresh = User.objects.select_for_update().get(pk=user.pk)
                user.is_active = fresh.is_active
                user.profil_gere_localement = fresh.profil_gere_localement
                return self._apply_claims(user, claims)
        return self._apply_claims(user, claims)

    def _apply_claims(self, user: User, claims: Mapping[str, Any]) -> User:
        changed: list[str] = []
        values = self._claim_values(claims)
        if user.profil_gere_localement:
            for field in SYNCED_FIELDS:
                values.pop(field, None)
        values["role_provisoire"] = False
        if "keycloak_id" in values and user.keycloak_id is None and not user.is_active:
            values["keycloak_sync_statut"] = KeycloakSyncStatut.EN_ATTENTE
            values["keycloak_sync_erreur"] = ""
            values["keycloak_sync_tentatives"] = 0
        for field, value in values.items():
            if getattr(user, field) != value:
                if (
                    field == "role"
                    and value == Role.AUDITE
                    and not _role_names(claims) & {"AUDITE"}
                ):
                    logger.warning(
                        "User %s downgraded from %s to AUDITE: no role in Keycloak claims",
                        user.pk,
                        user.role,
                    )
                setattr(user, field, value)
                changed.append(field)
        if changed:
            # Only the claim-derived columns: never is_active/is_staff/matricule, so a
            # concurrent admin change is not overwritten.
            user.save(update_fields=changed)
        return user
