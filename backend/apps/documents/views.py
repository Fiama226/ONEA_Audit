"""ViewSets des documents : aucune logique métier, tout passe par `services`.

Ordre des refus : rôle global (403) -> objet ou mission invisible (404) -> droit du fournisseur
(403) -> sérialiseur (400) -> règle métier (422). Une altération de fichier (`IntegriteError`,
sous-classe de `RegleMetierError`) répond 409 : la correspondance est explicite, portée par
`IntegriteError.status_http` et appliquée par `apps.core.handlers`.

Les fichiers ne sortent que par `file` (gabarit), `preview` (aperçu) et `download` (version) :
authentifiés, journalisés, en pièce jointe, jamais en statique.
"""

import io
from collections.abc import Callable
from typing import Any, ClassVar, TypeVar, cast

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch, QuerySet
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.viewsets import GenericViewSet

from apps.core.exceptions import RegleMetierError
from apps.core.filters import StableOrderingFilter
from apps.core.handlers import FORBIDDEN
from apps.core.reseau import adresse_client
from apps.core.schema import (
    ERROR_400,
    ERROR_404,
    ERROR_409,
    ERROR_422,
    ERROR_429,
    ERROR_RESPONSES,
)
from apps.core.throttling import ThrottleParActionMixin
from apps.missions.acces import missions_visibles
from apps.missions.etapes import romain
from apps.missions.gardes import STATUTS_FIGES
from apps.missions.models import Mission
from apps.missions.permissions import mission_visible
from apps.users.models import User

from . import filters, serializers
from .models import (
    ConsultationDocument,
    Document,
    DocumentVersion,
    FormatNumerotation,
    GabaritDocument,
    StatutGabarit,
    StatutGeneration,
)
from .moteur.contrats import CHAMPS_COMMUNS
from .moteur.registre import TypeDocument, types_documents
from .moteur.registre import type_document as type_enregistre
from .numerotation import apercu_numero, erreurs_format, modifier_format
from .permissions import (
    DocumentAccessPermission,
    EcrivainAdmin,
    LecteurAdminRai,
    LecteurRai,
    exiger_consultation,
    fournisseur_de,
    peut_generer,
)
from .services import gabarits as svc_gabarits
from .services import generation as svc_generation

TAG_GABARITS = "Documents : gabarits"
TAG_DOCUMENTS = "Documents"
F = TypeVar("F", bound=Callable[..., Any])
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF = "application/pdf"
TYPES_FICHIERS = {"docx": DOCX, "pdf": PDF}
_MARGE_MULTIPART = 64 * 1024  # envelope of a multipart body around the file itself
_Lignes = list[dict[str, Any]]
_INTERDITS = str.maketrans({c: "" for c in '"\\/\r\n\t\x00'})


def nom_telechargement(nom: str) -> str:
    """File name safe for `Content-Disposition`: no quote, separator or control character."""
    propre = "".join(c for c in nom.translate(_INTERDITS) if c.isprintable()).strip()
    return propre or "document"


def reponse_fichier(contenu: bytes, nom: str, type_contenu: str) -> FileResponse:
    """Authenticated attachment, never cached nor sniffed (name built by Django, RFC 6266)."""
    reponse = FileResponse(
        io.BytesIO(contenu),
        as_attachment=True,
        filename=nom_telechargement(nom),
        content_type=type_contenu,
    )
    reponse["Cache-Control"] = "private, no-store"
    reponse["X-Content-Type-Options"] = "nosniff"
    return reponse


class _ReglagesSansFormat:
    """DRF settings without `URL_FORMAT_OVERRIDE`: `?format=docx|pdf` is a file format here."""

    URL_FORMAT_OVERRIDE = None

    def __getattr__(self, nom: str) -> Any:
        return getattr(api_settings, nom)


class NegociationSansFormat(DefaultContentNegotiation):
    settings = _ReglagesSansFormat()  # type: ignore[assignment]


def _schema(
    summary: str,
    response: Any,
    *,
    tag: str = TAG_DOCUMENTS,
    request: Any = None,
    parametres: list[Any] | None = None,
    extra: dict[int, Any] | None = None,
    description: str = "",
    succes: int = 200,
    types_binaires: tuple[str, ...] = (),
) -> Callable[[F], F]:
    """Schema of an action; `types_binaires` declares a file response with its real media types."""
    erreurs: dict[int, Any] = {**ERROR_RESPONSES, **ERROR_404, **ERROR_422}
    if request is not None or parametres:
        erreurs.update(ERROR_400)
    erreurs.update(extra or {})
    reponses: dict[Any, Any] = dict(erreurs)
    if types_binaires:
        reponses.update({(succes, type_): OpenApiTypes.BINARY for type_ in types_binaires})
    else:
        reponses[succes] = response
    return extend_schema(
        tags=[tag],
        summary=summary,
        description=description,
        request=request,
        parameters=parametres,
        responses=reponses,
    )


class DocumentsApiViewSet(ThrottleParActionMixin, GenericViewSet[Any]):
    http_method_names = ["get", "post", "patch", "head", "options"]  # no PUT, no DELETE
    content_negotiation_class = NegociationSansFormat
    # Permission classes per action; the default applies to the others.
    permissions_par_action: ClassVar[dict[str, type[BasePermission]]] = {}
    permission_defaut: ClassVar[type[BasePermission]] = LecteurAdminRai

    def get_permissions(self) -> list[BasePermission]:
        classe = self.permissions_par_action.get(getattr(self, "action", "") or "")
        return [(classe or self.permission_defaut)()]

    @property
    def acteur(self) -> User:
        return cast(User, self.request.user)

    @property
    def adresse_ip(self) -> str | None:
        return adresse_client(self.request)


# --------------------------------------------------------------------- types de documents


class TypeDocumentViewSet(DocumentsApiViewSet):
    """Registre des types : contrat de balises, gabarit actif et format de numérotation."""

    serializer_class = serializers.TypeDocumentSerializer
    pagination_class = None
    filter_backends = ()

    @_schema("Lister : types de documents", serializers.TypeDocumentSerializer(many=True))
    def list(self, request: Request) -> Response:
        types = types_documents()
        codes = [t.code for t in types]
        actifs = {
            g.type_document: g
            for g in GabaritDocument.objects.filter(
                type_document__in=codes, statut=StatutGabarit.ACTIF
            )
        }
        formats = {
            f.type_document: f for f in FormatNumerotation.objects.filter(type_document__in=codes)
        }
        lignes = [
            {
                "code": t.code,
                "libelle": t.libelle,
                "etape": t.etape,
                "etape_romain": romain(t.etape) if t.etape else None,
                "contrat_version": t.contrat.version,
                "champs": [*CHAMPS_COMMUNS, *t.contrat.champs],
                "gabarit_actif": actifs.get(t.code),
                "format_numerotation": formats.get(t.code) or format_par_defaut(t),
            }
            for t in types
        ]
        return Response(cast(Any, serializers.TypeDocumentSerializer)(lignes, many=True).data)


def format_par_defaut(t: TypeDocument) -> FormatNumerotation:
    """Registry default of a type not customised yet (never saved: a read does not write)."""
    return FormatNumerotation(
        type_document=t.code,
        modele=t.modele_numero,
        portee=t.portee_numero,
        abreviation=t.abreviation,
    )


# ------------------------------------------------------------------------------ gabarits


class GabaritViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, DocumentsApiViewSet):
    serializer_class = serializers.GabaritDocumentSerializer
    filter_backends = [DjangoFilterBackend, StableOrderingFilter]
    filterset_class = filters.GabaritFilter
    ordering_fields = ["type_document", "version", "created_at"]
    lookup_value_regex = "[0-9a-fA-F-]{36}"
    permissions_par_action: ClassVar[dict[str, type[BasePermission]]] = {
        "create": EcrivainAdmin,
        "activate": EcrivainAdmin,
    }
    throttle_scopes: ClassVar[dict[str, str]] = {"create": "televersement", "preview": "apercu"}

    def get_queryset(self) -> QuerySet[GabaritDocument]:
        return GabaritDocument.objects.select_related("created_by", "active_par").order_by(
            "type_document", "-version"
        )

    @_schema("Lister : gabarits", serializers.GabaritDocumentSerializer(many=True))
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)

    @_schema("Détail : gabarit", serializers.GabaritDocumentSerializer)
    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=[TAG_GABARITS],
        summary="Déposer : une version de gabarit (multipart)",
        request={"multipart/form-data": serializers.GabaritDepotSerializer},
        responses={
            201: serializers.GabaritDocumentSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_422,
            **ERROR_429,
        },
    )
    def create(self, request: Request) -> Response:
        limite = settings.DOCUMENTS_MAX_GABARIT_MO * 1024 * 1024
        # refused from the declared length, before the body is parsed
        declare = request.META.get("CONTENT_LENGTH") or "0"
        if declare.isdigit() and int(declare) > limite + _MARGE_MULTIPART:
            raise taille_depassee()
        corps = serializers.GabaritDepotSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        fichier = corps.validated_data["fichier"]
        if fichier.size > limite:  # size of the upload, known without reading it
            raise taille_depassee()
        gabarit = svc_gabarits.deposer_gabarit(
            type_document=corps.validated_data["type_document"],
            contenu=fichier.read(limite + 1),
            nom_original=fichier.name or "",
            by=self.acteur,
            commentaire=corps.validated_data["commentaire"],
        )
        donnees = self.get_serializer(self.get_queryset().get(pk=gabarit.pk)).data
        return Response(donnees, status=status.HTTP_201_CREATED)

    @_schema(
        "Activer : un gabarit (archive l'actif précédent)", serializers.GabaritDocumentSerializer
    )
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def activate(self, request: Request, pk: str | None = None) -> Response:
        gabarit = self.get_object()
        svc_gabarits.activer_gabarit(gabarit, by=self.acteur)
        return Response(self.get_serializer(self.get_queryset().get(pk=gabarit.pk)).data)

    @_schema(
        "Télécharger : fichier d'un gabarit (journalisé)",
        OpenApiTypes.BINARY,
        extra=ERROR_409,
        types_binaires=(DOCX,),
    )
    @action(detail=True, methods=["get"], pagination_class=None, filter_backends=[])
    def file(self, request: Request, pk: str | None = None) -> FileResponse:
        gabarit = self.get_object()
        contenu, nom = svc_gabarits.fichier_gabarit(
            gabarit,
            by=self.acteur,
            adresse_ip=self.adresse_ip,
            journaliser=request.method != "HEAD",
        )
        return reponse_fichier(contenu, nom, DOCX)

    @_schema(
        "Aperçu : gabarit rempli avec les données d'exemple du contrat",
        OpenApiTypes.BINARY,
        parametres=[serializers.FormatQuerySerializer],
        extra={**ERROR_409, **ERROR_429},
        types_binaires=(DOCX, PDF),
    )
    @action(detail=True, methods=["get"], pagination_class=None, filter_backends=[])
    def preview(self, request: Request, pk: str | None = None) -> FileResponse:
        gabarit = self.get_object()
        requete = serializers.FormatQuerySerializer(data=request.query_params)
        requete.is_valid(raise_exception=True)
        format_ = requete.validated_data["format"]
        contenu, nom = svc_gabarits.apercu_gabarit(gabarit, format=format_)
        return reponse_fichier(contenu, nom, TYPES_FICHIERS[format_])


def taille_depassee() -> RegleMetierError:
    mo = settings.DOCUMENTS_MAX_GABARIT_MO
    return RegleMetierError(
        "Le gabarit est invalide.", {"fichier": [f"Le fichier dépasse {mo} Mo."]}
    )


# ------------------------------------------------------------------------- numérotation


class FormatNumerotationViewSet(DocumentsApiViewSet):
    serializer_class = serializers.FormatNumerotationSerializer
    pagination_class = None
    filter_backends = ()
    lookup_field = "type_document"
    lookup_value_regex = "[A-Za-z0-9_]+"
    permissions_par_action: ClassVar[dict[str, type[BasePermission]]] = {
        "partial_update": EcrivainAdmin,
        "preview": EcrivainAdmin,
    }
    throttle_scopes: ClassVar[dict[str, str]] = {"preview": "apercu"}

    def _format(self, code: str) -> FormatNumerotation:
        try:
            t = type_enregistre(code)
        except RegleMetierError as exc:
            raise Http404 from exc
        existant = FormatNumerotation.objects.filter(type_document=code).first()
        return existant or format_par_defaut(t)

    @_schema(
        "Lister : formats de numérotation", serializers.FormatNumerotationSerializer(many=True)
    )
    def list(self, request: Request) -> Response:
        enregistres = {f.type_document: f for f in FormatNumerotation.objects.all()}
        formats = [enregistres.get(t.code) or format_par_defaut(t) for t in types_documents()]
        return Response(serializers.FormatNumerotationSerializer(formats, many=True).data)

    @_schema("Détail : format de numérotation", serializers.FormatNumerotationSerializer)
    def retrieve(self, request: Request, type_document: str) -> Response:
        return Response(serializers.FormatNumerotationSerializer(self._format(type_document)).data)

    @_schema(
        "Modifier : format de numérotation (s'applique aux numéros suivants)",
        serializers.FormatNumerotationSerializer,
        request=serializers.FormatNumerotationEcritureSerializer,
    )
    def partial_update(self, request: Request, type_document: str) -> Response:
        self._format(type_document)  # 404 on an unknown type
        corps = serializers.FormatNumerotationEcritureSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        fmt = modifier_format(type_document, by=self.acteur, **corps.validated_data)
        return Response(serializers.FormatNumerotationSerializer(fmt).data)

    @_schema(
        "Prévisualiser : un format de numérotation",
        serializers.ApercuNumeroSerializer,
        request=serializers.ApercuFormatSerializer,
        description="Le numéro d'exemple est `null` quand le format a des erreurs.",
        extra=ERROR_429,
    )
    @action(detail=False, methods=["post"])
    def preview(self, request: Request) -> Response:
        corps = serializers.ApercuFormatSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        d = corps.validated_data
        erreurs = erreurs_format(d["modele"], d["portee"], d["abreviation"])
        numero = None
        if not erreurs:
            numero = apercu_numero(d["modele"], d["portee"], d["abreviation"])
        return Response({"numero": numero, "errors": erreurs})


# --------------------------------------------------------------------------- documents


def _versions_legeres() -> "Prefetch[Any]":
    return Prefetch("versions", queryset=DocumentVersion.objects.order_by("-numero_version"))


def _versions_completes() -> "Prefetch[Any]":
    return Prefetch(
        "versions",
        queryset=DocumentVersion.objects.select_related(
            "gabarit", "demandee_par", "confirmation__signataire"
        ).order_by("-numero_version"),
    )


class DocumentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, DocumentsApiViewSet):
    serializer_class = serializers.DocumentSerializer
    filter_backends = [DjangoFilterBackend, StableOrderingFilter]
    filterset_class = filters.DocumentFilter
    ordering_fields = ["numero", "created_at"]
    lookup_value_regex = "[0-9a-fA-F-]{36}"
    permission_defaut = DocumentAccessPermission
    throttle_scopes: ClassVar[dict[str, str]] = {"generate": "generation"}

    def get_serializer_class(self) -> Any:
        if self.action == "list":
            return serializers.DocumentListeSerializer
        return super().get_serializer_class()

    def get_queryset(self) -> QuerySet[Document]:
        if getattr(self, "swagger_fake_view", False):
            return Document.objects.none()
        prefetch = _versions_legeres() if self.action == "list" else _versions_completes()
        return (
            Document.objects.filter(mission__in=missions_visibles(self.acteur))
            .select_related("mission")
            .prefetch_related(prefetch)
            .order_by("-created_at")
        )

    @_schema(
        "Lister : documents des missions visibles", serializers.DocumentListeSerializer(many=True)
    )
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)

    @_schema("Détail : document et ses versions", serializers.DocumentSerializer)
    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        document = self.get_object()
        exiger_consultation(self.acteur, document)
        return Response(self.get_serializer(document).data)

    @_schema(
        "Documents disponibles : générés ou générables d'une mission",
        serializers.DocumentDisponibleSerializer(many=True),
        parametres=[serializers.MissionQuerySerializer],
    )
    @action(detail=False, methods=["get"], pagination_class=None, filter_backends=[])
    def available(self, request: Request) -> Response:
        requete = serializers.MissionQuerySerializer(data=request.query_params)
        requete.is_valid(raise_exception=True)
        mission = mission_visible(self.acteur, requete.validated_data["mission"])
        lignes = self._disponibles(mission)
        return Response(cast(Any, serializers.DocumentDisponibleSerializer)(lignes, many=True).data)

    def _disponibles(self, mission: Mission) -> _Lignes:
        user = self.acteur
        existants = {
            (d.type_document, d.object_id): d
            for d in Document.objects.filter(mission=mission)
            .select_related("mission")
            .prefetch_related(_versions_legeres())
        }
        types = types_documents()
        actifs = set(
            GabaritDocument.objects.filter(
                type_document__in=[t.code for t in types], statut=StatutGabarit.ACTIF
            ).values_list("type_document", flat=True)
        )
        lignes: _Lignes = []
        for t in types:
            f = t.fournisseur
            objets = f.objets_de_mission(mission)
            for objet in objets:  # la mission est connue : pas de requête par objet
                if getattr(objet, "mission_id", None) == mission.pk:
                    cast(Any, objet).mission = mission
            consultables = getattr(f, "ids_consultables", None)
            visibles = consultables(user, mission, objets) if consultables else None
            for objet in objets:
                if visibles is not None:
                    if objet.pk not in visibles:
                        continue
                elif not f.peut_consulter(user, objet):
                    continue
                document = existants.get((t.code, objet.pk))
                droit = f.peut_generer(user, objet)
                raison = _raison(
                    user, droit, f.raison_non_generable(objet), mission, t.code in actifs
                )
                lignes.append(
                    {
                        "type_document": t.code,
                        "libelle": t.libelle,
                        "etape": t.etape,
                        "objet_id": objet.pk,
                        "document": document,
                        "peut_generer": droit and raison is None,
                        "raison": raison,
                        "en_cours": document is not None
                        and any(
                            v.statut in (StatutGeneration.EN_ATTENTE, StatutGeneration.EN_COURS)
                            for v in document.versions.all()
                        ),
                    }
                )
        return lignes

    @_schema(
        "Générer : une nouvelle version d'un document (traitement en arrière-plan)",
        serializers.DocumentVersionSerializer,
        request=serializers.GenerationSerializer,
        extra=ERROR_429,
        succes=202,
        description="Répond 202 : suivre `statut` et `statut_pdf` sur la version.",
    )
    @action(detail=False, methods=["post"], pagination_class=None, filter_backends=[])
    def generate(self, request: Request) -> Response:
        corps = serializers.GenerationSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        code, objet_id = corps.validated_data["type_document"], corps.validated_data["objet"]
        fournisseur = fournisseur_de(code)
        try:
            objet = fournisseur.objet(objet_id)
        except ObjectDoesNotExist as exc:
            raise Http404 from exc
        # invisible mission: 404 (existence not revealed); visible but not allowed: 403
        get_object_or_404(missions_visibles(self.acteur), pk=fournisseur.mission_de(objet).pk)
        if not fournisseur.peut_generer(self.acteur, objet):
            raise PermissionDenied(FORBIDDEN)
        version = svc_generation.demander_generation(
            type_document=code, objet_id=objet_id, by=self.acteur
        )
        donnees = serializers.DocumentVersionSerializer(
            _version_complete(version.pk), context=self.get_serializer_context()
        ).data
        return Response(donnees, status=status.HTTP_202_ACCEPTED)


def _raison(
    user: User, droit: bool, raison_metier: str | None, mission: Mission, gabarit: bool
) -> str | None:
    """Why the document cannot be generated now (None when it can)."""
    if not droit:
        return "Vous n'avez pas le droit de générer ce document."
    if raison_metier:
        return raison_metier
    if mission.statut in STATUTS_FIGES:
        return (
            f"La mission {mission.reference} est {mission.get_statut_display().lower()} : "
            "aucun document ne peut être généré."
        )
    if not gabarit:
        return "Aucun gabarit actif : l'administrateur doit en déposer un."
    return None


def _version_complete(pk: Any) -> DocumentVersion:
    return cast(
        DocumentVersion,
        DocumentVersion.objects.select_related(
            "document", "gabarit", "demandee_par", "confirmation__signataire"
        ).get(pk=pk),
    )


# ---------------------------------------------------------------------------- versions


class VersionViewSet(mixins.RetrieveModelMixin, DocumentsApiViewSet):
    serializer_class = serializers.DocumentVersionSerializer
    filter_backends = ()
    lookup_value_regex = "[0-9a-fA-F-]{36}"
    permission_defaut = DocumentAccessPermission
    permissions_par_action: ClassVar[dict[str, type[BasePermission]]] = {
        "consultations": LecteurRai,
    }

    def get_queryset(self) -> QuerySet[DocumentVersion]:
        if getattr(self, "swagger_fake_view", False):
            return DocumentVersion.objects.none()
        return DocumentVersion.objects.filter(
            document__mission__in=missions_visibles(self.acteur)
        ).select_related("document__mission", "gabarit", "demandee_par", "confirmation__signataire")

    @_schema("Détail : version d'un document", serializers.DocumentVersionSerializer)
    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        version = self.get_object()
        exiger_consultation(self.acteur, version.document)
        return Response(self.get_serializer(version).data)

    @_schema(
        "Télécharger : fichier Word ou PDF d'une version (journalisé)",
        OpenApiTypes.BINARY,
        parametres=[serializers.FormatQuerySerializer],
        extra=ERROR_409,
        types_binaires=(DOCX, PDF),
    )
    @action(detail=True, methods=["get"], pagination_class=None)
    def download(self, request: Request, pk: str | None = None) -> FileResponse:
        version = self.get_object()
        exiger_consultation(self.acteur, version.document)
        requete = serializers.FormatQuerySerializer(data=request.query_params)
        requete.is_valid(raise_exception=True)
        format_ = requete.validated_data["format"]
        contenu, nom = svc_generation.ouvrir_version(
            version,
            format=format_.upper(),
            by=self.acteur,
            adresse_ip=self.adresse_ip,
            journaliser=request.method != "HEAD",
        )
        return reponse_fichier(contenu, nom, TYPES_FICHIERS[format_])

    @_schema("Relancer : la conversion PDF d'une version", serializers.DocumentVersionSerializer)
    @action(detail=True, methods=["post"], url_path="retry-pdf", pagination_class=None)
    def retry_pdf(self, request: Request, pk: str | None = None) -> Response:
        version = self.get_object()
        exiger_consultation(self.acteur, version.document)
        if not peut_generer(self.acteur, version.document):
            raise PermissionDenied(FORBIDDEN)
        svc_generation.relancer_pdf(version, by=self.acteur)
        return Response(self.get_serializer(self.get_queryset().get(pk=version.pk)).data)

    @_schema(
        "Lister : consultations d'une version (RAI)",
        serializers.ConsultationSerializer(many=True),
    )
    @action(detail=True, methods=["get"])
    def consultations(self, request: Request, pk: str | None = None) -> Response:
        version = self.get_object()
        consultations = ConsultationDocument.objects.filter(version=version).select_related(
            "utilisateur"
        )
        page = self.paginate_queryset(consultations)
        return self.get_paginated_response(serializers.ConsultationSerializer(page, many=True).data)
