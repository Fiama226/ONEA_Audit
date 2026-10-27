import logging
import uuid
from collections.abc import Mapping
from typing import Any

from django.core.exceptions import SuspiciousOperation
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from .models import Role, User

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


def _role_names(claims: Mapping[str, Any]) -> set[str]:
    raw = claims.get("roles")
    items: list[object] = [raw] if isinstance(raw, str) else raw if isinstance(raw, list) else []
    return {item for item in items if isinstance(item, str)}


class OneaOIDCBackend(OIDCAuthenticationBackend):  # type: ignore[misc]
    """Maps Keycloak userinfo claims onto the local User.

    The role is derived ONLY from the claims returned by the verified userinfo
    endpoint, never from anything supplied by the request.
    """

    def verify_claims(self, claims: Mapping[str, Any]) -> bool:
        # A stable UUID subject is mandatory (it is the account key); email is optional.
        return _parse_uuid(claims.get("sub")) is not None

    def get_or_create_user(self, access_token: str, id_token: Any, payload: Any) -> User | None:
        try:
            user: User | None = super().get_or_create_user(access_token, id_token, payload)
        except SuspiciousOperation as exc:
            logger.warning("OIDC login refused: %s", exc)
            raise
        return user

    def get_role_from_claims(self, claims: Mapping[str, Any]) -> Role:
        names = _role_names(claims)
        for role in ROLE_PRIORITY:
            if role.value in names:
                return role
        return Role.AUDITE

    def filter_users_by_claims(self, claims: Mapping[str, Any]) -> QuerySet[User]:
        users = User.objects.all()
        kc_id = _parse_uuid(claims.get("sub"))
        if kc_id is not None:
            by_id = users.filter(keycloak_id=kc_id)
            if by_id.exists():
                return by_id
        email = _text(claims.get("email"))
        # Email fallback only for a verified email (a self-declared one would allow
        # account takeover) and only to bind a still-unbound, non-privileged account.
        if not email or claims.get("email_verified") is not True:
            return users.none()
        matches = list(users.filter(email__iexact=email)[:2])
        if len(matches) > 1:
            logger.warning("OIDC email matches several local accounts; not binding")
            return users.none()
        if not matches:
            return users.none()
        local = matches[0]
        if local.keycloak_id is not None or local.is_staff or local.is_superuser:
            return users.none()
        return users.filter(pk=local.pk)

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
        changed: list[str] = []
        for field, value in self._claim_values(claims).items():
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
