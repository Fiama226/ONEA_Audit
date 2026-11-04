"""API d'administration des comptes : aucune logique métier, tout passe par les services."""

from typing import Any, ClassVar, cast
from uuid import UUID

from django.db.models import OuterRef, QuerySet, Subquery
from django.http import Http404, HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, serializers
from rest_framework.decorators import action
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.core import antivirus
from apps.core.filters import StableOrderingFilter
from apps.core.schema import (
    ERROR_400,
    ERROR_404,
    ERROR_422,
    ERROR_429,
    ERROR_RESPONSES,
)
from apps.core.throttling import ThrottleParActionMixin
from apps.referentiel.models import Direction

from . import provisioning, services
from .account_filters import UserAccountFilter
from .account_permissions import AccountAdminPermission, LectureComptes, PeutGererComptes
from .account_serializers import (
    ChangementRoleSerializer,
    CompteUtilisateurListeSerializer,
    CompteUtilisateurSerializer,
    CreationCompteSerializer,
    DelegationGestionComptesSerializer,
    ImportCsvSerializer,
    MotDePasseTemporaireSerializer,
    MotifDesactivationSerializer,
    ProfilUtilisateurSerializer,
    RapportImportSerializer,
    ReinitialisationCompteSerializer,
)
from .delegation import ACTIONS
from .models import User
from .provisioning import FichierImportInvalide

TAG = "Comptes utilisateurs"

_COMPTE = {"200": None}
_ERREURS_ACTION = {**ERROR_RESPONSES, **ERROR_404, **ERROR_422}

# Who may call each action (re-checked by the services on the locked target). Anything not
# listed (delegations, imports, OPTIONS) is ADMIN only.
_PERMISSIONS: dict[str, type[BasePermission]] = {
    "list": LectureComptes,
    "retrieve": LectureComptes,
    "create": PeutGererComptes("creer"),
    "reset_password": PeutGererComptes("reinitialiser"),
    "disable_otp": PeutGererComptes("reinitialiser"),
    "change_role": PeutGererComptes("roles"),
    # Per changed field in the service: names/matricule/function = creer, email =
    # reinitialiser, direction = roles.
    "partial_update": PeutGererComptes("creer", "reinitialiser", "roles"),
    "deactivate": PeutGererComptes("desactiver"),
    "reactivate": PeutGererComptes("desactiver"),
}


class _SansNegociation(BaseContentNegotiation):
    """A file downloads whatever the `Accept` header says (never a 406)."""

    def select_renderer(  # type: ignore[no-untyped-def]
        self, request, renderers, format_suffix=None
    ):
        return renderers[0], renderers[0].media_type


@extend_schema_view(
    list=extend_schema(
        tags=[TAG],
        summary="Lister : comptes utilisateurs",
        responses={
            200: CompteUtilisateurListeSerializer(many=True),
            **ERROR_400,
            **ERROR_RESPONSES,
        },
    ),
    retrieve=extend_schema(
        tags=[TAG],
        summary="Détail : compte utilisateur",
        responses={200: CompteUtilisateurSerializer, **ERROR_RESPONSES, **ERROR_404},
    ),
)
class UserAccountViewSet(
    ThrottleParActionMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet[User],
):
    throttle_scopes: ClassVar[dict[str, str]] = {
        "import_csv": "import",
        # Open to delegates and sending emails: capped per user (no mailbox flooding).
        "create": "gestion_comptes",
        "reset_password": "gestion_comptes",
        "disable_otp": "gestion_comptes",
    }
    permission_classes = [AccountAdminPermission]
    filter_backends = [DjangoFilterBackend, StableOrderingFilter]
    filterset_class = UserAccountFilter
    http_method_names = ["get", "patch", "post", "put"]
    lookup_value_regex = r"\d+"
    ordering_fields = (
        "last_name",
        "username",
        "role",
        "direction_code",
        "is_active",
        "date_joined",
    )
    ordering = ("last_name", "first_name", "pk")

    def get_queryset(self) -> QuerySet[User]:
        libelle = Direction.objects.filter(
            code=OuterRef("direction_code"), deleted_at__isnull=True
        ).values("libelle")[:1]
        return User.objects.select_related("desactive_par").annotate(
            direction_libelle=Subquery(libelle)
        )

    def get_permissions(self) -> list[BasePermission]:
        return [_PERMISSIONS.get(self.action or "", AccountAdminPermission)()]

    def get_serializer_class(self) -> type[serializers.BaseSerializer[Any]]:
        if self.action == "list":
            return CompteUtilisateurListeSerializer
        return CompteUtilisateurSerializer

    @property
    def acteur(self) -> User:
        return cast(User, self.request.user)

    def _reponse(self, compte: User) -> Response:
        frais = self.get_queryset().get(pk=compte.pk)
        data = CompteUtilisateurSerializer(frais, context=self.get_serializer_context()).data
        return Response(data)

    def _reponse_mot_de_passe(
        self, compte: User, mot_de_passe: str | None, envoye: bool, status: int
    ) -> Response:
        """Account + one-time temporary password: never cached by the browser or a proxy."""
        frais = self.get_queryset().get(pk=compte.pk)
        data = {
            "compte": CompteUtilisateurSerializer(
                frais, context=self.get_serializer_context()
            ).data,
            "courriel_envoye": envoye,
            "mot_de_passe_temporaire": mot_de_passe or None,
        }
        reponse = Response(data, status=status)
        reponse["Cache-Control"] = "no-store"
        return reponse

    @extend_schema(
        tags=[TAG],
        summary="Créer un compte",
        description=(
            "Crée un compte local avec un mot de passe temporaire (72 h, à changer à la "
            "première connexion). Le rôle est obligatoire. Le mot de passe n'est renvoyé "
            "qu'une fois, et seulement s'il n'a pas pu partir par courriel."
        ),
        request=CreationCompteSerializer,
        responses={
            201: MotDePasseTemporaireSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_422,
            **ERROR_429,
        },
    )
    def create(self, request: Request) -> Response:
        serializer = CreationCompteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        donnees = dict(serializer.validated_data)
        envoyer = donnees.pop("envoyer_courriel")
        compte, mot_de_passe = services.creer_compte(
            donnees=donnees, par=self.acteur, envoyer_courriel=envoyer
        )
        return self._reponse_mot_de_passe(
            compte, mot_de_passe, envoye=mot_de_passe is None, status=201
        )

    @extend_schema(
        tags=[TAG],
        summary="Réinitialiser le mot de passe d'un compte",
        description=(
            "Nouveau mot de passe temporaire (72 h, à changer à la connexion suivante) : le "
            "compte est déverrouillé et toutes ses sessions sont fermées. Refusé sur un "
            "compte désactivé et sur son propre compte."
        ),
        request=ReinitialisationCompteSerializer,
        responses={
            200: MotDePasseTemporaireSerializer,
            **ERROR_400,
            **_ERREURS_ACTION,
            **ERROR_429,
        },
    )
    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request: Request, pk: str) -> Response:
        compte = self.get_object()
        serializer = ReinitialisationCompteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mot_de_passe, envoye = services.reinitialiser_mot_de_passe(
            compte, par=self.acteur, envoyer_courriel=serializer.validated_data["envoyer_courriel"]
        )
        return self._reponse_mot_de_passe(compte, mot_de_passe, envoye=envoye, status=200)

    @extend_schema(
        tags=[TAG],
        summary="Désactiver le code de connexion par courriel d'un compte",
        description="Seul le titulaire peut l'activer ; refusé sur son propre compte.",
        request=None,
        responses={200: CompteUtilisateurSerializer, **_ERREURS_ACTION, **ERROR_429},
    )
    @action(detail=True, methods=["post"], url_path="disable-otp")
    def disable_otp(self, request: Request, pk: str) -> Response:
        compte = self.get_object()
        services.desactiver_otp(compte, par=self.acteur)
        return self._reponse(compte)

    @extend_schema(
        tags=[TAG],
        summary="Modifier le profil d'un compte",
        description=(
            "Droit requis par champ modifié : nom, prénom, matricule et fonction = « créer "
            "des comptes » ; courriel = « réinitialiser les mots de passe » (il sert à la "
            "récupération du compte) ; direction = « changer les rôles ». Un champ renvoyé "
            "inchangé ne demande aucun droit. Un délégué ne modifie ni un administrateur, ni "
            "un RAI, ni la Direction générale, ni un autre délégué, ni son propre compte."
        ),
        request=ProfilUtilisateurSerializer,
        responses={200: CompteUtilisateurSerializer, **ERROR_400, **_ERREURS_ACTION},
    )
    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        compte = self.get_object()
        serializer = ProfilUtilisateurSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        services.modifier_profil(compte, changes=serializer.validated_data, by=self.acteur)
        return self._reponse(compte)

    @extend_schema(
        tags=[TAG],
        summary="Changer le rôle d'un compte",
        description=(
            "Seul un administrateur attribue les rôles Administrateur, RAI et Direction "
            "générale (un délégué attribue Auditeur ou Audité) ; personne ne change son "
            "propre rôle ; le dernier administrateur actif garde le sien."
        ),
        request=ChangementRoleSerializer,
        responses={200: CompteUtilisateurSerializer, **ERROR_400, **_ERREURS_ACTION},
    )
    @action(detail=True, methods=["post"], url_path="change-role")
    def change_role(self, request: Request, pk: str) -> Response:
        compte = self.get_object()
        serializer = ChangementRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.changer_role(compte, role=serializer.validated_data["role"], par=self.acteur)
        return self._reponse(compte)

    @extend_schema(
        methods=["GET"],
        tags=[TAG],
        summary="Délégation de gestion des comptes d'un agent",
        description="Administrateur seulement (un délégué ne lit pas les délégations).",
        responses={200: DelegationGestionComptesSerializer, **_ERREURS_ACTION},
    )
    @extend_schema(
        methods=["PUT"],
        tags=[TAG],
        summary="Définir la délégation de gestion des comptes d'un agent",
        description=(
            "Administrateur seulement. Les quatre droits sont obligatoires ; tout à faux "
            "révoque la délégation. Effet immédiat ; refusé sur un compte administrateur."
        ),
        request=DelegationGestionComptesSerializer,
        responses={200: DelegationGestionComptesSerializer, **ERROR_400, **_ERREURS_ACTION},
    )
    @action(detail=True, methods=["get", "put"], url_path="delegation")
    def delegation(self, request: Request, pk: str) -> Response:
        compte = self.get_object()
        if request.method == "PUT":
            serializer = DelegationGestionComptesSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            droits: dict[str, bool] = {a: serializer.validated_data[a] for a in ACTIONS}
            services.definir_delegation(compte, droits=droits, par=self.acteur)
        data = DelegationGestionComptesSerializer(services.delegation_de(compte)).data
        return Response(data)

    @extend_schema(
        tags=[TAG],
        summary="Désactiver un compte",
        request=MotifDesactivationSerializer,
        responses={200: CompteUtilisateurSerializer, **ERROR_400, **_ERREURS_ACTION},
    )
    @action(detail=True, methods=["post"])
    def deactivate(self, request: Request, pk: str) -> Response:
        compte = self.get_object()
        serializer = MotifDesactivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.desactiver(compte, motif=serializer.validated_data["motif"], by=self.acteur)
        return self._reponse(compte)

    @extend_schema(
        tags=[TAG],
        summary="Réactiver un compte",
        request=None,
        responses={200: CompteUtilisateurSerializer, **_ERREURS_ACTION},
    )
    @action(detail=True, methods=["post"])
    def reactivate(self, request: Request, pk: str) -> Response:
        compte = self.get_object()
        services.reactiver(compte, by=self.acteur)
        return self._reponse(compte)

    @extend_schema(
        tags=[TAG],
        summary="Importer des comptes depuis un fichier CSV",
        description=(
            "Crée des comptes locaux (rôle obligatoire, ADMIN exclu), chacun avec un mot de "
            "passe temporaire (72 h, à changer à la première connexion), envoyé par courriel "
            "de bienvenue si l'envoi est actif. Les mots de passe qui ne partent pas vont dans "
            "un fichier à télécharger une seule fois (`fichier_mots_de_passe_id`)."
        ),
        request={"multipart/form-data": ImportCsvSerializer},
        responses={200: RapportImportSerializer, **ERROR_400, **ERROR_RESPONSES, **ERROR_429},
    )
    @action(detail=False, methods=["post"], url_path="import-csv", parser_classes=[MultiPartParser])
    def import_csv(self, request: Request) -> Response:
        serializer = ImportCsvSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fichier = serializer.validated_data["fichier"]
        antivirus.analyser(fichier)  # SEC-04 : tout téléversement passe par l'antivirus
        contenu = fichier.read(provisioning.CSV_MAX_BYTES + 1)
        try:
            rapport = provisioning.importer_csv(
                contenu,
                by=self.acteur,
                dry_run=serializer.validated_data["dry_run"],
                envoyer_courriel=serializer.validated_data["envoyer_courriel"],
            )
        except FichierImportInvalide as exc:
            raise serializers.ValidationError({"fichier": [exc.message]}) from exc
        return Response(RapportImportSerializer(rapport).data)

    @extend_schema(
        tags=[TAG],
        summary="Télécharger le fichier des mots de passe d'un import (une seule fois)",
        description=(
            "Fichier CSV des mots de passe temporaires qu'aucun courriel n'a portés. "
            "Réservé à l'auteur de l'import ; détruit dès ce téléchargement, et au plus "
            "tard 24 h après l'import (404 ensuite)."
        ),
        responses={
            (200, "text/csv"): OpenApiTypes.BINARY,
            **ERROR_RESPONSES,
            **ERROR_404,
        },
    )
    @action(
        detail=False,
        methods=["get"],
        url_path=r"import-passwords/(?P<fichier_id>[0-9a-fA-F-]{36})",
        filter_backends=[],
        pagination_class=None,
        content_negotiation_class=_SansNegociation,
    )
    def import_passwords(self, request: Request, fichier_id: str) -> HttpResponse:
        try:
            identifiant = UUID(fichier_id)
        except ValueError:
            raise Http404 from None
        texte = provisioning.lire_fichier_mots_de_passe(identifiant, par=self.acteur)
        reponse = HttpResponse(texte.encode("utf-8"), content_type="text/csv; charset=utf-8")
        reponse["Content-Disposition"] = 'attachment; filename="mots-de-passe-temporaires.csv"'
        reponse["Cache-Control"] = "no-store"
        reponse["X-Content-Type-Options"] = "nosniff"
        return reponse
