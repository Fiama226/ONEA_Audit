"""API des tableaux de bord : lecture seule, aucun calcul dans les vues (`services`, `exports`)."""

from collections.abc import Iterable
from typing import Any, cast

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.schema import ERROR_400, ERROR_429, ERROR_RESPONSES
from apps.missions.services import aujourd_hui
from apps.referentiel.renderers import PassthroughRenderer
from apps.users.models import Role, User
from apps.users.permissions import HasRole

from . import exports, services
from .serializers import (
    TableauAuditeSerializer,
    TableauAuditeurSerializer,
    TableauDgSerializer,
    TableauRaiSerializer,
)

TAG = "Tableaux de bord"
ANNEE_MIN, ANNEE_MAX = 2000, 2100

PARAM_ANNEE = OpenApiParameter(
    "annee",
    OpenApiTypes.INT,
    description=f"Année ({ANNEE_MIN} à {ANNEE_MAX}) ; défaut : l'année courante.",
)


def annee_demandee(request: Request) -> int:
    """`annee` : entier entre 2000 et 2100 (défaut : l'année courante), sinon 400."""
    brut = request.query_params.get("annee")
    if brut is None:
        return aujourd_hui().year
    if not brut.isascii() or not brut.isdigit() or not ANNEE_MIN <= int(brut) <= ANNEE_MAX:
        raise ValidationError({"annee": [f"Année attendue entre {ANNEE_MIN} et {ANNEE_MAX}."]})
    return int(brut)


class _TableauView(APIView):
    pagination_class = None

    def utilisateur(self) -> User:
        return cast(User, self.request.user)


class TableauRaiView(_TableauView):
    permission_classes = [HasRole(Role.RAI)]

    @extend_schema(
        tags=[TAG],
        summary="Tableau de bord du RAI",
        parameters=[PARAM_ANNEE],
        responses={200: TableauRaiSerializer, **ERROR_400, **ERROR_RESPONSES},
    )
    def get(self, request: Request) -> Response:
        donnees = services.tableau_rai(annee_demandee(request), aujourd_hui())
        return Response(TableauRaiSerializer(donnees).data)


class TableauAuditeurView(_TableauView):
    permission_classes = [HasRole(Role.AUDITEUR)]

    @extend_schema(
        tags=[TAG],
        summary="Tableau de bord de l'auditeur",
        responses={200: TableauAuditeurSerializer, **ERROR_RESPONSES},
    )
    def get(self, request: Request) -> Response:
        donnees = services.tableau_auditeur(self.utilisateur(), aujourd_hui())
        return Response(TableauAuditeurSerializer(donnees).data)


class TableauAuditeView(_TableauView):
    permission_classes = [HasRole(Role.AUDITE)]

    @extend_schema(
        tags=[TAG],
        summary="Tableau de bord de l'audité",
        responses={200: TableauAuditeSerializer, **ERROR_RESPONSES},
    )
    def get(self, request: Request) -> Response:
        donnees = services.tableau_audite(self.utilisateur(), aujourd_hui())
        return Response(TableauAuditeSerializer(donnees).data)


class TableauDgView(_TableauView):
    permission_classes = [HasRole(Role.DG, Role.RAI)]

    @extend_schema(
        tags=[TAG],
        summary="Tableau de bord de la direction générale",
        parameters=[PARAM_ANNEE],
        responses={200: TableauDgSerializer, **ERROR_400, **ERROR_RESPONSES},
    )
    def get(self, request: Request) -> Response:
        donnees = services.tableau_dg(annee_demandee(request), aujourd_hui())
        return Response(TableauDgSerializer(donnees).data)


class _SansNegociation(BaseContentNegotiation):
    """Le paramètre `format` désigne ici le fichier exporté, pas un rendu DRF : on l'ignore."""

    def select_renderer(
        self, request: Request, renderers: Iterable[BaseRenderer], format_suffix: str | None = None
    ) -> tuple[BaseRenderer, str]:
        premier = next(iter(renderers))
        return premier, premier.media_type


class TauxExportView(_TableauView):
    permission_classes = [HasRole(Role.DG, Role.RAI)]
    throttle_scope = "export"
    renderer_classes = [PassthroughRenderer, JSONRenderer]
    content_negotiation_class = _SansNegociation

    @extend_schema(
        tags=[TAG],
        summary="Exporter les taux de mise en oeuvre (CSV ou XLSX)",
        parameters=[
            PARAM_ANNEE,
            OpenApiParameter(
                "format",
                OpenApiTypes.STR,
                required=True,
                enum=["csv", "xlsx"],
                description="Format du fichier : csv (UTF-8, séparateur « ; ») ou xlsx.",
            ),
        ],
        responses={
            (200, exports.TYPE_CSV): OpenApiTypes.BINARY,
            (200, exports.TYPE_XLSX): OpenApiTypes.BINARY,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_429,
        },
    )
    def get(self, request: Request) -> HttpResponse:
        format_ = request.query_params.get("format")
        if format_ not in ("csv", "xlsx"):
            raise ValidationError({"format": ["Format attendu : csv ou xlsx."]})
        annee = annee_demandee(request)
        donnees = services.tableau_dg(annee, aujourd_hui())
        if format_ == "csv":
            contenu, type_mime = exports.exporter_csv(donnees), exports.TYPE_CSV
        else:
            contenu, type_mime = exports.exporter_xlsx(donnees), exports.TYPE_XLSX
        reponse = HttpResponse(contenu, content_type=type_mime)
        reponse["Content-Disposition"] = (
            f'attachment; filename="{exports.nom_fichier(annee, format_)}"'
        )
        return reponse

    def finalize_response(
        self, request: Request, response: Response, *args: Any, **kwargs: Any
    ) -> Response:
        final = super().finalize_response(request, response, *args, **kwargs)
        if isinstance(final, Response) and final.status_code >= 400:
            final.accepted_renderer = JSONRenderer()
            final.accepted_media_type = "application/json"
        return final
