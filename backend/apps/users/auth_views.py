"""Session login of the SPA: login (+ OTP step), logout, session state, CSRF token,
forgotten password (code by email), password change, login code option.

Every POST here requires the CSRF token, even anonymous (login CSRF). Failures of the
password or the code always give the same answer, whatever the reason.
"""

import logging
import time
from datetime import timedelta
from typing import Any, cast

from django.conf import settings
from django.contrib.auth import login, logout, update_session_auth_hash
from django.core.exceptions import ValidationError as DjangoValidationError
from django.middleware.csrf import get_token
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import APIException, AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.middleware import CLE_ACTIVITE, CLE_CONNEXION
from apps.core.reseau import adresse_client
from apps.core.schema import ERROR_400, ERROR_409, ERROR_429, ERROR_RESPONSES

from . import auth_services
from .auth_serializers import (
    ChangementMotDePasseSerializer,
    CodeConnexionSerializer,
    ConnexionSerializer,
    EtatOtpSerializer,
    EtatSessionSerializer,
    JetonCsrfSerializer,
    MessageSerializer,
    MotDePasseOublieSerializer,
    ReinitialisationSerializer,
)
from .auth_services import CLE_OTP_COMPTE, Etape, Resultat
from .auth_throttles import ConnexionParIpThrottle, MotDePasseOublieParIdentifiantThrottle
from .authentication import SessionAuthentication401
from .courriels import envoyer_code
from .models import ObjetOtp, User
from .serializers import MeSerializer
from .tasks import envoyer_code_reinitialisation

logger = logging.getLogger(__name__)

ECHEC_CONNEXION = "Identifiant ou mot de passe incorrect."
CODE_INVALIDE = "Code invalide ou expiré."
DEMANDE_CODE = (
    "Si un compte actif correspond à cet identifiant, un code de vérification vient d'être "
    "envoyé à son adresse de courriel. Il est valable 10 minutes."
)
ANCIEN_INCORRECT = "Mot de passe actuel incorrect."
# Pending second step (OTP): the account id (CLE_OTP_COMPTE) and when the password was checked.
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


class CodeRefuse(APIException):
    """Uniform refusal of a reset: unknown account, disabled account, bad or used code."""

    status_code = 400
    default_detail = CODE_INVALIDE
    default_code = "code_invalide"


def _erreurs_mot_de_passe(champ: str, exc: DjangoValidationError) -> ValidationError:
    return ValidationError({champ: list(exc.messages)})


class MotDePasseOublieView(_CsrfObligatoireMixin, APIView):
    """Always 202 with the same body: whether an account exists is never told.

    The request only looks the account up and queues the task, for every identifier; the
    code is issued and emailed by the worker, to an active account only.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ConnexionParIpThrottle, MotDePasseOublieParIdentifiantThrottle]

    @extend_schema(
        tags=["Authentification"],
        summary="Mot de passe oublié : demande d'un code par courriel",
        request=MotDePasseOublieSerializer,
        responses={202: MessageSerializer, **ERROR_400, **ERROR_429, **ERROR_RESPONSES},
    )
    def post(self, request: Request) -> Response:
        serializer = MotDePasseOublieSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        compte = auth_services.trouver_compte(serializer.validated_data["identifiant"])
        compte_id = compte.pk if compte is not None else None
        auth_services.logger_securite.info(
            "Demande de code de réinitialisation : compte=%s adresse=%s",
            compte_id or "inconnu",
            adresse_client(request) or "inconnue",
        )
        try:
            envoyer_code_reinitialisation.delay(compte_id)
        except Exception as exc:  # noqa: BLE001 - broker down: same answer, logged
            logger.warning("Demande de code non transmise : %s", type(exc).__name__)
        return Response({"detail": DEMANDE_CODE}, status=202)


class ReinitialisationView(_CsrfObligatoireMixin, APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ConnexionParIpThrottle]

    @extend_schema(
        tags=["Authentification"],
        summary="Mot de passe oublié : nouveau mot de passe avec le code reçu",
        request=ReinitialisationSerializer,
        responses={204: None, **ERROR_400, **ERROR_429, **ERROR_RESPONSES},
    )
    def post(self, request: Request) -> Response:
        serializer = ReinitialisationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        donnees = serializer.validated_data
        try:
            compte = auth_services.reinitialiser_mot_de_passe(
                donnees["identifiant"],
                donnees["code"],
                donnees["nouveau_mot_de_passe"],
                adresse=adresse_client(request),
            )
        except DjangoValidationError as exc:
            raise _erreurs_mot_de_passe("nouveau_mot_de_passe", exc) from None
        if compte is None:
            raise CodeRefuse
        return Response(status=204)


class ChangementMotDePasseView(APIView):
    """Change by the logged-in agent (also the forced change of a temporary password).

    The current session stays open under a new key (login stamps and fixed expiry kept);
    every other session of the agent ends.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ConnexionParIpThrottle]

    @extend_schema(
        tags=["Authentification"],
        summary="Changement de son mot de passe",
        request=ChangementMotDePasseSerializer,
        responses={200: EtatSessionSerializer, **ERROR_400, **ERROR_429, **ERROR_RESPONSES},
    )
    def post(self, request: Request) -> Response:
        serializer = ChangementMotDePasseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            compte = auth_services.changer_mot_de_passe(
                cast(User, request.user),
                serializer.validated_data["ancien"],
                serializer.validated_data["nouveau"],
                adresse=adresse_client(request),
            )
        except DjangoValidationError as exc:
            raise _erreurs_mot_de_passe("nouveau", exc) from None
        if compte is None:
            raise ValidationError({"ancien": [ANCIEN_INCORRECT]})
        # New session key bound to the new password hash; the session data (stamps) is kept.
        update_session_auth_hash(request._request, compte)
        auth_services.terminer_sessions(compte.pk, sauf=request.session.session_key)
        return Response(_etat(auth_services.etape_apres_second_facteur(compte), compte))


class _OtpConnexionView(APIView):
    """Acts on the caller's own account only: no route or field names another account."""

    permission_classes = [IsAuthenticated]
    actif: bool

    def _basculer(self, request: Request) -> Response:
        compte = cast(User, request.user)
        auth_services.changer_otp_connexion(compte, self.actif, adresse=adresse_client(request))
        return Response({"otp_connexion_actif": compte.otp_connexion_actif})


class ActivationOtpView(_OtpConnexionView):
    actif = True

    @extend_schema(
        tags=["Authentification"],
        summary="Activer le code de connexion par courriel (son propre compte)",
        request=None,
        responses={200: EtatOtpSerializer, **ERROR_409, **ERROR_RESPONSES},
    )
    def post(self, request: Request) -> Response:
        return self._basculer(request)


class DesactivationOtpView(_OtpConnexionView):
    actif = False

    @extend_schema(
        tags=["Authentification"],
        summary="Désactiver le code de connexion par courriel (son propre compte)",
        request=None,
        responses={200: EtatOtpSerializer, **ERROR_RESPONSES},
    )
    def post(self, request: Request) -> Response:
        return self._basculer(request)
