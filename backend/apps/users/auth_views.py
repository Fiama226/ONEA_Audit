"""Session login of the SPA: login (+ OTP step), logout, session state, CSRF token.

Every POST here requires the CSRF token, even anonymous (login CSRF). Failures of the
password or the code always give the same answer, whatever the reason.
"""

import logging
import time
from datetime import timedelta
from typing import Any, cast

from django.conf import settings
from django.contrib.auth import login, logout
from django.middleware.csrf import get_token
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.middleware import CLE_ACTIVITE, CLE_CONNEXION
from apps.core.reseau import adresse_client
from apps.core.schema import ERROR_400, ERROR_RESPONSES

from . import auth_services
from .auth_serializers import (
    CodeConnexionSerializer,
    ConnexionSerializer,
    EtatSessionSerializer,
    JetonCsrfSerializer,
)
from .auth_services import Etape, Resultat
from .auth_throttles import ConnexionParIpThrottle
from .authentication import SessionAuthentication401
from .courriels import envoyer_code
from .models import ObjetOtp, User
from .serializers import MeSerializer

logger = logging.getLogger(__name__)

ECHEC_CONNEXION = "Identifiant ou mot de passe incorrect."
CODE_INVALIDE = "Code invalide ou expiré."
# Pending second step (OTP): the account id and when the password was checked.
CLE_OTP_COMPTE = "onea_otp_compte"
CLE_OTP_LE = "onea_otp_le"
BACKEND = "django.contrib.auth.backends.ModelBackend"


def _etat(etape: Etape, user: User | None) -> dict[str, Any]:
    return {"etape": etape.value, "me": MeSerializer(user).data if user is not None else None}


def _ouvrir_session(request: Request, user: User) -> None:
    """Log in (new session key) with an absolute 8 h expiry and the idle-timer stamps."""
    request.session.pop(CLE_OTP_COMPTE, None)
    request.session.pop(CLE_OTP_LE, None)
    login(request._request, user, backend=BACKEND)
    maintenant = time.time()
    request.session[CLE_CONNEXION] = maintenant
    request.session[CLE_ACTIVITE] = maintenant
    request.session.set_expiry(timezone.now() + timedelta(seconds=settings.SESSION_COOKIE_AGE))


class _CsrfObligatoireMixin:
    """DRF checks CSRF only for session-authenticated requests; here anonymous POSTs too."""

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        super().initial(request, *args, **kwargs)  # type: ignore[misc]
        SessionAuthentication401().enforce_csrf(request)  # no-op on safe methods


class ConnexionView(_CsrfObligatoireMixin, APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ConnexionParIpThrottle]

    @extend_schema(
        tags=["Authentification"],
        summary="Connexion par identifiant (ou courriel) et mot de passe",
        request=ConnexionSerializer,
        responses={200: EtatSessionSerializer, **ERROR_400, **ERROR_RESPONSES},
    )
    def post(self, request: Request) -> Response:
        serializer = ConnexionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resultat: Resultat = auth_services.authentifier(
            serializer.validated_data["identifiant"],
            serializer.validated_data["mot_de_passe"],
            adresse=adresse_client(request),
        )
        if resultat.etape is None or resultat.user is None:
            raise AuthenticationFailed(ECHEC_CONNEXION)
        user = resultat.user
        if resultat.etape is Etape.OTP:
            # Password alone opens nothing: end any current session, remember the pending step.
            logout(request._request)  # flush: also a fresh session key
            request.session[CLE_OTP_COMPTE] = user.pk
            request.session[CLE_OTP_LE] = time.time()
            code = auth_services.emettre_otp(user, ObjetOtp.LOGIN)
            if not envoyer_code(user, code, ObjetOtp.LOGIN):
                logger.warning("Code de connexion non envoyé : compte=%s", user.pk)
            return Response(_etat(Etape.OTP, None))
        _ouvrir_session(request, user)
        return Response(_etat(resultat.etape, user))


class ConnexionCodeView(_CsrfObligatoireMixin, APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ConnexionParIpThrottle]

    @extend_schema(
        tags=["Authentification"],
        summary="Connexion : vérification du code reçu par courriel",
        request=CodeConnexionSerializer,
        responses={200: EtatSessionSerializer, **ERROR_400, **ERROR_RESPONSES},
    )
    def post(self, request: Request) -> Response:
        serializer = CodeConnexionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        compte_id = request.session.get(CLE_OTP_COMPTE)
        depuis = request.session.get(CLE_OTP_LE)
        if (
            not isinstance(compte_id, int)
            or not isinstance(depuis, int | float)
            or time.time() - depuis > auth_services.OTP_VALIDITE.total_seconds()
        ):
            raise AuthenticationFailed(CODE_INVALIDE)
        resultat = auth_services.authentifier_code(
            compte_id, serializer.validated_data["code"], adresse=adresse_client(request)
        )
        if resultat.etape is None or resultat.user is None:
            raise AuthenticationFailed(CODE_INVALIDE)
        _ouvrir_session(request, resultat.user)
        return Response(_etat(resultat.etape, resultat.user))


class DeconnexionView(_CsrfObligatoireMixin, APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Authentification"],
        summary="Déconnexion (fin de la session)",
        request=None,
        responses={204: None, **ERROR_RESPONSES},
    )
    def post(self, request: Request) -> Response:
        logout(request._request)
        return Response(status=204)


class SessionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Authentification"],
        summary="État de la session courante",
        responses={200: EtatSessionSerializer, **ERROR_RESPONSES},
    )
    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        return Response(_etat(auth_services.etape_apres_second_facteur(user), user))


class JetonCsrfView(APIView):
    """Sets the CSRF cookie and returns the token (the cookie is HttpOnly in production)."""

    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Authentification"],
        summary="Jeton CSRF à joindre aux requêtes d'écriture (en-tête X-CSRFToken)",
        responses={200: JetonCsrfSerializer},
    )
    def get(self, request: Request) -> Response:
        return Response({"csrf_token": get_token(request._request)})
