"""ViewSets de l'API du suivi : aucune logique métier, tout passe par `services`.

Ordre des refus : rôle global (403, ADMIN inclus) -> objet invisible (404) -> droit (403, calculé
par `droits.py`) -> sérialiseur (400) -> règle métier, état ou gel (422, portés par les services).
Les listes sont bornées : le contexte des droits est calculé une fois par page, les relations
sont chargées par jointure ou par un préchargement unique.
"""

from collections.abc import Callable, Sequence
from typing import Any, ClassVar, TypeVar
from uuid import UUID

from django.db.models import Count, Prefetch, Q, QuerySet
from django.http import HttpResponse
from django.http.response import HttpResponseBase
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.http import content_disposition_header
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accomplissement.fichiers import MSG_TAILLE, taille_maximale
from apps.accomplissement.views import (
    _MARGE_MULTIPART,
    MSG_PARAMETRE,
    NegociationTelechargement,
    _uuid,
    _uuid_du_corps,
)
from apps.constats.models import Recommandation
from apps.core.exceptions import RegleMetierError
from apps.core.schema import (
    ERROR_400,
    ERROR_404,
    ERROR_409,
    ERROR_422,
    ERROR_429,
    ERROR_RESPONSES,
)
from apps.core.throttling import ThrottleParActionMixin
from apps.documents.views import nom_telechargement
from apps.missions.models import Mission
from apps.missions.views import MissionApiViewSet
from apps.users.models import Role

from . import droits, exports, filters, serializers
from .droits import contexte_suivi, missions_suivi_visibles, suivis_visibles
from .models import (
    STATUTS_CLOS,
    DemandeReport,
    EvenementSuivi,
    PreuveMiseEnOeuvre,
    StatutDemandeReport,
    SuiviAction,
)
from .permissions import SuiviAccessPermission
from .services import cloture, preuves, registre, reports, workflow

_F = TypeVar("_F", bound=Callable[..., Any])
TAG_ACTIONS = "Suivi des actions"
TAG_REGISTRE = "Registre des recommandations"
TAG_PREUVES = "Preuves de mise en œuvre"
TAG_REPORTS = "Reports d'échéance"
TAG_MISSIONS = "Clôture des missions suivies"
_UUID_REGEX = "[0-9a-fA-F-]{36}"
_FORMAT_EXPORT = OpenApiParameter(
    "format",
    OpenApiTypes.STR,
    required=True,
    enum=["csv", "xlsx"],
    description="Format du fichier : csv (UTF-8, séparateur « ; ») ou xlsx.",
)
_REPONSES_EXPORT: dict[Any, Any] = {
    (200, exports.TYPE_CSV): OpenApiTypes.BINARY,
    (200, exports.TYPE_XLSX): OpenApiTypes.BINARY,
    **ERROR_400,
    **ERROR_RESPONSES,
    **ERROR_422,
    **ERROR_429,
}


class SuiviBaseViewSet(ThrottleParActionMixin, MissionApiViewSet):
    """Base : rôle global (R11), contexte des droits calculé une fois par page."""

    permission_classes = [SuiviAccessPermission]
    lookup_value_regex = _UUID_REGEX
    roles_suivi: ClassVar[tuple[str, ...]]
    avec_contexte: ClassVar[bool] = True

    def paginate_queryset(self, queryset: QuerySet[Any] | Sequence[Any]) -> list[Any] | None:
        page = super().paginate_queryset(queryset)
        if page is not None and self.avec_contexte:
            self._contexte_page = contexte_suivi(self.acteur, {o.mission_id for o in page})
        return page

    def get_serializer_context(self) -> dict[str, Any]:
        contexte = dict(super().get_serializer_context())
        contexte["contexte_suivi"] = getattr(self, "_contexte_page", None)
        return contexte

    def suivi_visible(self, identifiant: UUID) -> SuiviAction:
        """Action visible, sinon 404."""
        suivi: SuiviAction = get_object_or_404(
            suivis_visibles(self.acteur).select_related("mission", "responsable"), pk=identifiant
        )
        return suivi


def _reponse_export(contenu: bytes, prefixe: str, fmt: str) -> HttpResponse:
    type_mime = exports.TYPE_CSV if fmt == "csv" else exports.TYPE_XLSX
    reponse = HttpResponse(contenu, content_type=type_mime)
    reponse["Content-Disposition"] = content_disposition_header(
        True, exports.nom_fichier(prefixe, fmt)
    )
    reponse["Cache-Control"] = "private, no-store"
    reponse["X-Content-Type-Options"] = "nosniff"
    return reponse


def _format_export(request: Request) -> str:
    fmt = request.query_params.get("format")
    if fmt not in exports.FORMATS:
        raise ValidationError({"format": ["Format attendu : csv ou xlsx."]})
    return str(fmt)


def _schema_transition(resume: str, requete: Any) -> Callable[[_F], _F]:
    decorateur: Callable[[_F], _F] = extend_schema(
        tags=[TAG_ACTIONS],
        summary=resume,
        request=requete,
        responses={
            200: serializers.SuiviActionSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
    )
    return decorateur


# --------------------------------------------------------------------------- actions


@extend_schema_view(
    list=extend_schema(
        tags=[TAG_ACTIONS],
        summary="Lister : actions suivies",
        responses={
            200: serializers.SuiviActionSerializer(many=True),
            **ERROR_400,
            **ERROR_RESPONSES,
        },
    ),
    retrieve=extend_schema(
        tags=[TAG_ACTIONS],
        summary="Détail : action suivie",
        responses={200: serializers.SuiviActionSerializer, **ERROR_RESPONSES, **ERROR_404},
    ),
    partial_update=extend_schema(
        tags=[TAG_ACTIONS],
        summary="Changer le responsable d'une action (RAI)",
        request=serializers.ResponsableRequestSerializer,
        responses={
            200: serializers.SuiviActionSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
    ),
)
class SuiviActionViewSet(SuiviBaseViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    serializer_class = serializers.SuiviActionSerializer
    queryset = SuiviAction.objects.none()
    filterset_class = filters.SuiviActionFilter
    ordering_fields = ("echeance", "statut", "derniere_activite_le")
    ordering = ("echeance",)
    throttle_scopes: ClassVar[dict[str, str]] = {"export": "export"}

    def get_queryset(self) -> QuerySet[SuiviAction]:
        base = suivis_visibles(self.acteur).select_related(
            "mission",
            "recommandation__constat",
            "entite",
            "responsable",
            "declaree_par",
            "verifiee_par",
            "cloturee_par",
            "action",
        )
        if self.action == "export":
            return base
        en_attente = DemandeReport.objects.filter(
            statut=StatutDemandeReport.EN_ATTENTE
        ).select_related("demandee_par", "decidee_par", "mission", "suivi")
        return base.annotate(
            nombre_preuves=Count("preuves", filter=Q(preuves__deleted_at__isnull=True))
        ).prefetch_related(
            Prefetch("demandes_report", queryset=en_attente, to_attr="report_en_attente")
        )

    def _operer(
        self,
        request: Request,
        code: str,
        requete: Any,
        appeler: Callable[[SuiviAction, dict[str, Any]], Any],
    ) -> Response:
        suivi = self.get_object()
        droits.exiger_droit_action(self.acteur, suivi, code)
        corps = requete(data=request.data)
        corps.is_valid(raise_exception=True)
        appeler(suivi, corps.validated_data)
        return Response(self.lire(suivi.pk))

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._operer(
            request,
            "CHANGER_RESPONSABLE",
            serializers.ResponsableRequestSerializer,
            lambda s, d: workflow.changer_responsable(
                s, responsable=d["responsable"], by=self.acteur
            ),
        )

    @_schema_transition("Démarrer une action", serializers.CommentaireRequestSerializer)
    @action(detail=True, methods=["post"], url_path="start", pagination_class=None)
    def start(self, request: Request, pk: str | None = None) -> Response:
        return self._operer(
            request,
            "DEMARRER",
            serializers.CommentaireRequestSerializer,
            lambda s, d: workflow.demarrer(s, by=self.acteur, commentaire=d["commentaire"]),
        )

    @_schema_transition(
        "Déclarer une action réalisée (preuve et commentaire obligatoires)",
        serializers.CommentaireObligatoireRequestSerializer,
    )
    @action(detail=True, methods=["post"], url_path="declare-done", pagination_class=None)
    def declare_done(self, request: Request, pk: str | None = None) -> Response:
        return self._operer(
            request,
            "DECLARER_REALISEE",
            serializers.CommentaireObligatoireRequestSerializer,
            lambda s, d: workflow.declarer_realisee(
                s, commentaire=d["commentaire"], by=self.acteur
            ),
        )

    @_schema_transition(
        "Proposer l'abandon d'une action", serializers.JustificationRequestSerializer
    )
    @action(detail=True, methods=["post"], url_path="propose-abandon", pagination_class=None)
    def propose_abandon(self, request: Request, pk: str | None = None) -> Response:
        return self._operer(
            request,
            "PROPOSER_ABANDON",
            serializers.JustificationRequestSerializer,
            lambda s, d: workflow.proposer_abandon(
                s, justification=d["justification"], by=self.acteur
            ),
        )

    @_schema_transition("Vérifier une action réalisée", serializers.CommentaireRequestSerializer)
    @action(detail=True, methods=["post"], url_path="verify", pagination_class=None)
    def verify(self, request: Request, pk: str | None = None) -> Response:
        return self._operer(
            request,
            "VERIFIER",
            serializers.CommentaireRequestSerializer,
            lambda s, d: workflow.verifier(s, by=self.acteur, commentaire=d["commentaire"]),
        )

    @_schema_transition(
        "Rejeter une action (motif obligatoire)", serializers.MotifSuiviRequestSerializer
    )
    @action(detail=True, methods=["post"], url_path="reject", pagination_class=None)
    def reject(self, request: Request, pk: str | None = None) -> Response:
        return self._operer(
            request,
            "REJETER",
            serializers.MotifSuiviRequestSerializer,
            lambda s, d: workflow.rejeter(s, motif=d["motif"], by=self.acteur),
        )

    @_schema_transition(
        "Clôturer une action vérifiée (RAI)", serializers.CommentaireRequestSerializer
    )
    @action(detail=True, methods=["post"], url_path="close", pagination_class=None)
    def close(self, request: Request, pk: str | None = None) -> Response:
        return self._operer(
            request,
            "CLOTURER",
            serializers.CommentaireRequestSerializer,
            lambda s, d: workflow.cloturer(s, by=self.acteur, commentaire=d["commentaire"]),
        )

    @_schema_transition(
        "Accepter l'abandon d'une action (RAI)",
        serializers.CommentaireObligatoireRequestSerializer,
    )
    @action(detail=True, methods=["post"], url_path="accept-abandon", pagination_class=None)
    def accept_abandon(self, request: Request, pk: str | None = None) -> Response:
        return self._operer(
            request,
            "ACCEPTER_ABANDON",
            serializers.CommentaireObligatoireRequestSerializer,
            lambda s, d: workflow.accepter_abandon(s, commentaire=d["commentaire"], by=self.acteur),
        )

    @_schema_transition("Rouvrir une action close (RAI)", serializers.MotifSuiviRequestSerializer)
    @action(detail=True, methods=["post"], url_path="reopen", pagination_class=None)
    def reopen(self, request: Request, pk: str | None = None) -> Response:
        return self._operer(
            request,
            "ROUVRIR",
            serializers.MotifSuiviRequestSerializer,
            lambda s, d: workflow.rouvrir(s, motif=d["motif"], by=self.acteur),
        )

    @_schema_transition("Commenter une action", serializers.TexteRequestSerializer)
    @action(detail=True, methods=["post"], url_path="comment", pagination_class=None)
    def comment(self, request: Request, pk: str | None = None) -> Response:
        return self._operer(
            request,
            "COMMENTER",
            serializers.TexteRequestSerializer,
            lambda s, d: workflow.commenter(s, texte=d["texte"], by=self.acteur),
        )

    @extend_schema(
        tags=[TAG_ACTIONS],
        summary="Journal d'une action",
        responses={
            200: serializers.EvenementActionSuiviSerializer(many=True),
            **ERROR_RESPONSES,
            **ERROR_404,
        },
    )
    @action(detail=True, methods=["get"], pagination_class=None, filter_backends=[])
    def events(self, request: Request, pk: str | None = None) -> Response:
        suivi = self.get_object()
        evenements = EvenementSuivi.objects.filter(suivi=suivi).select_related(
            "par", "pour_compte_de"
        )
        return Response(serializers.EvenementActionSuiviSerializer(evenements, many=True).data)

    @extend_schema(
        tags=[TAG_ACTIONS],
        summary="Exporter les actions du registre (CSV ou XLSX, 5 000 lignes au plus)",
        parameters=[_FORMAT_EXPORT],
        responses=_REPONSES_EXPORT,
    )
    @action(
        detail=False,
        methods=["get"],
        pagination_class=None,
        renderer_classes=[JSONRenderer],
        content_negotiation_class=NegociationTelechargement,
    )
    def export(self, request: Request) -> HttpResponse:
        fmt = _format_export(request)
        contenu = exports.exporter_actions(self.filter_queryset(self.get_queryset()), fmt)
        return _reponse_export(contenu, "suivi-actions", fmt)


# --------------------------------------------------------------------------- registre


@extend_schema_view(
    list=extend_schema(
        tags=[TAG_REGISTRE],
        summary="Lister : recommandations suivies",
        responses={
            200: serializers.RecommandationSuiviSerializer(many=True),
            **ERROR_400,
            **ERROR_RESPONSES,
        },
    ),
    retrieve=extend_schema(
        tags=[TAG_REGISTRE],
        summary="Détail : recommandation suivie",
        responses={
            200: serializers.RecommandationSuiviSerializer,
            **ERROR_RESPONSES,
            **ERROR_404,
        },
    ),
)
class RecommandationSuiviViewSet(
    SuiviBaseViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin
):
    serializer_class = serializers.RecommandationSuiviSerializer
    queryset = Recommandation.objects.none()
    avec_contexte = False
    filterset_class = filters.RecommandationSuiviFilter
    ordering_fields = ("prochaine_echeance", ("priorite", "priorite_rang"))
    ordering = ("prochaine_echeance",)
    throttle_scopes: ClassVar[dict[str, str]] = {"export": "export"}

    def get_queryset(self) -> QuerySet[Recommandation]:
        base = Recommandation.objects.filter(mission__in=missions_suivi_visibles(self.acteur))
        return registre.annoter_registre(base, timezone.localdate())

    @extend_schema(
        tags=[TAG_REGISTRE],
        summary="Exporter le registre des recommandations (CSV ou XLSX, 5 000 lignes au plus)",
        parameters=[_FORMAT_EXPORT],
        responses=_REPONSES_EXPORT,
    )
    @action(
        detail=False,
        methods=["get"],
        pagination_class=None,
        renderer_classes=[JSONRenderer],
        content_negotiation_class=NegociationTelechargement,
    )
    def export(self, request: Request) -> HttpResponse:
        fmt = _format_export(request)
        contenu = exports.exporter_recommandations(self.filter_queryset(self.get_queryset()), fmt)
        return _reponse_export(contenu, "suivi-recommandations", fmt)


# --------------------------------------------------------------------------- preuves


def _poser_en_tetes(reponse: HttpResponseBase, taille: int) -> None:
    """Rien ne s'exécute, rien n'est mis en cache."""
    reponse["Cache-Control"] = "private, no-store"
    reponse["X-Content-Type-Options"] = "nosniff"
    reponse["Content-Security-Policy"] = "default-src 'none'; sandbox"
    reponse["Content-Length"] = str(taille)


@extend_schema_view(
    list=extend_schema(
        tags=[TAG_PREUVES],
        summary="Lister : preuves d'une action (paramètre `action` obligatoire)",
        parameters=[
            OpenApiParameter(
                "action", OpenApiTypes.UUID, required=True, description="Action suivie."
            )
        ],
        responses={
            200: serializers.PreuveSerializer(many=True),
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
        },
    ),
    retrieve=extend_schema(
        tags=[TAG_PREUVES],
        summary="Détail : preuve de mise en œuvre",
        responses={200: serializers.PreuveSerializer, **ERROR_RESPONSES, **ERROR_404},
    ),
    create=extend_schema(
        tags=[TAG_PREUVES],
        summary="Déposer : une preuve de mise en œuvre (multipart)",
        request={"multipart/form-data": serializers.DepotPreuveSerializer},
        parameters=[
            OpenApiParameter(
                "action",
                OpenApiTypes.UUID,
                required=False,
                description="Action cible : droits contrôlés avant le corps (recommandé).",
            )
        ],
        responses={
            201: serializers.PreuveSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
            **ERROR_429,
        },
    ),
    partial_update=extend_schema(
        tags=[TAG_PREUVES],
        summary="Modifier : libellé et description d'une preuve (le fichier est immuable)",
        request=serializers.ModifierPreuveSerializer,
        responses={
            200: serializers.PreuveSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
    ),
    destroy=extend_schema(
        tags=[TAG_PREUVES],
        summary="Retirer (logiquement) : une preuve ; `commentaire` obligatoire pour le RAI",
        request=serializers.CommentaireRequestSerializer,
        responses={204: None, **ERROR_RESPONSES, **ERROR_404, **ERROR_422},
    ),
)
class PreuveViewSet(SuiviBaseViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    serializer_class = serializers.PreuveSerializer
    queryset = PreuveMiseEnOeuvre.objects.none()
    filterset_class = filters.PreuveFilter
    ordering_fields = ("numero",)
    ordering = ("numero",)
    throttle_scopes: ClassVar[dict[str, str]] = {"create": "televersement"}

    def get_queryset(self) -> QuerySet[PreuveMiseEnOeuvre]:
        return PreuveMiseEnOeuvre.objects.filter(
            mission__in=missions_suivi_visibles(self.acteur)
        ).select_related("deposee_par", "suivi", "mission")

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        brut = request.query_params.get("action")
        if not brut:
            raise ValidationError({"action": [MSG_PARAMETRE]})
        identifiant = _uuid(brut)
        if identifiant is None:
            raise ValidationError({"action": ["Identifiant invalide."]})
        self.suivi_visible(identifiant)
        return super().list(request, *args, **kwargs)

    def _suivi_operable(self, identifiant: UUID) -> SuiviAction:
        """Action visible (404) dont l'acteur peut saisir pour le responsable (403)."""
        suivi = self.suivi_visible(identifiant)
        droits.exiger_operer_pour_responsable(self.acteur, suivi)
        return suivi

    def _refuser_trop_gros(self, request: Request) -> None:
        """Taille annoncée refusée AVANT toute lecture du corps."""
        declare = request.META.get("CONTENT_LENGTH") or "0"
        if declare.isdigit() and int(declare) > taille_maximale() + _MARGE_MULTIPART:
            raise RegleMetierError(MSG_TAILLE, {"fichier": [MSG_TAILLE]})

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self._refuser_trop_gros(request)
        # `?action=` : droits contrôlés AVANT toute lecture du corps (aucun multipart analysé
        # pour un non-autorisé). Le champ `action` du corps reste accepté (analysé d'abord).
        brut = request.query_params.get("action")
        suivi_url: SuiviAction | None = None
        if brut:
            identifiant = _uuid(brut)
            if identifiant is None:
                raise ValidationError({"action": ["Identifiant invalide."]})
            suivi_url = self._suivi_operable(identifiant)
        else:
            du_corps = _uuid_du_corps(request, "action")
            if du_corps is not None:
                self._suivi_operable(du_corps)
        corps = serializers.DepotPreuveSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        donnees = corps.validated_data
        suivi = donnees.get("action") or suivi_url
        if suivi is None:
            raise ValidationError({"action": ["Ce champ est obligatoire."]})
        if suivi_url is not None and suivi.pk != suivi_url.pk:
            raise ValidationError({"action": ["L'action du corps diffère de celle de l'URL."]})
        fichier = donnees["fichier"]
        if fichier.size is not None and fichier.size > taille_maximale():  # sans rien lire
            raise RegleMetierError(MSG_TAILLE, {"fichier": [MSG_TAILLE]})
        preuve = preuves.deposer_preuve(
            suivi,
            fichier=fichier,
            libelle=donnees["libelle"],
            description=donnees["description"],
            commentaire=donnees["commentaire"],
            by=self.acteur,
        )
        return Response(self.lire(preuve.pk), status=status.HTTP_201_CREATED)

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        preuve = self.get_object()
        droits.exiger_operer_pour_responsable(self.acteur, preuve.suivi)
        corps = serializers.ModifierPreuveSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        preuves.modifier_preuve(preuve, by=self.acteur, **corps.validated_data)
        return Response(self.lire(preuve.pk))

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        preuve = self.get_object()
        droits.exiger_operer_pour_responsable(self.acteur, preuve.suivi)
        corps = serializers.CommentaireRequestSerializer(
            data=request.data if isinstance(request.data, dict) else {}
        )
        corps.is_valid(raise_exception=True)
        preuves.retirer_preuve(
            preuve, by=self.acteur, commentaire=corps.validated_data["commentaire"]
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=[TAG_PREUVES],
        summary="Télécharger : fichier d'une preuve (empreinte vérifiée, journalisé ; DG refusé)",
        responses={
            (200, "application/octet-stream"): OpenApiTypes.BINARY,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_409,
        },
    )
    @action(
        detail=True,
        methods=["get"],
        pagination_class=None,
        filter_backends=[],
        content_negotiation_class=NegociationTelechargement,
    )
    def download(self, request: Request, pk: str | None = None) -> HttpResponseBase:
        preuve: PreuveMiseEnOeuvre = self.get_object()
        nom = nom_telechargement(preuve.nom_fichier_original)
        if request.method == "HEAD":  # en-têtes seuls : droit contrôlé, rien n'est lu ni journalisé
            droits.exiger_telechargement_preuve(self.acteur, preuve)
            reponse = HttpResponse(content_type="application/octet-stream")
            reponse["Content-Disposition"] = content_disposition_header(True, nom)
            _poser_en_tetes(reponse, preuve.taille_octets)
            return reponse
        contenu = preuves.ouvrir_preuve_verifiee(preuve, by=self.acteur, adresse_ip=self.adresse_ip)
        envoi = HttpResponse(contenu, content_type="application/octet-stream")
        envoi["Content-Disposition"] = content_disposition_header(True, nom)
        _poser_en_tetes(envoi, len(contenu))
        return envoi


# --------------------------------------------------------------------------- reports


@extend_schema_view(
    list=extend_schema(
        tags=[TAG_REPORTS],
        summary="Lister : demandes de report d'échéance",
        responses={
            200: serializers.DemandeReportSerializer(many=True),
            **ERROR_400,
            **ERROR_RESPONSES,
        },
    ),
    retrieve=extend_schema(
        tags=[TAG_REPORTS],
        summary="Détail : demande de report d'échéance",
        responses={200: serializers.DemandeReportSerializer, **ERROR_RESPONSES, **ERROR_404},
    ),
    create=extend_schema(
        tags=[TAG_REPORTS],
        summary="Demander : un report d'échéance",
        request=serializers.DemandeReportRequestSerializer,
        responses={
            201: serializers.DemandeReportSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
    ),
)
class DemandeReportViewSet(
    SuiviBaseViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
):
    serializer_class = serializers.DemandeReportSerializer
    queryset = DemandeReport.objects.none()
    filterset_class = filters.DemandeReportFilter
    ordering_fields = ("created_at", "nouvelle_echeance")
    ordering = ("-created_at",)

    def get_queryset(self) -> QuerySet[DemandeReport]:
        return DemandeReport.objects.filter(
            mission__in=missions_suivi_visibles(self.acteur)
        ).select_related("suivi", "demandee_par", "decidee_par", "mission")

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        identifiant = _uuid_du_corps(request, "action")
        if identifiant is not None:
            suivi = self.suivi_visible(identifiant)
            droits.exiger_operer_pour_responsable(self.acteur, suivi)
        corps = serializers.DemandeReportRequestSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        demande = reports.demander_report(
            corps.validated_data["action"],
            nouvelle_echeance=corps.validated_data["nouvelle_echeance"],
            motif=corps.validated_data["motif"],
            by=self.acteur,
        )
        return Response(self.lire(demande.pk), status=status.HTTP_201_CREATED)

    def _decider(self, request: Request, requete: Any, appeler: Any) -> Response:
        demande = self.get_object()
        droits.exiger_decideur_report(self.acteur)
        corps = requete(data=request.data)
        corps.is_valid(raise_exception=True)
        appeler(demande, corps.validated_data["commentaire"])
        return Response(self.lire(demande.pk))

    @extend_schema(
        tags=[TAG_REPORTS],
        summary="Accepter un report d'échéance (RAI)",
        request=serializers.DecisionReportSerializer,
        responses={
            200: serializers.DemandeReportSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
    )
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def accept(self, request: Request, pk: str | None = None) -> Response:
        return self._decider(
            request,
            serializers.DecisionReportSerializer,
            lambda d, c: reports.accepter_report(d, by=self.acteur, commentaire=c),
        )

    @extend_schema(
        tags=[TAG_REPORTS],
        summary="Refuser un report d'échéance (RAI, commentaire obligatoire)",
        request=serializers.CommentaireObligatoireRequestSerializer,
        responses={
            200: serializers.DemandeReportSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
    )
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def refuse(self, request: Request, pk: str | None = None) -> Response:
        return self._decider(
            request,
            serializers.CommentaireObligatoireRequestSerializer,
            lambda d, c: reports.refuser_report(d, by=self.acteur, commentaire=c),
        )


# --------------------------------------------------------------------------- missions


@extend_schema_view(
    list=extend_schema(
        tags=[TAG_MISSIONS],
        summary="Lister : missions à clôturer (toutes les actions sont closes ; RAI)",
        responses={
            200: serializers.MissionACloturerSerializer(many=True),
            **ERROR_400,
            **ERROR_RESPONSES,
        },
    ),
)
class MissionSuiviViewSet(SuiviBaseViewSet, mixins.ListModelMixin):
    serializer_class = serializers.MissionACloturerSerializer
    queryset = Mission.objects.none()
    avec_contexte = False
    ordering_fields = ("reference", "annee")
    ordering = ("reference",)
    roles_suivi = (Role.RAI,)

    def get_queryset(self) -> QuerySet[Mission]:
        if self.action == "list":
            base = cloture.missions_a_cloturer()
            return base.annotate(
                actions_total=Count(
                    "suivis_actions", filter=Q(suivis_actions__deleted_at__isnull=True)
                ),
                actions_closes=Count(
                    "suivis_actions",
                    filter=Q(suivis_actions__deleted_at__isnull=True)
                    & Q(suivis_actions__statut__in=tuple(STATUTS_CLOS)),
                ),
            )
        return missions_suivi_visibles(self.acteur)

    @extend_schema(
        tags=[TAG_MISSIONS],
        summary="Clôturer une mission suivie (RAI) : toutes les actions du plan sont closes",
        request=serializers.CommentaireRequestSerializer,
        responses={
            200: serializers.MissionSuiviSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
    )
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def close(self, request: Request, pk: str | None = None) -> Response:
        mission = self.get_object()
        corps = serializers.CommentaireRequestSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        cloturee = cloture.cloturer_mission(
            mission, by=self.acteur, commentaire=corps.validated_data["commentaire"]
        )
        return Response(serializers.MissionSuiviSerializer(cloturee).data)
