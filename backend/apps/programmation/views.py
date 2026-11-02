"""ViewSets du programme annuel : aucune logique métier, tout passe par `services`."""

from decimal import Decimal
from typing import Any, ClassVar, cast

from django.db.models import Count, DecimalField, Prefetch, Q, QuerySet, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.viewsets import ModelViewSet

from apps.core.filters import StableOrderingFilter
from apps.core.schema import (
    ERROR_400,
    ERROR_404,
    ERROR_422,
    ERROR_429,
    ERROR_RESPONSES,
    crud_schema,
)
from apps.core.throttling import ThrottleParActionMixin
from apps.referentiel.models import Direction
from apps.referentiel.permissions import RolePermission
from apps.referentiel.renderers import PassthroughRenderer
from apps.users.models import User

from . import exports, pdf, services
from .filters import LigneFilter, ProgrammeFilter
from .models import LigneProgramme, ProgrammeAnnuel
from .permissions import ECRITURE_PROGRAMME, LECTURE_PROGRAMME
from .serializers import (
    LigneProgrammeSerializer,
    ProgrammeAnnuelSerializer,
    SyntheseProgrammeSerializer,
)

TAG = "Programme annuel"


class _ProgrammeViewSet[M: ProgrammeAnnuel | LigneProgramme](
    ThrottleParActionMixin, ModelViewSet[M]
):
    permission_classes = [RolePermission]
    filter_backends = [DjangoFilterBackend, StableOrderingFilter]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    read_roles: ClassVar[tuple[str, ...]] = LECTURE_PROGRAMME
    write_roles: ClassVar[tuple[str, ...]] = ECRITURE_PROGRAMME
    throttle_scopes: ClassVar[dict[str, str]] = {"export": "export"}

    @property
    def acteur(self) -> User:
        return cast(User, self.request.user)

    def _publier(self, serializer: BaseSerializer[Any], obj: M) -> None:
        """Renvoie la représentation de lecture (annotations et préchargements inclus)."""
        serializer.instance = self.get_queryset().get(pk=obj.pk)


def _programmes_annotes() -> QuerySet[ProgrammeAnnuel]:
    actives = Q(lignes__deleted_at__isnull=True)
    return ProgrammeAnnuel.objects.select_related("valide_par").annotate(
        nb_lignes=Count("lignes", filter=actives),
        charge_totale_jours=Coalesce(
            Sum("lignes__charge_prevue_jours", filter=actives),
            Value(Decimal("0")),
            output_field=DecimalField(max_digits=10, decimal_places=1),
        ),
    )


@crud_schema(ProgrammeAnnuelSerializer, TAG, "programmes annuels d'audit")
class ProgrammeAnnuelViewSet(_ProgrammeViewSet[ProgrammeAnnuel]):
    serializer_class = ProgrammeAnnuelSerializer
    filterset_class = ProgrammeFilter
    ordering_fields = ("annee",)
    ordering = ("-annee",)

    def get_queryset(self) -> QuerySet[ProgrammeAnnuel]:
        return _programmes_annotes()

    def perform_create(self, serializer: BaseSerializer[ProgrammeAnnuel]) -> None:
        obj = services.creer_programme(**serializer.validated_data, by=self.acteur)
        self._publier(serializer, obj)

    def perform_update(self, serializer: BaseSerializer[ProgrammeAnnuel]) -> None:
        obj = services.modifier_programme(
            cast(ProgrammeAnnuel, serializer.instance),
            **serializer.validated_data,
            by=self.acteur,
        )
        self._publier(serializer, obj)

    def perform_destroy(self, instance: ProgrammeAnnuel) -> None:
        services.supprimer_programme(instance, by=self.acteur)

    @extend_schema(
        tags=[TAG],
        summary="Valider (figer) un programme annuel",
        request=None,
        responses={
            200: ProgrammeAnnuelSerializer,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
    )
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def validate(self, request: Request, pk: str | None = None) -> Response:
        programme = self.get_object()
        services.valider_programme(programme, by=self.acteur)
        return Response(ProgrammeAnnuelSerializer(self.get_queryset().get(pk=programme.pk)).data)

    @extend_schema(
        tags=[TAG],
        summary="Exporter un programme annuel (CSV, XLSX ou PDF)",
        description=(
            "Télécharge le programme : missions prévues (CSV ou XLSX) ; le XLSX ajoute "
            "une feuille de synthèse ; le PDF (paysage A4) reproduit le modèle d'impression ONEA."
        ),
        parameters=[
            OpenApiParameter(
                "type",
                OpenApiTypes.STR,
                required=True,
                enum=["csv", "xlsx", "pdf"],
                description="Format du fichier : csv (UTF-8, séparateur « ; »), xlsx ou pdf.",
            ),
        ],
        responses={
            (200, exports.TYPE_CSV): OpenApiTypes.BINARY,
            (200, exports.TYPE_XLSX): OpenApiTypes.BINARY,
            (200, pdf.TYPE_PDF): OpenApiTypes.BINARY,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_429,
        },
    )
    @action(
        detail=True,
        methods=["get"],
        pagination_class=None,
        filter_backends=[],
        renderer_classes=[JSONRenderer, PassthroughRenderer],
    )
    def export(self, request: Request, pk: str | None = None) -> HttpResponse:
        format_ = request.query_params.get("type")
        if format_ not in ("csv", "xlsx", "pdf"):
            raise ValidationError({"type": ["Format attendu : csv, xlsx ou pdf."]})
        programme = self.get_object()
        if format_ == "csv":
            contenu, type_mime = exports.exporter_csv(programme), exports.TYPE_CSV
        elif format_ == "xlsx":
            contenu, type_mime = exports.exporter_xlsx(programme), exports.TYPE_XLSX
        else:
            contenu, type_mime = pdf.exporter_pdf(programme), pdf.TYPE_PDF
        reponse = HttpResponse(contenu, content_type=type_mime)
        reponse["Content-Disposition"] = (
            f'attachment; filename="{exports.nom_fichier(programme, format_)}"'
        )
        return reponse

    def finalize_response(
        self, request: Request, response: Response, *args: Any, **kwargs: Any
    ) -> Response:
        # Export : le moteur « passthrough » accepte tout `Accept`, mais les erreurs
        # (400, 403, 404...) restent du JSON.
        final = super().finalize_response(request, response, *args, **kwargs)
        if self.action == "export" and isinstance(final, Response) and final.status_code >= 400:
            final.accepted_renderer = JSONRenderer()
            final.accepted_media_type = "application/json"
        return final

    @extend_schema(
        tags=[TAG],
        summary="Synthèse d'un programme annuel",
        responses={200: SyntheseProgrammeSerializer, **ERROR_RESPONSES, **ERROR_404},
    )
    @action(detail=True, methods=["get"], pagination_class=None, filter_backends=[])
    def summary(self, request: Request, pk: str | None = None) -> Response:
        resultat = services.synthese(self.get_object())
        return Response(
            SyntheseProgrammeSerializer(
                {
                    "nb_lignes": resultat.nb_lignes,
                    "charge_totale_jours": resultat.charge_totale_jours,
                    "par_type": resultat.par_type,
                    "par_trimestre": {str(q): n for q, n in resultat.par_trimestre.items()},
                }
            ).data
        )


@crud_schema(LigneProgrammeSerializer, TAG, "missions prévues du programme annuel")
class LigneProgrammeViewSet(_ProgrammeViewSet[LigneProgramme]):
    serializer_class = LigneProgrammeSerializer
    filterset_class = LigneFilter
    ordering_fields = ("debut_prevu", "numero", "titre", "processus__code")
    ordering = ("debut_prevu", "numero")

    def get_queryset(self) -> QuerySet[LigneProgramme]:
        # Lecture sur `all_objects` (D6) : un élément supprimé du référentiel reste affiché.
        return LigneProgramme.objects.select_related(
            "programme", "processus", "objet_auditable"
        ).prefetch_related(Prefetch("entites", queryset=Direction.all_objects.order_by("code")))

    def perform_create(self, serializer: BaseSerializer[LigneProgramme]) -> None:
        obj = services.creer_ligne(**serializer.validated_data, by=self.acteur)
        self._publier(serializer, obj)

    def perform_update(self, serializer: BaseSerializer[LigneProgramme]) -> None:
        obj = services.modifier_ligne(
            cast(LigneProgramme, serializer.instance),
            **serializer.validated_data,
            by=self.acteur,
        )
        self._publier(serializer, obj)

    def perform_destroy(self, instance: LigneProgramme) -> None:
        services.supprimer_ligne(instance, by=self.acteur)
