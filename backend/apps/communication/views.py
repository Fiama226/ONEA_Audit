"""ViewSets de l'API de la communication : aucune logique métier, tout passe par `services`.

Ordre des refus : rôle global (403) -> mission ou objet invisible (404) -> droit (403, calculé
par `droits.py`, `permissions.py` et `missions.acces`) -> sérialiseur (400, dont `confirme` absent
ou faux) -> règle métier, gel ou fenêtre d'écriture (422, portés par les services).
`confirme: true` est exigé ICI avant `valider_rapport` et avant toute réponse au provisoire : les
services n'ont pas ce paramètre, et rien n'est jamais pré-confirmé.
"""

from collections.abc import Callable
from typing import Any, TypeVar
from uuid import UUID

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    PolymorphicProxySerializer,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.viewsets import GenericViewSet

from apps.accomplissement.views import MSG_PARAMETRE, _uuid, _uuid_du_corps
from apps.core.consultations import journaliser_consultation
from apps.core.exceptions import RegleMetierError
from apps.core.schema import ERROR_400, ERROR_404, ERROR_409, ERROR_422, ERROR_RESPONSES
from apps.documents.services.generation import ouvrir_version
from apps.documents.views import DOCX, PDF, NegociationSansFormat, reponse_fichier
from apps.missions.acces import declaration_levee, est_chef, est_responsable_entite
from apps.missions.models import Mission
from apps.missions.permissions import (
    exiger,
    exiger_contribution,
    mission_du_corps,
    mission_visible,
)
from apps.missions.services import aujourd_hui
from apps.missions.views import MissionApiViewSet
from apps.users.models import Role

from . import filters, serializers
from .droits import peut_lire_rapport_interne
from .models import (
    DestinataireDiffusion,
    EvenementRapport,
    Rapport,
    RapportProvisoire,
    ReponseRapport,
)
from .permissions import (
    STATUTS_DIFFUSES,
    CommunicationAccessPermission,
    constats_du_provisoire,
    destinataires_lisibles,
    peut_lire,
    peut_telecharger,
    provisoires_lisibles,
    rapports_lisibles,
    reponses_lisibles,
)
from .services import correction as svc_correction
from .services import diffusion as svc_diffusion
from .services import provisoire as svc_provisoire
from .services import redaction as svc_redaction
from .services import soumission as svc_soumission
from .services import validation as svc_validation
from .services._textes import texte_reponse_provisoire

F = TypeVar("F", bound=Callable[..., Any])
TAG_RAPPORTS = "Rapports"
TAG_PROVISOIRE = "Rapports provisoires"
TAG_REPONSES = "Réponses au rapport provisoire"
TAG_DESTINATAIRES = "Destinataires de la diffusion"
_UUID_REGEX = "[0-9a-fA-F-]{36}"

PARAM_PROVISOIRE = OpenApiParameter(
    "provisoire", OpenApiTypes.UUID, required=True, description="Rapport provisoire (obligatoire)."
)

RapportLecture = PolymorphicProxySerializer(
    component_name="RapportLecture",
    serializers=[serializers.RapportSerializer, serializers.RapportDiffuseSerializer],
    resource_type_field_name=None,
)
RapportLectureListe = PolymorphicProxySerializer(
    component_name="RapportLecture",
    serializers=[serializers.RapportSerializer, serializers.RapportDiffuseSerializer],
    resource_type_field_name=None,
    many=True,
)


def _action_ecriture(
    tag: str,
    summary: str,
    reponse: Any,
    *,
    request: Any = None,
    code: int = 200,
    extra: dict[int, Any] | None = None,
    parametres: list[Any] | None = None,
) -> Callable[[F], F]:
    erreurs: dict[int, Any] = {**ERROR_RESPONSES, **ERROR_404, **ERROR_422}
    if request is not None or parametres:
        erreurs.update(ERROR_400)
    erreurs.update(extra or {})
    return extend_schema(
        tags=[tag],
        summary=summary,
        request=request,
        parameters=parametres,
        responses={code: reponse, **erreurs},
    )


class CommunicationBaseViewSet(MissionApiViewSet):
    # Base : accès par rôle (ADMIN refusé), UUID dans l'URL, paramètres de portée. (Un docstring
    # serait recopié dans la description OpenAPI de chaque route.)

    permission_classes = [CommunicationAccessPermission]
    lookup_value_regex = _UUID_REGEX
    # Actions ouvertes au DG (`audite_actions` est celles de l'audité).
    dg_actions: frozenset[str] = frozenset()

    def uuid_requis(self, request: Request, champ: str) -> UUID:
        brut = request.query_params.get(champ)
        if not brut:
            raise ValidationError({champ: [MSG_PARAMETRE]})
        identifiant = _uuid(brut)
        if identifiant is None:
            raise ValidationError({champ: ["Identifiant invalide."]})
        return identifiant

    def mission_requise(self, request: Request) -> Mission:
        return mission_visible(self.acteur, self.uuid_requis(request, "mission"))

    def exiger_rai(self) -> None:
        exiger(self.acteur.role == Role.RAI)

    def exiger_equipe_ou_rai(self, mission: Mission) -> None:
        exiger(peut_lire_rapport_interne(self.acteur, mission))


# --------------------------------------------------------------------------- rapports


@extend_schema_view(
    list=extend_schema(
        tags=[TAG_RAPPORTS],
        summary="Lister : rapports d'une mission, ou rapports diffusés visibles",
        description=(
            "Avec `mission` : tous les rapports pour l'équipe et le RAI, les seuls rapports "
            "diffusés pour les autres lecteurs. Sans `mission` : rapports diffusés visibles."
        ),
        responses={200: RapportLectureListe, **ERROR_400, **ERROR_RESPONSES, **ERROR_404},
    ),
    retrieve=extend_schema(
        tags=[TAG_RAPPORTS],
        summary="Détail : rapport (journalisé avant diffusion)",
        responses={200: RapportLecture, **ERROR_RESPONSES, **ERROR_404},
    ),
    create=extend_schema(
        tags=[TAG_RAPPORTS],
        summary="Créer le rapport de la mission (prérempli)",
        request=serializers.RapportCreationRequestSerializer,
        responses={
            201: serializers.RapportSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
    ),
    partial_update=extend_schema(
        tags=[TAG_RAPPORTS],
        summary="Modifier les sections du rapport",
        request=serializers.RapportModificationRequestSerializer,
        responses={
            200: serializers.RapportSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
    ),
)
class RapportViewSet(
    CommunicationBaseViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet[Rapport],
):
    serializer_class = serializers.RapportSerializer
    queryset = Rapport.objects.none()
    filterset_class = filters.RapportFilter
    ordering_fields = ("numero_version", "created_at")
    ordering = ("numero_version",)
    content_negotiation_class = NegociationSansFormat  # `?format=pdf|docx` est un format de fichier
    http_method_names = ["get", "post", "patch", "head", "options"]
    lecteurs = frozenset({"list", "retrieve", "download", "acknowledge"})
    audite_actions = lecteurs
    dg_actions = lecteurs

    def get_queryset(self) -> Any:
        from django.db.models import Prefetch

        return (
            rapports_lisibles(self.acteur)
            .select_related(
                "mission",
                "confirmation_validation__signataire",
                "diffusion__version_rapport__document",
                "diffusion__version_note",
                "diffusion__diffusee_par",
            )
            .prefetch_related(
                "provisoires",
                Prefetch("evenements", queryset=EvenementRapport.objects.select_related("par")),
            )
        )

    # -- lecture

    def _serializer_de(self, mission: Mission) -> type[BaseSerializer[Any]]:
        if peut_lire_rapport_interne(self.acteur, mission):
            return serializers.RapportSerializer
        return serializers.RapportDiffuseSerializer

    def _representer(self, pk: Any) -> Any:
        rapport = self.get_queryset().get(pk=pk)
        classe = self._serializer_de(rapport.mission)
        return classe(rapport, context=self.get_serializer_context()).data

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        classe: type[BaseSerializer[Any]] = serializers.RapportDiffuseSerializer
        queryset = self.get_queryset()
        brut = request.query_params.get("mission")
        if brut:
            identifiant = _uuid(brut)
            if identifiant is None:
                raise ValidationError({"mission": ["Identifiant invalide."]})
            if self.acteur.role != Role.DG:  # le DG ne voit aucune mission : seulement ses diffusés
                mission = mission_visible(self.acteur, identifiant)
                if peut_lire_rapport_interne(self.acteur, mission):
                    classe = serializers.RapportSerializer
        if classe is serializers.RapportDiffuseSerializer:
            queryset = queryset.filter(statut__in=STATUTS_DIFFUSES)
        page = self.paginate_queryset(self.filter_queryset(queryset))
        contexte = self.get_serializer_context()
        return self.get_paginated_response(classe(page, many=True, context=contexte).data)

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        rapport = self.get_object()
        exiger(peut_lire(self.acteur, rapport))
        if rapport.statut not in STATUTS_DIFFUSES:
            journaliser_consultation(
                rapport, par=self.acteur, action="CONSULTATION", adresse_ip=self.adresse_ip
            )
        classe = self._serializer_de(rapport.mission)
        return Response(classe(rapport, context=self.get_serializer_context()).data)

    def objet_interne(self) -> Rapport:
        """Rapport visible ET lisible avant diffusion (équipe, RAI) : sinon 403."""
        rapport: Rapport = self.get_object()
        self.exiger_equipe_ou_rai(rapport.mission)
        return rapport

    # -- rédaction

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        mission = mission_du_corps(request)
        if mission is not None:
            exiger_contribution(self.acteur, mission)
        corps = serializers.RapportCreationRequestSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        rapport = svc_redaction.creer_rapport(
            mission or corps.validated_data["mission"], by=self.acteur
        )
        return Response(self._representer(rapport.pk), status=status.HTTP_201_CREATED)

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        rapport = self.objet_interne()
        exiger_contribution(self.acteur, rapport.mission)
        corps = serializers.RapportModificationRequestSerializer(data=request.data, partial=True)
        corps.is_valid(raise_exception=True)
        svc_redaction.modifier_rapport(rapport, by=self.acteur, **corps.validated_data)
        return Response(self._representer(rapport.pk))

    @extend_schema(
        tags=[TAG_RAPPORTS],
        summary="Aperçu : assemblage courant du rapport (non figé)",
        responses={200: OpenApiTypes.OBJECT, **ERROR_RESPONSES, **ERROR_404},
    )
    @action(detail=True, methods=["get"], pagination_class=None, filter_backends=[])
    def preview(self, request: Request, pk: str | None = None) -> Response:
        rapport = self.objet_interne()
        return Response(svc_redaction.apercu(rapport))

    # -- soumission, validation, diffusion, correction

    @_action_ecriture(
        TAG_RAPPORTS, "Soumettre le rapport au RAI (chef de mission)", serializers.RapportSerializer
    )
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def submit(self, request: Request, pk: str | None = None) -> Response:
        rapport = self.objet_interne()
        mission = rapport.mission
        exiger(est_chef(self.acteur, mission) and declaration_levee(self.acteur, mission))
        svc_soumission.soumettre_rapport(rapport, by=self.acteur)
        return Response(self._representer(rapport.pk))

    @extend_schema(
        tags=[TAG_RAPPORTS],
        summary="Texte exact à confirmer pour valider le rapport, et mode de signature",
        responses={
            200: serializers.TexteValidationSerializer,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="validation-text",
        pagination_class=None,
        filter_backends=[],
    )
    def texte_validation(self, request: Request, pk: str | None = None) -> Response:
        rapport = self.objet_interne()
        self.exiger_rai()
        if rapport.instantane_soumis is None:
            raise RegleMetierError(svc_validation.MSG_STATUT)
        from apps.signatures.models import TypeDocumentSignable
        from apps.signatures.parametres import exigences, mode_requis

        mode = mode_requis(TypeDocumentSignable.VALIDATION_RAPPORT)
        exigees = exigences(TypeDocumentSignable.VALIDATION_RAPPORT)
        donnees = {
            "texte": svc_validation._texte_confirmation(rapport, self.acteur),  # noqa: SLF001
            "mode": mode,
            "confirmation_requise": exigees.confirmation,
            "signature_electronique_requise": exigees.electronique,
        }
        return Response(serializers.TexteValidationSerializer(donnees).data)

    @_action_ecriture(
        TAG_RAPPORTS,
        "Valider le rapport soumis (confirmé, RAI)",
        serializers.RapportSerializer,
        request=serializers.ValidationRequestSerializer,
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="validate",
        pagination_class=None,
        filter_backends=[],
    )
    def valider(self, request: Request, pk: str | None = None) -> Response:
        rapport = self.objet_interne()
        self.exiger_rai()
        corps = serializers.ValidationRequestSerializer(data=request.data)
        corps.is_valid(raise_exception=True)  # `confirme` absent ou faux : 400, rien d'écrit
        svc_validation.valider_rapport(rapport, by=self.acteur, adresse_ip=self.adresse_ip)
        return Response(self._representer(rapport.pk))

    @_action_ecriture(
        TAG_RAPPORTS,
        "Renvoyer le rapport soumis à l'équipe (motif, RAI)",
        serializers.RapportSerializer,
        request=serializers.MotifRequestSerializer,
    )
    @action(
        detail=True, methods=["post"], url_path="return", pagination_class=None, filter_backends=[]
    )
    def renvoyer(self, request: Request, pk: str | None = None) -> Response:
        rapport = self.objet_interne()
        self.exiger_rai()
        corps = serializers.MotifRequestSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        svc_validation.renvoyer_rapport(
            rapport, motif=corps.validated_data["motif"], by=self.acteur
        )
        return Response(self._representer(rapport.pk))

    @_action_ecriture(
        TAG_RAPPORTS,
        "Diffuser le rapport validé (RAI)",
        serializers.RapportSerializer,
        request=serializers.DiffusionRequestSerializer,
    )
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def distribute(self, request: Request, pk: str | None = None) -> Response:
        rapport = self.objet_interne()
        self.exiger_rai()
        corps = serializers.DiffusionRequestSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        svc_diffusion.diffuser(rapport, message=corps.validated_data["message"], by=self.acteur)
        return Response(self._representer(rapport.pk))

    @_action_ecriture(
        TAG_RAPPORTS,
        "Émettre un rapport corrigé (motif, RAI)",
        serializers.RapportSerializer,
        request=serializers.MotifRequestSerializer,
        code=201,
    )
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def correct(self, request: Request, pk: str | None = None) -> Response:
        rapport = self.objet_interne()
        self.exiger_rai()
        corps = serializers.MotifRequestSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        corrige = svc_correction.emettre_rapport_corrige(
            rapport, motif=corps.validated_data["motif"], by=self.acteur
        )
        return Response(self._representer(corrige.pk), status=status.HTTP_201_CREATED)

    @_action_ecriture(
        TAG_RAPPORTS,
        "Accuser réception du rapport diffusé (destinataire)",
        serializers.RapportDiffuseSerializer,
    )
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def acknowledge(self, request: Request, pk: str | None = None) -> Response:
        rapport = self.get_object()
        exiger(peut_lire(self.acteur, rapport))
        svc_diffusion.accuser_reception(rapport, by=self.acteur)
        return Response(self._representer(rapport.pk))

    @_action_ecriture(
        TAG_RAPPORTS,
        "Transmettre le rapport provisoire aux audités (chef de mission ou RAI)",
        serializers.RapportProvisoireSerializer,
        request=serializers.TransmissionRequestSerializer,
        code=201,
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="transmit-draft",
        pagination_class=None,
        filter_backends=[],
    )
    def transmettre_provisoire(self, request: Request, pk: str | None = None) -> Response:
        rapport = self.objet_interne()
        mission = rapport.mission
        exiger(
            self.acteur.role == Role.RAI
            or (est_chef(self.acteur, mission) and declaration_levee(self.acteur, mission))
        )
        corps = serializers.TransmissionRequestSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        provisoire = svc_provisoire.transmettre_provisoire(
            rapport, by=self.acteur, delai_jours=corps.validated_data["delai_jours"]
        )
        lu = provisoires_lisibles(self.acteur).get(pk=provisoire.pk)
        donnees = serializers.RapportProvisoireSerializer(
            lu, context=self.get_serializer_context()
        ).data
        return Response(donnees, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=[TAG_RAPPORTS],
        summary="Télécharger : version diffusée du rapport ou de la note (journalisé)",
        parameters=[serializers.TelechargementQuerySerializer],
        responses={
            200: OpenApiTypes.BINARY,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_409,
        },
    )
    @action(detail=True, methods=["get"], pagination_class=None, filter_backends=[])
    def download(self, request: Request, pk: str | None = None) -> FileResponse:
        rapport = self.get_object()
        # Version non diffusée, ou lecteur hors périmètre : 404 (l'existence n'est pas révélée).
        if rapport.statut not in STATUTS_DIFFUSES or not peut_telecharger(self.acteur, rapport):
            raise Http404
        requete = serializers.TelechargementQuerySerializer(data=request.query_params)
        requete.is_valid(raise_exception=True)
        diffusion = rapport.diffusion
        version = (
            diffusion.version_rapport
            if requete.validated_data["document"] == "rapport"
            else diffusion.version_note
        )
        if version is None:
            raise Http404
        format_ = requete.validated_data["format"]
        contenu, nom = ouvrir_version(
            version, format=format_.upper(), by=self.acteur, adresse_ip=self.adresse_ip
        )
        svc_diffusion.noter_consultation(rapport, self.acteur)
        return reponse_fichier(contenu, nom, PDF if format_ == "pdf" else DOCX)


# --------------------------------------------------------------------------- provisoire


@extend_schema_view(
    list=extend_schema(
        tags=[TAG_PROVISOIRE],
        summary="Lister : rapports provisoires d'un rapport ou d'une mission",
        responses={
            200: serializers.RapportProvisoireSerializer(many=True),
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
        },
    ),
    retrieve=extend_schema(
        tags=[TAG_PROVISOIRE],
        summary="Détail : rapport provisoire",
        responses={200: serializers.RapportProvisoireSerializer, **ERROR_RESPONSES, **ERROR_404},
    ),
)
class RapportProvisoireViewSet(
    CommunicationBaseViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet[Any]
):
    serializer_class = serializers.RapportProvisoireSerializer
    queryset = RapportProvisoire.objects.none()
    filterset_class = filters.ProvisoireFilter
    ordering_fields = ("numero", "transmis_le")
    ordering = ("numero",)
    audite_actions = frozenset({"list", "retrieve"})

    def get_queryset(self) -> Any:
        return provisoires_lisibles(self.acteur).select_related("mission", "rapport")

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        if request.query_params.get("rapport"):
            identifiant = self.uuid_requis(request, "rapport")
            get_object_or_404(rapports_lisibles(self.acteur), pk=identifiant)
        else:
            self.mission_requise(request)
        return super().list(request, *args, **kwargs)


# --------------------------------------------------------------------------- réponses


@extend_schema_view(
    list=extend_schema(
        tags=[TAG_REPONSES],
        summary="Lister : réponses au rapport provisoire (l'audité : les siennes)",
        parameters=[PARAM_PROVISOIRE],
        responses={
            200: serializers.ReponseRapportSerializer(many=True),
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
        },
    ),
    create=extend_schema(
        tags=[TAG_REPONSES],
        summary="Répondre à un constat du rapport provisoire (confirmé)",
        request=serializers.ReponseRapportRequestSerializer,
        responses={
            201: serializers.ReponseRapportSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
    ),
)
class ReponseRapportViewSet(
    CommunicationBaseViewSet, mixins.ListModelMixin, mixins.CreateModelMixin, GenericViewSet[Any]
):
    serializer_class = serializers.ReponseRapportSerializer
    queryset = ReponseRapport.objects.none()
    filterset_class = filters.ReponseFilter
    ordering_fields = ("created_at",)
    ordering = ("created_at",)
    audite_actions = frozenset({"list", "create", "texte"})

    def get_queryset(self) -> Any:
        return reponses_lisibles(self.acteur).select_related(
            "auteur", "confirmation__signataire", "provisoire"
        )

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        identifiant = self.uuid_requis(request, "provisoire")
        get_object_or_404(provisoires_lisibles(self.acteur), pk=identifiant)
        return super().list(request, *args, **kwargs)

    def _cibles(self, provisoire: Any, constat: Any) -> None:
        """Droit de répondre (403) : audité responsable de l'entité du constat."""
        exiger(self.acteur.role == Role.AUDITE)
        exiger(
            constat.entite_id is not None
            and est_responsable_entite(self.acteur, provisoire.mission, constat.entite_id)
        )

    def _objets_du_corps(self, request: Request) -> tuple[Any, Any]:
        """Provisoire et constat du corps, visibles (404 sinon) ; `None` : 400 du sérialiseur."""
        provisoire = constat = None
        brut = _uuid_du_corps(request, "provisoire")
        if brut is not None:
            provisoire = get_object_or_404(
                provisoires_lisibles(self.acteur).select_related("mission"), pk=brut
            )
        brut = _uuid_du_corps(request, "constat")
        if brut is not None:
            constat = get_object_or_404(constats_du_provisoire(self.acteur), pk=brut)
        return provisoire, constat

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        exiger(self.acteur.role == Role.AUDITE)
        provisoire, constat = self._objets_du_corps(request)
        if provisoire is not None and constat is not None:
            self._cibles(provisoire, constat)
        corps = serializers.ReponseRapportRequestSerializer(data=request.data)
        corps.is_valid(raise_exception=True)  # `confirme` absent ou faux : 400
        reponse = svc_provisoire.repondre_provisoire(
            corps.validated_data["provisoire"],
            constat=corps.validated_data["constat"],
            commentaire=corps.validated_data["commentaire"],
            by=self.acteur,
            adresse_ip=self.adresse_ip,
        )
        lue = self.get_queryset().get(pk=reponse.pk)
        return Response(self.get_serializer(lue).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=[TAG_REPONSES],
        summary="Texte exact à confirmer pour répondre à un constat",
        parameters=[
            PARAM_PROVISOIRE,
            OpenApiParameter(
                "constat", OpenApiTypes.UUID, required=True, description="Constat (obligatoire)."
            ),
        ],
        responses={
            200: serializers.TexteReponseRapportSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
        },
    )
    @action(detail=False, methods=["get"], pagination_class=None, filter_backends=[])
    def texte(self, request: Request) -> Response:
        exiger(self.acteur.role == Role.AUDITE)
        provisoire = get_object_or_404(
            provisoires_lisibles(self.acteur).select_related("mission"),
            pk=self.uuid_requis(request, "provisoire"),
        )
        constat = get_object_or_404(
            constats_du_provisoire(self.acteur), pk=self.uuid_requis(request, "constat")
        )
        self._cibles(provisoire, constat)
        courant = svc_provisoire.provisoire_courant(provisoire.rapport) or provisoire
        donnees = {
            "texte": texte_reponse_provisoire(
                constat, provisoire, self.acteur, mission_reference=provisoire.mission.reference
            ),
            "date_limite_reponses": courant.date_limite_reponses,
            "hors_delai": aujourd_hui() > courant.date_limite_reponses,
        }
        return Response(serializers.TexteReponseRapportSerializer(donnees).data)


# --------------------------------------------------------------------------- destinataires


@extend_schema_view(
    list=extend_schema(
        tags=[TAG_DESTINATAIRES],
        summary="Lister : destinataires de la diffusion (RAI, chef ; sinon sa propre ligne)",
        parameters=[
            OpenApiParameter(
                "rapport", OpenApiTypes.UUID, required=True, description="Rapport (obligatoire)."
            )
        ],
        responses={
            200: serializers.DestinataireSerializer(many=True),
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
        },
    ),
    retrieve=extend_schema(
        tags=[TAG_DESTINATAIRES],
        summary="Détail : destinataire de la diffusion",
        responses={200: serializers.DestinataireSerializer, **ERROR_RESPONSES, **ERROR_404},
    ),
    create=extend_schema(
        tags=[TAG_DESTINATAIRES],
        summary="Ajouter un destinataire (RAI)",
        request=serializers.DestinataireCreationRequestSerializer,
        responses={
            201: serializers.DestinataireSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
    ),
    partial_update=extend_schema(
        tags=[TAG_DESTINATAIRES],
        summary="Modifier un destinataire (RAI)",
        request=serializers.DestinataireModificationRequestSerializer,
        responses={
            200: serializers.DestinataireSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
    ),
    destroy=extend_schema(
        tags=[TAG_DESTINATAIRES],
        summary="Retirer un destinataire (RAI)",
        responses={204: None, **ERROR_RESPONSES, **ERROR_404, **ERROR_422},
    ),
)
class DestinataireViewSet(
    CommunicationBaseViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet[Any],
):
    serializer_class = serializers.DestinataireSerializer
    queryset = DestinataireDiffusion.objects.none()
    filterset_class = filters.DestinataireFilter
    ordering_fields = ("created_at",)
    ordering = ("created_at",)
    lecteurs = frozenset({"list", "retrieve"})
    audite_actions = lecteurs
    dg_actions = lecteurs

    def get_queryset(self) -> Any:
        return destinataires_lisibles(self.acteur).select_related("utilisateur")

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        identifiant = self.uuid_requis(request, "rapport")
        get_object_or_404(rapports_lisibles(self.acteur), pk=identifiant)
        return super().list(request, *args, **kwargs)

    def _representer(self, pk: Any) -> Any:
        return self.get_serializer(self.get_queryset().get(pk=pk)).data

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self.exiger_rai()
        brut = _uuid_du_corps(request, "rapport")
        if brut is not None:
            get_object_or_404(rapports_lisibles(self.acteur), pk=brut)
        corps = serializers.DestinataireCreationRequestSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        donnees = corps.validated_data
        destinataire = svc_diffusion.ajouter_destinataire(
            donnees["rapport"],
            by=self.acteur,
            categorie=donnees["categorie"],
            utilisateur=donnees.get("utilisateur"),
            nom_externe=donnees["nom_externe"],
            qualite=donnees["qualite"],
        )
        return Response(self._representer(destinataire.pk), status=status.HTTP_201_CREATED)

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self.exiger_rai()
        destinataire = self.get_object()
        corps = serializers.DestinataireModificationRequestSerializer(
            data=request.data, partial=True
        )
        corps.is_valid(raise_exception=True)
        svc_diffusion.modifier_destinataire(destinataire, by=self.acteur, **corps.validated_data)
        return Response(self._representer(destinataire.pk))

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self.exiger_rai()
        destinataire = self.get_object()
        svc_diffusion.retirer_destinataire(destinataire, by=self.acteur)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @_action_ecriture(
        TAG_DESTINATAIRES,
        "Dater la remise hors plateforme à un destinataire externe (RAI)",
        serializers.DestinataireSerializer,
        request=serializers.RemiseRequestSerializer,
    )
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def delivered(self, request: Request, pk: str | None = None) -> Response:
        self.exiger_rai()
        destinataire = self.get_object()
        corps = serializers.RemiseRequestSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        svc_diffusion.marquer_remis_hors_plateforme(
            destinataire, le=corps.validated_data["le"], by=self.acteur
        )
        return Response(self._representer(destinataire.pk))
