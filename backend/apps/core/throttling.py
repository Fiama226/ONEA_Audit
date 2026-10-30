"""Limitation de débit par utilisateur (indépendante du NAT d'entreprise).

La clé est l'identifiant de l'utilisateur authentifié ; seul un appelant anonyme est
limité par l'adresse client (``apps.core.reseau.adresse_client``). Les taux viennent de
``REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]``. Si le cache est indisponible, la requête
passe et un avertissement est journalisé : la limitation ne doit pas bloquer le service.
"""

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from rest_framework.request import Request
from rest_framework.settings import api_settings
from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle

from .reseau import adresse_client

if TYPE_CHECKING:  # import réel impossible : rest_framework.views charge ce module
    from rest_framework.views import APIView

logger = logging.getLogger(__name__)

PORTEE_ANONYME = "anonyme"


class UtilisateurScopedRateThrottle(ScopedRateThrottle):
    """Taux par portée (``throttle_scope`` de la vue), compté par utilisateur."""

    def get_rate(self) -> str | None:
        # lu à chaque requête : les taux restent surchargeables (réglages, tests)
        taux = api_settings.DEFAULT_THROTTLE_RATES
        try:
            return str(taux[self.scope or ""])
        except KeyError:
            return super().get_rate()

    def get_cache_key(self, request: Request, view: "APIView") -> str:
        utilisateur = getattr(request, "user", None)
        if utilisateur is not None and utilisateur.is_authenticated:
            identite = f"u{utilisateur.pk}"
        else:
            identite = f"ip{adresse_client(request) or 'inconnue'}"
        return f"throttle_{self.scope}_{identite}"

    def allow_request(self, request: Request, view: "APIView") -> bool:
        portee = getattr(view, "throttle_scope", None)
        if not portee:
            return True
        utilisateur = getattr(request, "user", None)
        authentifie = utilisateur is not None and utilisateur.is_authenticated
        self.scope = portee if authentifie else PORTEE_ANONYME
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)
        try:
            return SimpleRateThrottle.allow_request(self, request, view)
        except Exception as exc:
            logger.warning(
                "Limitation de débit désactivée pour la portée « %s » : cache indisponible (%s).",
                self.scope,
                type(exc).__name__,
            )
            return True


class ThrottleParActionMixin:
    # Portée de limitation par action (pas de docstring : drf-spectacular la publierait).

    throttle_scopes: ClassVar[dict[str, str]] = {}
    action: Any

    @property
    def throttle_scope(self) -> str | None:
        return self.throttle_scopes.get(getattr(self, "action", None) or "")
