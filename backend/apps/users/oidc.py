import logging
import uuid
from collections.abc import Mapping
from typing import Any

from django.db.models import QuerySet
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from .models import Role, User

logger = logging.getLogger(__name__)

# Highest privilege first. Anything not listed (offline_access, uma_authorization,
# default-roles-onea, ...) is ignored.
ROLE_PRIORITY: tuple[Role, ...] = (Role.ADMIN, Role.RAI, Role.AUDITEUR, Role.DG, Role.AUDITE)


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _parse_uuid(value: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


class OneaOIDCBackend(OIDCAuthenticationBackend):  # type: ignore[misc]
    """Maps Keycloak userinfo claims onto the local User.

    The role is derived ONLY from the claims returned by the verified userinfo
    endpoint, never from anything supplied by the request.
    """

    def verify_claims(self, claims: Mapping[str, Any]) -> bool:
        # A stable subject is mandatory; email is optional (matching falls back on sub).
        return bool(_text(claims.get("sub")))

    def get_role_from_claims(self, claims: Mapping[str, Any]) -> Role:
        raw = claims.get("roles")
        items: list[object] = (
            [raw] if isinstance(raw, str) else raw if isinstance(raw, list) else []
        )
        names = {item for item in items if isinstance(item, str)}
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
        if not email:
            return users.none()
        # Never take over an account already bound to another Keycloak identity.
        return users.filter(email__iexact=email, keycloak_id__isnull=True)

    def _username(self, claims: Mapping[str, Any]) -> str:
        base = _text(claims.get("preferred_username")) or _text(claims.get("email")).split("@")[0]
        base = (base or "user")[:140]
        if not User.objects.filter(username__iexact=base).exists():
            return base
        return f"{base}-{uuid.uuid4().hex[:8]}"

    def _apply_claims(self, user: User, claims: Mapping[str, Any]) -> None:
        kc_id = _parse_uuid(claims.get("sub"))
        if kc_id is not None:
            user.keycloak_id = kc_id
        elif user.keycloak_id is None:
            logger.warning("OIDC subject is not a UUID; keycloak_id left empty")
        email = _text(claims.get("email"))
        if email:
            user.email = email
        user.first_name = _text(claims.get("given_name"))[:150]
        user.last_name = _text(claims.get("family_name"))[:150]
        user.direction_code = _text(claims.get("direction"))[:16]
        user.fonction = _text(claims.get("fonction"))[:128]
        # Keycloak is the source of truth: always re-sync, even when the claim is
        # empty, so that removing a role there takes effect (and may downgrade a
        # local ADMIN to AUDITE).
        user.role = self.get_role_from_claims(claims)

    def create_user(self, claims: Mapping[str, Any]) -> User:
        user = User(username=self._username(claims), is_active=True)
        user.set_unusable_password()
        self._apply_claims(user, claims)
        user.save()
        return user

    def update_user(self, user: User, claims: Mapping[str, Any]) -> User:
        self._apply_claims(user, claims)
        user.save()
        return user
