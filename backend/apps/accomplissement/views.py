"""ViewSets de l'accomplissement : aucune logique métier, tout passe par `services`.

Ordre des refus : rôle global (403) -> mission ou objet invisible (404) -> droit (403) ->
sérialiseur (400) -> règle métier, gel ou fenêtre d'écriture (422, portés par les services ;
409 pour une pièce altérée). L'audité n'a aucun accès en v1 (403 partout).

Les fichiers ne sortent que par `evidence/{id}/download/` : copie vérifiée par empreinte, en
pièce jointe, avec les en-têtes de D8, et journalisée (sauf HEAD).
"""

from typing import Any
from uuid import UUID

from django.db.models import Count, Prefetch, Q, QuerySet
from django.http import FileResponse, Http404, HttpResponse
from django.http.response import HttpResponseBase
from django.utils.http import content_disposition_header
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer, Serializer
from rest_framework.viewsets import ModelViewSet

from apps.analyse.gardes import ACTIFS, statuts_etapes
from apps.core.consultations import journaliser_consultation
from apps.core.exceptions import RegleMetierError
from apps.core.schema import (
    ERROR_400,
    ERROR_404,
    ERROR_409,
    ERROR_422,
    ERROR_RESPONSES,
    crud_schema,
)
from apps.documents.integrite import IntegriteError
from apps.documents.views import nom_telechargement
from apps.missions import acces
from apps.missions.models import Mission
from apps.missions.permissions import exiger, exiger_contribution, mission_visible
from apps.missions.serializers import MotifSerializer
from apps.missions.services.etapes import contexte_actions
from apps.missions.views import MissionApiViewSet, _action_schema

from . import droits, droits_fiches, filters, serializers
from .fichiers import MSG_TAILLE, taille_maximale, type_contenu
from .models import (
    EvenementFiche,
    FicheDeTest,
    InstantaneProgramme,
    PieceJustificative,
    ProgrammeDeTravail,
    TestPrevu,
)
from .permissions import AccomplissementAccessPermission
from .services import fiches as svc_fiches
from .services import pieces as svc_pieces
from .services import programme as svc_programme
from .services import tests_prevus as svc_tests
from .services.integrite import ouvrir_piece_verifiee
from .services.synthese import synthese_programme
from .stockage import FichierIntrouvableError

TAG_PROGRAMME = "Programme de travail"
TAG_TESTS = "Tests prévus"
TAG_FICHES = "Fiches de test"
TAG_PIECES = "Pièces justificatives"
MSG_PARAMETRE = "Ce paramètre est obligatoire."
_UUID_REGEX = "[0-9a-fA-F-]{36}"
_MARGE_MULTIPART = 64 * 1024  # enveloppe d'un corps multipart autour du fichier lui-même

PARAM_MISSION = OpenApiParameter(
    "mission", OpenApiTypes.UUID, required=True, description="Mission (obligatoire)."
)


def _uuid(brut: Any) -> UUID | None:
    try:
        return UUID(str(brut))
    except ValueError:
        return None


def _uuid_du_corps(request: Request, champ: str) -> UUID | None:
    """Identifiant lisible du champ du corps, sinon `None` (le sérialiseur répondra 400)."""
    brut = request.data.get(champ) if hasattr(request.data, "get") else None
    return _uuid(brut) if brut is not None else None


class AccomplissementViewSet(MissionApiViewSet):
    """Base : liste bornée à une mission visible ; l'audité est refusé par la permission."""

    permission_classes = [AccomplissementAccessPermission]
    lookup_value_regex = _UUID_REGEX

    def mission_requise(self, request: Request) -> Mission:
        brut = request.query_params.get("mission")
        if not brut:
            raise ValidationError({"mission": [MSG_PARAMETRE]})
        identifiant = _uuid(brut)
        if identifiant is None:
            raise ValidationError({"mission": ["Identifiant invalide."]})
        return mission_visible(self.acteur, identifiant)

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self.mission_requise(request)
        return super().list(request, *args, **kwargs)  # type: ignore[misc, no-any-return]

    def visibles(self) -> QuerySet[Mission]:
        return acces.missions_visibles(self.acteur)

    def lire_donnees(self, pk: Any) -> Any:
        return self.get_serializer(self.get_queryset().get(pk=pk)).data


# --------------------------------------------------------------------------- programme


@crud_schema(
    serializers.ProgrammeDeTravailSerializer,
    TAG_PROGRAMME,
    "programmes de travail",
    creation_404=True,
)
class ProgrammeViewSet(AccomplissementViewSet, ModelViewSet[ProgrammeDeTravail]):
    serializer_class = serializers.ProgrammeDeTravailSerializer
    queryset = ProgrammeDeTravail.objects.none()
    filterset_class = filters.ProgrammeFilter
    ordering_fields = ("created_at",)
    ordering = ("created_at",)
    actions_contribution = frozenset({"partial_update", "destroy"})

    def get_queryset(self) -> QuerySet[ProgrammeDeTravail]:
        queryset: QuerySet[ProgrammeDeTravail] = (
            ProgrammeDeTravail.objects.filter(mission__in=self.visibles())
            .select_related("objectif", "mission")
            .annotate(nb_tests=Count("tests", filter=Q(tests__deleted_at__isnull=True)))
        )
        return queryset

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self.creer_pour_mission(request)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer: BaseSerializer[ProgrammeDeTravail]) -> None:
        donnees = dict(serializer.validated_data)
        programme = svc_programme.creer_programme(
            donnees.pop("mission"), objectif=donnees.pop("objectif"), by=self.acteur, **donnees
        )
        self._publier(serializer, programme)

    def perform_update(self, serializer: BaseSerializer[ProgrammeDeTravail]) -> None:
        instance = self._cible(serializer)
        changements = self.retirer_immuables(
            serializer.validated_data, instance, ("mission", "objectif")
        )
        programme = svc_programme.modifier_programme(instance, by=self.acteur, **changements)
        self._publier(serializer, programme)

    def perform_destroy(self, instance: ProgrammeDeTravail) -> None:
        svc_programme.supprimer_programme(instance, by=self.acteur)

    @extend_schema(
        tags=[TAG_PROGRAMME],
        summary="Synthèse du programme (charges par objectif et par auditeur)",
        parameters=[PARAM_MISSION],
        responses={
            200: serializers.SyntheseProgrammeTravailSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
        },
    )
    @action(detail=False, methods=["get"], pagination_class=None, filter_backends=[])
    def summary(self, request: Request) -> Response:
        mission = self.mission_requise(request)
        return Response(
            serializers.SyntheseProgrammeTravailSerializer(synthese_programme(mission)).data
        )


@extend_schema_view(
    list=extend_schema(
        tags=[TAG_PROGRAMME],
        summary="Lister : instantanés du programme validé (sans les données)",
        parameters=[PARAM_MISSION],
        responses={
            200: serializers.InstantaneResumeSerializer(many=True),
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
        },
    ),
    retrieve=extend_schema(
        tags=[TAG_PROGRAMME],
        summary="Détail : instantané du programme validé (avec les données)",
        responses={200: serializers.InstantaneSerializer, **ERROR_RESPONSES, **ERROR_404},
    ),
)
class InstantaneViewSet(AccomplissementViewSet, ModelViewSet[InstantaneProgramme]):
    serializer_class = serializers.InstantaneSerializer
    queryset = InstantaneProgramme.objects.none()
    http_method_names = ["get", "head", "options"]
    pagination_class = None
    filter_backends = ()  # type: ignore[assignment]

    def get_serializer_class(self) -> type[Serializer[Any]]:
        if self.action == "list":
            return serializers.InstantaneResumeSerializer
        return serializers.InstantaneSerializer

    def get_queryset(self) -> QuerySet[InstantaneProgramme]:
        queryset = InstantaneProgramme.objects.filter(mission__in=self.visibles()).select_related(
            "valide_par"
        )
        if self.action == "list":
            queryset = queryset.defer("donnees").filter(
                mission_id=self.request.query_params["mission"]
            )
        return queryset.order_by("-valide_le", "pk")


# --------------------------------------------------------------------------- tests prévus


@crud_schema(serializers.TestPrevuSerializer, TAG_TESTS, "tests prévus", creation_404=True)
class TestPrevuViewSet(AccomplissementViewSet, ModelViewSet[TestPrevu]):
    __test__ = False

    serializer_class = serializers.TestPrevuSerializer
    queryset = TestPrevu.objects.none()
    filterset_class = filters.TestPrevuFilter
    ordering_fields = ("code", "ordre")
    ordering = ("ordre",)

    def get_queryset(self) -> QuerySet[TestPrevu]:
        queryset: QuerySet[TestPrevu] = TestPrevu.objects.filter(
            mission__in=self.visibles()
        ).select_related("programme__objectif", "auditeur", "risque_mission", "mission")
        return queryset

    def get_object(self) -> Any:
        test: TestPrevu = super().get_object()
        if self.action in ("partial_update", "destroy", "abandon"):
            self._exiger_droit(test)
        return test

    def _exiger_droit(self, test: TestPrevu) -> None:
        """403 avant tout contrôle du corps : compléments et abandons (XII) ou contribution."""
        mission = test.mission
        if test.complementaire or self.action == "abandon":
            _, _, complementaires = droits.profil(
                self.acteur, contexte_actions(mission, self.acteur)
            )
            exiger(complementaires)
        else:
            exiger_contribution(self.acteur, mission)

    def _complementaire(self, mission: Mission) -> bool:
        """Test ajouté pendant l'accomplissement : XII active, VIII et IX non."""
        statuts = statuts_etapes(
            mission.pk,
            (droits.ETAPE_CONTENU, droits.ETAPE_RESSOURCES, droits.ETAPE_COMPLEMENTAIRES),
        )
        programmation = (
            statuts.get(droits.ETAPE_CONTENU) in ACTIFS
            or statuts.get(droits.ETAPE_RESSOURCES) in ACTIFS
        )
        return not programmation and statuts.get(droits.ETAPE_COMPLEMENTAIRES) in ACTIFS

    def _ressources_sans_droit(self, mission: Mission, request: Request) -> bool:
        """Le corps touche des champs de ressources (IX) sans que l'acteur y ait droit."""
        corps = request.data
        if not hasattr(corps, "keys") or not (set(corps.keys()) & svc_tests.CHAMPS_RESSOURCES):
            return False
        _, ressources, _ = droits.profil(self.acteur, contexte_actions(mission, self.acteur))
        return not ressources

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        try:
            return super().partial_update(request, *args, **kwargs)
        except ValidationError:
            # 403 avant 400 : champs de ressources invalides envoyés sans le droit (IX).
            if self._ressources_sans_droit(self.get_object().mission, request):
                raise PermissionDenied from None
            raise

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        try:
            return self._creer(request, *args, **kwargs)
        except ValidationError:
            identifiant = _uuid_du_corps(request, "programme")
            programme = (
                ProgrammeDeTravail.objects.filter(pk=identifiant, mission__in=self.visibles())
                .select_related("mission")
                .first()
            )
            if programme is not None and self._ressources_sans_droit(programme.mission, request):
                raise PermissionDenied from None
            raise

    def _creer(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        identifiant = _uuid_du_corps(request, "programme")
        if identifiant is not None:
            programme = (
                ProgrammeDeTravail.objects.filter(pk=identifiant, mission__in=self.visibles())
                .select_related("mission")
                .first()
            )
            if programme is None:
                raise Http404("Non trouvé.")
            if self._complementaire(programme.mission):
                _, _, complementaires = droits.profil(
                    self.acteur, contexte_actions(programme.mission, self.acteur)
                )
                exiger(complementaires)
            else:
                exiger_contribution(self.acteur, programme.mission)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer: BaseSerializer[TestPrevu]) -> None:
        donnees = dict(serializer.validated_data)
        programme: ProgrammeDeTravail = donnees.pop("programme")
        if self._complementaire(programme.mission):
            test = svc_tests.creer_test_complementaire(programme, by=self.acteur, **donnees)
        else:
            test = svc_tests.creer_test(
                programme,
                libelle=donnees.pop("libelle"),
                nature=donnees.pop("nature", "AUTRE"),
                by=self.acteur,
                **donnees,
            )
        self._publier(serializer, test)

    def perform_update(self, serializer: BaseSerializer[TestPrevu]) -> None:
        instance = self._cible(serializer)
        changements = self.retirer_immuables(serializer.validated_data, instance, ("programme",))
        test = svc_tests.modifier_test(instance, by=self.acteur, **changements)
        self._publier(serializer, test)

    def perform_destroy(self, instance: TestPrevu) -> None:
        svc_tests.supprimer_test(instance, by=self.acteur)

    @_action_schema(
        "Abandonner un test prévu (étape XII, motif obligatoire)",
        serializers.TestPrevuSerializer,
        request=MotifSerializer,
        tag=TAG_TESTS,
    )
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def abandon(self, request: Request, pk: str | None = None) -> Response:
        test = self.get_object()
        corps = MotifSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        svc_tests.abandonner_test(test, motif=corps.validated_data["motif"], by=self.acteur)
        return Response(self.lire_donnees(test.pk))


# --------------------------------------------------------------------------- fiches


@crud_schema(
    serializers.FicheDeTestSerializer,
    TAG_FICHES,
    "fiches de test",
    liste=serializers.FicheDeTestListeSerializer,
    creation_404=True,
)
class FicheViewSet(AccomplissementViewSet, ModelViewSet[FicheDeTest]):
    serializer_class = serializers.FicheDeTestSerializer
    queryset = FicheDeTest.objects.none()
    filterset_class = filters.FicheFilter
    ordering_fields = ("test__numero", "created_at")
    ordering = ("test__numero",)
    actions_redaction = frozenset({"partial_update", "destroy", "submit"})
    actions_validation = frozenset({"validate", "return_", "reopen"})

    def get_serializer_class(self) -> type[Serializer[Any]]:
        if self.action == "list":
            return serializers.FicheDeTestListeSerializer
        return serializers.FicheDeTestSerializer

    def get_queryset(self) -> QuerySet[FicheDeTest]:
        queryset = (
            FicheDeTest.objects.filter(mission__in=self.visibles())
            .select_related("test__programme__objectif", "auteur", "mission")
            .prefetch_related("constats")
        )
        if self.action != "list":
            queryset = queryset.prefetch_related(
                Prefetch(
                    "pieces",
                    queryset=PieceJustificative.objects.select_related(
                        "deposee_par", "mission", "fiche__test"
                    ).order_by("numero"),
                ),
                Prefetch("evenements", queryset=EvenementFiche.objects.select_related("par")),
            )
        return queryset

    def get_object(self) -> Any:
        fiche: FicheDeTest = super().get_object()
        if self.action in self.actions_redaction:
            droits_fiches.exiger_redacteur(self.acteur, fiche.mission, fiche.test)
        elif self.action in self.actions_validation:
            droits_fiches.exiger_valideur(self.acteur, fiche.mission)
        return fiche

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        fiche = self.get_object()
        donnees = self.get_serializer(fiche).data
        if request.method != "HEAD":
            journaliser_consultation(
                fiche, par=self.acteur, action="CONSULTATION", adresse_ip=self.adresse_ip
            )
        return Response(donnees)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        identifiant = _uuid_du_corps(request, "test")
        if identifiant is not None:
            test = (
                TestPrevu.objects.filter(pk=identifiant, mission__in=self.visibles())
                .select_related("mission")
                .first()
            )
            if test is None:
                raise Http404("Non trouvé.")
            droits_fiches.exiger_redacteur(self.acteur, test.mission, test)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer: BaseSerializer[FicheDeTest]) -> None:
        fiche = svc_fiches.creer_fiche(serializer.validated_data["test"], by=self.acteur)
        changements = {
            c: v for c, v in serializer.validated_data.items() if c not in ("test", "mission")
        }
        if changements:
            fiche = svc_fiches.modifier_fiche(fiche, by=self.acteur, **changements)
        self._publier(serializer, fiche)

    def perform_update(self, serializer: BaseSerializer[FicheDeTest]) -> None:
        instance = self._cible(serializer)
        changements = self.retirer_immuables(serializer.validated_data, instance, ("test",))
        fiche = svc_fiches.modifier_fiche(instance, by=self.acteur, **changements)
        self._publier(serializer, fiche)

    def perform_destroy(self, instance: FicheDeTest) -> None:
        svc_fiches.supprimer_fiche(instance, by=self.acteur)

    @_action_schema(
        "Soumettre la fiche à validation", serializers.FicheDeTestSerializer, tag=TAG_FICHES
    )
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def submit(self, request: Request, pk: str | None = None) -> Response:
        fiche = self.get_object()
        svc_fiches.soumettre_fiche(fiche, by=self.acteur)
        return Response(self.lire_donnees(fiche.pk))

    @_action_schema(
        "Valider la fiche (étape XIII)", serializers.FicheDeTestSerializer, tag=TAG_FICHES
    )
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def validate(self, request: Request, pk: str | None = None) -> Response:
        fiche = self.get_object()
        svc_fiches.valider_fiche(fiche, by=self.acteur)
        return Response(self.lire_donnees(fiche.pk))

    @_action_schema(
        "Renvoyer la fiche à son auteur (motif obligatoire)",
        serializers.FicheDeTestSerializer,
        request=MotifSerializer,
        tag=TAG_FICHES,
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="return",
        url_name="return",
        pagination_class=None,
        filter_backends=[],
    )
    def return_(self, request: Request, pk: str | None = None) -> Response:
        fiche = self.get_object()
        corps = MotifSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        svc_fiches.renvoyer_fiche(fiche, motif=corps.validated_data["motif"], by=self.acteur)
        return Response(self.lire_donnees(fiche.pk))

    @_action_schema(
        "Rouvrir une fiche validée (motif obligatoire)",
        serializers.FicheDeTestSerializer,
        request=MotifSerializer,
        tag=TAG_FICHES,
    )
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def reopen(self, request: Request, pk: str | None = None) -> Response:
        fiche = self.get_object()
        corps = MotifSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        svc_fiches.rouvrir_fiche(fiche, motif=corps.validated_data["motif"], by=self.acteur)
        return Response(self.lire_donnees(fiche.pk))


# --------------------------------------------------------------------------- pièces


class NegociationTelechargement(BaseContentNegotiation):
    """Un fichier se télécharge quel que soit l'en-tête `Accept` (jamais de 406)."""

    def select_renderer(  # type: ignore[no-untyped-def]
        self, request, renderers, format_suffix=None
    ):
        return renderers[0], renderers[0].media_type


def _poser_en_tetes(reponse: HttpResponseBase, piece: PieceJustificative) -> None:
    """En-têtes de sécurité de D8 : rien ne s'exécute, rien n'est mis en cache."""
    reponse["Cache-Control"] = "private, no-store"
    reponse["X-Content-Type-Options"] = "nosniff"
    reponse["Content-Security-Policy"] = "default-src 'none'; sandbox"
    reponse["Content-Length"] = str(piece.taille_octets)


@extend_schema_view(
    create=extend_schema(
        tags=[TAG_PIECES],
        summary="Déposer : une pièce justificative (multipart)",
        request={"multipart/form-data": serializers.DepotPieceSerializer},
        parameters=[
            OpenApiParameter(
                "fiche",
                OpenApiTypes.UUID,
                required=False,
                description="Fiche cible : droits contrôlés avant l'analyse du corps (recommandé).",
            )
        ],
        responses={
            201: serializers.PieceJustificativeSerializer,
            200: serializers.PieceJustificativeSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
        description="200 quand les mêmes octets étaient déjà déposés sur la fiche.",
    ),
    list=extend_schema(
        tags=[TAG_PIECES],
        summary="Lister : pièces justificatives (paramètre `fiche` ou `mission` obligatoire)",
        responses={
            200: serializers.PieceJustificativeSerializer(many=True),
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
        },
    ),
)
@crud_schema(serializers.PieceJustificativeSerializer, TAG_PIECES, "pièces justificatives")
class PieceViewSet(AccomplissementViewSet, ModelViewSet[PieceJustificative]):
    serializer_class = serializers.PieceJustificativeSerializer
    queryset = PieceJustificative.objects.none()
    filterset_class = filters.PieceFilter
    ordering_fields = ("numero",)
    ordering = ("numero",)
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self) -> QuerySet[PieceJustificative]:
        queryset: QuerySet[PieceJustificative] = PieceJustificative.objects.filter(
            mission__in=self.visibles()
        ).select_related("deposee_par", "mission", "fiche__test")
        return queryset

    def get_object(self) -> Any:
        piece: PieceJustificative = super().get_object()
        if self.action in ("partial_update", "destroy"):
            droits_fiches.exiger_redacteur(self.acteur, piece.mission, piece.fiche.test)
        return piece

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        brut_fiche = request.query_params.get("fiche")
        if brut_fiche:
            identifiant = _uuid(brut_fiche)
            if identifiant is None:
                raise ValidationError({"fiche": ["Identifiant invalide."]})
            visible = FicheDeTest.objects.filter(pk=identifiant, mission__in=self.visibles())
            if not visible.exists():
                raise Http404("Non trouvé.")
            return ModelViewSet.list(self, request, *args, **kwargs)
        if not request.query_params.get("mission"):
            raise ValidationError({"fiche": [MSG_PARAMETRE], "mission": [MSG_PARAMETRE]})
        self.mission_requise(request)
        return ModelViewSet.list(self, request, *args, **kwargs)

    def _refuser_trop_gros(self, request: Request) -> None:
        """Taille annoncée refusée AVANT toute lecture du corps (le multipart n'est pas analysé)."""
        declare = request.META.get("CONTENT_LENGTH") or "0"
        if declare.isdigit() and int(declare) > taille_maximale() + _MARGE_MULTIPART:
            raise RegleMetierError(MSG_TAILLE, {"fichier": [MSG_TAILLE]})

    def _fiche_redigeable(self, identifiant: UUID) -> FicheDeTest:
        """Fiche visible (404) dont l'acteur est rédacteur (403)."""
        fiche: FicheDeTest | None = (
            FicheDeTest.objects.filter(pk=identifiant, mission__in=self.visibles())
            .select_related("mission", "test")
            .first()
        )
        if fiche is None:
            raise Http404("Non trouvé.")
        droits_fiches.exiger_redacteur(self.acteur, fiche.mission, fiche.test)
        return fiche

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self._refuser_trop_gros(request)
        # `?fiche=` : droits contrôlés AVANT toute lecture du corps (aucun multipart analysé
        # pour un non-rédacteur). Le champ `fiche` du corps reste accepté (analysé d'abord).
        brut = request.query_params.get("fiche")
        fiche_url: FicheDeTest | None = None
        if brut:
            identifiant = _uuid(brut)
            if identifiant is None:
                raise ValidationError({"fiche": ["Identifiant invalide."]})
            fiche_url = self._fiche_redigeable(identifiant)
        else:
            identifiant = _uuid_du_corps(request, "fiche")
            if identifiant is not None:
                self._fiche_redigeable(identifiant)
        corps = serializers.DepotPieceSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        donnees = corps.validated_data
        fiche = donnees.get("fiche") or fiche_url
        if fiche is None:
            raise ValidationError({"fiche": ["Ce champ est obligatoire."]})
        if fiche_url is not None and fiche.pk != fiche_url.pk:
            raise ValidationError({"fiche": ["La fiche du corps diffère de celle de l'URL."]})
        fichier = donnees["fichier"]
        if fichier.size is not None and fichier.size > taille_maximale():  # sans rien lire
            raise RegleMetierError(MSG_TAILLE, {"fichier": [MSG_TAILLE]})
        piece = svc_pieces.deposer_piece(
            fiche,
            fichier=fichier,
            libelle=donnees["libelle"],
            description=donnees["description"],
            by=self.acteur,
        )
        code = status.HTTP_200_OK if piece.doublon else status.HTTP_201_CREATED
        return Response(self.lire_donnees(piece.pk), status=code)

    def perform_update(self, serializer: BaseSerializer[PieceJustificative]) -> None:
        piece = svc_pieces.modifier_piece(
            self._cible(serializer), by=self.acteur, **serializer.validated_data
        )
        self._publier(serializer, piece)

    def perform_destroy(self, instance: PieceJustificative) -> None:
        svc_pieces.retirer_piece(instance, by=self.acteur)

    @extend_schema(
        tags=[TAG_PIECES],
        summary="Télécharger : fichier d'une pièce (journalisé)",
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
        piece: PieceJustificative = self.get_object()
        type_mime = type_contenu(piece.nom_fichier_original)
        if request.method == "HEAD":  # en-têtes seuls : pas de lecture, pas de consultation
            reponse = HttpResponse(content_type=type_mime)
            reponse["Content-Disposition"] = content_disposition_header(
                True, nom_telechargement(piece.nom_fichier_original)
            )
            _poser_en_tetes(reponse, piece)
            return reponse
        try:
            flux = ouvrir_piece_verifiee(piece)
        except FichierIntrouvableError as exc:
            raise IntegriteError from exc
        try:
            journaliser_consultation(
                piece, par=self.acteur, action="TELECHARGEMENT", adresse_ip=self.adresse_ip
            )
        except BaseException:
            flux.close()
            raise
        envoi = FileResponse(
            flux,
            as_attachment=True,
            filename=nom_telechargement(piece.nom_fichier_original),
            content_type=type_mime,
        )
        _poser_en_tetes(envoi, piece)
        return envoi
