"""ViewSets des missions : aucune logique métier, tout passe par `services`.

Ordre des refus : rôle global (403) -> mission invisible (404) -> droit (403) -> sérialiseur
(400) -> règle métier (422).
"""

from collections.abc import Callable
from typing import Any, ClassVar, TypeVar, cast
from uuid import UUID

from django.contrib.contenttypes.models import ContentType
from django.db.models import (
    Case,
    IntegerField,
    OuterRef,
    Prefetch,
    QuerySet,
    Subquery,
    Value,
    When,
)
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer, Serializer
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from apps.core.filters import StableOrderingFilter
from apps.core.reseau import adresse_client
from apps.core.schema import ERROR_400, ERROR_404, ERROR_422, ERROR_RESPONSES, crud_schema
from apps.referentiel.models import NiveauRisque
from apps.signatures.models import Confirmation, TypeDocumentSignable
from apps.users.models import Role, User
from apps.users.serializers import UtilisateurResumeSerializer

from . import acces, filters, serializers
from .etapes import ETAPE_DE_REUNION
from .models import (
    AffectationMission,
    DeclarationIndependance,
    Entretien,
    EtapeMission,
    EvenementEtape,
    Mission,
    Reunion,
    RisqueMission,
)
from .permissions import (
    MissionAccessPermission,
    exiger,
    exiger_contribution,
    exiger_rai,
    mission_du_corps,
    mission_visible,
)
from .services import declarations as svc_declarations
from .services import entretiens as svc_entretiens
from .services import equipe as svc_equipe
from .services import etapes as svc_etapes
from .services import missions as svc_missions
from .services import reunions as svc_reunions
from .services import risques as svc_risques
from .services.etapes import ActionEtape
from .services.suivi import fiche_de_suivi

TAG = "Missions"
F = TypeVar("F", bound=Callable[..., Any])
LECTURE = frozenset({"list", "retrieve"})


def _action_schema(
    summary: str,
    response: Any,
    *,
    request: Any = None,
    tag: str = TAG,
    description: str = "",
) -> Callable[[F], F]:
    erreurs = {**ERROR_RESPONSES, **ERROR_404, **ERROR_422}
    if request is not None:
        erreurs.update(ERROR_400)
    return extend_schema(
        tags=[tag],
        summary=summary,
        description=description,
        request=request,
        responses={200: response, **erreurs},
    )


class MissionApiViewSet(GenericViewSet[Any]):
    """Base : accès par rôle, pas de PUT, adresse IP et acteur."""

    permission_classes = [MissionAccessPermission]
    filter_backends = [DjangoFilterBackend, StableOrderingFilter]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    # Actions ouvertes à l'AUDITE (D4) ; toutes les autres lui répondent 403.
    audite_actions: ClassVar[frozenset[str]] = frozenset()
    # Actions réservées au RAI ; actions d'écriture des travaux (RAI ou contributeur).
    actions_rai: ClassVar[frozenset[str]] = frozenset()
    actions_contribution: ClassVar[frozenset[str]] = frozenset()

    @property
    def acteur(self) -> User:
        return cast(User, self.request.user)

    @property
    def adresse_ip(self) -> str | None:
        return adresse_client(self.request)

    def get_object(self) -> Any:
        objet = super().get_object()
        if self.action in self.actions_rai:
            exiger_rai(self.acteur)
        if self.action in self.actions_contribution:
            exiger_contribution(self.acteur, self.mission_de(objet))
        return objet

    def mission_de(self, objet: Any) -> Mission:
        return cast(Mission, objet.mission)

    def lire(self, pk: Any) -> Any:
        """Représentation de lecture (annotations et préchargements inclus)."""
        serializer = self.get_serializer(self.get_queryset().get(pk=pk))
        return serializer.data

    def _publier(self, serializer: BaseSerializer[Any], obj: Any) -> None:
        serializer.instance = self.get_queryset().get(pk=obj.pk)

    def _cible(self, serializer: BaseSerializer[Any]) -> Any:
        return serializer.instance

    def retirer_immuables(
        self, data: dict[str, Any], instance: Any, champs: tuple[str, ...]
    ) -> dict[str, Any]:
        """Champs fixés à la création : ignorés si inchangés, 400 sinon."""
        propre = dict(data)
        for champ in champs:
            if champ not in propre:
                continue
            valeur = propre.pop(champ)
            actuel = getattr(instance, champ, None)
            if valeur != actuel:
                raise ValidationError({champ: ["Ce champ ne peut pas être modifié."]})
        return propre

    def creer_pour_mission(self, request: Request, ecriture: bool = True) -> Mission | None:
        mission = mission_du_corps(request)
        if mission is not None and ecriture:
            exiger_contribution(self.acteur, mission)
        return mission


# --------------------------------------------------------------------------- missions


def _affectations(*, detail: bool) -> QuerySet[AffectationMission]:
    queryset = AffectationMission.objects.select_related("utilisateur", "declaration")
    if detail:
        confirmations = Confirmation.objects.filter(
            content_type=ContentType.objects.get_for_model(DeclarationIndependance),
            object_id=OuterRef("declaration__pk"),
            type_document=TypeDocumentSignable.DECLARATION_INDEPENDANCE,
        ).order_by("-confirme_le")
        queryset = queryset.annotate(
            declaration_confirmee_le=Subquery(confirmations.values("confirme_le")[:1])
        )
    return queryset.order_by("created_at")


@crud_schema(
    serializers.MissionSerializer,
    TAG,
    "missions",
    liste=serializers.MissionListeSerializer,
)
class MissionViewSet(MissionApiViewSet, ModelViewSet[Mission]):
    queryset = Mission.objects.none()
    filterset_class = filters.MissionFilter
    ordering_fields = ("reference", "date_debut_prevue", "created_at")
    ordering = ("-created_at",)
    audite_actions = LECTURE
    actions_rai = frozenset(
        {
            "partial_update",
            "destroy",
            "plan",
            "launch",
            "issue_order",
            "suspend",
            "resume",
            "cancel",
            "replace_chief",
            "default_auditees",
        }
    )

    def get_serializer_class(self) -> type[Serializer[Any]]:
        if self.action == "list":
            return serializers.MissionListeSerializer
        return serializers.MissionSerializer

    def get_queryset(self) -> QuerySet[Mission]:
        queryset = acces.missions_visibles(self.acteur).prefetch_related(
            Prefetch("affectations", queryset=_affectations(detail=self.action != "list")),
            Prefetch(
                "etapes",
                queryset=EtapeMission.objects.filter(statut="EN_COURS").order_by("numero"),
                to_attr="etapes_en_cours",
            ),
        )
        if self.action != "list":
            queryset = queryset.prefetch_related("processus", "entites")
        return queryset

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        exiger_rai(self.acteur)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer: BaseSerializer[Mission]) -> None:
        mission = svc_missions.creer_mission(**serializer.validated_data, by=self.acteur)
        self._publier(serializer, mission)

    def perform_update(self, serializer: BaseSerializer[Mission]) -> None:
        mission = svc_missions.modifier_mission(
            self._cible(serializer), by=self.acteur, **serializer.validated_data
        )
        self._publier(serializer, mission)

    def perform_destroy(self, instance: Mission) -> None:
        svc_missions.supprimer_mission(instance, by=self.acteur)

    # -- cycle de vie

    @_action_schema("Planifier la mission (référence attribuée)", serializers.MissionSerializer)
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def plan(self, request: Request, pk: str | None = None) -> Response:
        mission = self.get_object()
        svc_missions.planifier_mission(mission, by=self.acteur)
        return Response(self.lire(mission.pk))

    @_action_schema("Lancer la mission (étape I en cours)", serializers.MissionSerializer)
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def launch(self, request: Request, pk: str | None = None) -> Response:
        mission = self.get_object()
        svc_missions.lancer_mission(mission, by=self.acteur)
        return Response(self.lire(mission.pk))

    @_action_schema(
        "Émettre l'ordre de mission (confirmation horodatée)",
        serializers.MissionSerializer,
        request=serializers.ConfirmationSerializer,
        description="Seul `confirme: true` est pris en compte ; `conflit` est ignoré.",
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="issue-order",
        pagination_class=None,
        filter_backends=[],
    )
    def issue_order(self, request: Request, pk: str | None = None) -> Response:
        mission = self.get_object()
        corps = serializers.ConfirmationSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        svc_missions.emettre_ordre_mission(mission, by=self.acteur, adresse_ip=self.adresse_ip)
        return Response(self.lire(mission.pk))

    @_action_schema(
        "Suspendre la mission", serializers.MissionSerializer, request=serializers.MotifSerializer
    )
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def suspend(self, request: Request, pk: str | None = None) -> Response:
        mission = self.get_object()
        corps = serializers.MotifSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        svc_missions.suspendre_mission(mission, motif=corps.validated_data["motif"], by=self.acteur)
        return Response(self.lire(mission.pk))

    @_action_schema("Reprendre la mission suspendue", serializers.MissionSerializer)
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def resume(self, request: Request, pk: str | None = None) -> Response:
        mission = self.get_object()
        svc_missions.reprendre_mission(mission, by=self.acteur)
        return Response(self.lire(mission.pk))

    @_action_schema(
        "Annuler la mission (définitif)",
        serializers.MissionSerializer,
        request=serializers.MotifSerializer,
    )
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def cancel(self, request: Request, pk: str | None = None) -> Response:
        mission = self.get_object()
        corps = serializers.MotifSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        svc_missions.annuler_mission(mission, motif=corps.validated_data["motif"], by=self.acteur)
        return Response(self.lire(mission.pk))

    @_action_schema(
        "Remplacer le chef de mission",
        serializers.MissionSerializer,
        request=serializers.RemplacerChefSerializer,
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="replace-chief",
        pagination_class=None,
        filter_backends=[],
    )
    def replace_chief(self, request: Request, pk: str | None = None) -> Response:
        mission = self.get_object()
        corps = serializers.RemplacerChefSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        svc_equipe.remplacer_chef(
            mission, utilisateur=corps.validated_data["utilisateur"], by=self.acteur
        )
        return Response(self.lire(mission.pk))

    # -- lectures

    @_action_schema("Fiche de suivi de la mission", serializers.FicheSuiviSerializer)
    @action(detail=True, methods=["get"], pagination_class=None, filter_backends=[])
    def tracking(self, request: Request, pk: str | None = None) -> Response:
        mission = self.get_object()
        return Response(serializers.FicheSuiviSerializer(fiche_de_suivi(mission)).data)

    @_action_schema("Matrice 5x5 des risques de la mission", serializers.MatriceMissionSerializer)
    @action(
        detail=True,
        methods=["get"],
        url_path="risk-matrix",
        pagination_class=None,
        filter_backends=[],
    )
    def risk_matrix(self, request: Request, pk: str | None = None) -> Response:
        mission = self.get_object()
        cellules = svc_risques.matrice_mission(mission)
        par_niveau = {n.value: 0 for n in NiveauRisque}
        for cellule in cellules:
            par_niveau[cellule.niveau] += cellule.nombre
        donnees = {
            "mission": mission.pk,
            "total": sum(par_niveau.values()),
            "par_niveau": par_niveau,
            "cellules": cellules,
        }
        return Response(serializers.MatriceMissionSerializer(donnees).data)

    @_action_schema(
        "Audités proposés par défaut (rattachés aux entités de la mission)",
        UtilisateurResumeSerializer(many=True),
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="default-auditees",
        pagination_class=None,
        filter_backends=[],
    )
    def default_auditees(self, request: Request, pk: str | None = None) -> Response:
        mission = self.get_object()
        return Response(
            UtilisateurResumeSerializer(svc_equipe.audites_par_defaut(mission), many=True).data
        )


# --------------------------------------------------------------------------- équipe


@extend_schema_view(
    list=extend_schema(
        tags=[TAG],
        summary="Lister : affectations",
        responses={
            200: serializers.AffectationSerializer(many=True),
            **ERROR_400,
            **ERROR_RESPONSES,
        },
    ),
    retrieve=extend_schema(
        tags=[TAG],
        summary="Détail : affectation",
        responses={200: serializers.AffectationSerializer, **ERROR_RESPONSES, **ERROR_404},
    ),
    create=extend_schema(
        tags=[TAG],
        summary="Affecter un utilisateur à la mission",
        responses={
            201: serializers.AffectationSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
    ),
    partial_update=extend_schema(
        tags=[TAG],
        summary="Désigner ou retirer le responsable de l'entité",
        description=(
            "Seul `responsable_entite` est pris en compte ; les autres champs sont ignorés."
        ),
        responses={
            200: serializers.AffectationSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
    ),
    destroy=extend_schema(
        tags=[TAG],
        summary="Désaffecter (logiquement)",
        responses={204: None, **ERROR_RESPONSES, **ERROR_404, **ERROR_422},
    ),
)
class AffectationViewSet(
    MissionApiViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
):
    serializer_class = serializers.AffectationSerializer
    queryset = AffectationMission.objects.none()
    filterset_class = filters.AffectationFilter
    ordering_fields = ("created_at",)
    ordering = ("created_at",)
    actions_rai = frozenset({"destroy", "partial_update"})

    def get_queryset(self) -> QuerySet[AffectationMission]:
        return _affectations(detail=True).filter(mission__in=acces.missions_visibles(self.acteur))

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        mission_du_corps(request)
        exiger_rai(self.acteur)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer: BaseSerializer[AffectationMission]) -> None:
        donnees = serializer.validated_data
        affectation = svc_equipe.affecter(
            donnees["mission"],
            utilisateur=donnees["utilisateur"],
            role_mission=donnees["role_mission"],
            responsable_entite=donnees["responsable_entite"],
            by=self.acteur,
        )
        self._publier(serializer, affectation)

    def perform_update(self, serializer: BaseSerializer[AffectationMission]) -> None:
        # Seule la désignation du responsable de l'entité est modifiable (équipe figée sinon).
        affectation = self._cible(serializer)
        responsable = serializer.validated_data.get("responsable_entite")
        if responsable is not None:
            affectation = svc_equipe.definir_responsable_entite(
                affectation, responsable=responsable, by=self.acteur
            )
        self._publier(serializer, affectation)

    def perform_destroy(self, instance: AffectationMission) -> None:
        svc_equipe.desaffecter(instance, by=self.acteur)


# --------------------------------------------------------------------------- déclarations


@extend_schema_view(
    list=extend_schema(
        tags=[TAG],
        summary="Lister : déclarations d'indépendance",
        responses={
            200: serializers.DeclarationSerializer(many=True),
            **ERROR_400,
            **ERROR_RESPONSES,
        },
    ),
    retrieve=extend_schema(
        tags=[TAG],
        summary="Détail : déclaration d'indépendance",
        responses={200: serializers.DeclarationSerializer, **ERROR_RESPONSES, **ERROR_404},
    ),
)
class DeclarationViewSet(MissionApiViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    serializer_class = serializers.DeclarationSerializer
    queryset = DeclarationIndependance.objects.none()
    filterset_class = filters.DeclarationFilter
    ordering_fields = ("created_at",)
    ordering = ("created_at",)

    def get_queryset(self) -> QuerySet[DeclarationIndependance]:
        return DeclarationIndependance.objects.filter(
            affectation__mission__in=acces.missions_visibles(self.acteur),
            affectation__deleted_at__isnull=True,
        ).select_related("affectation__mission", "affectation__utilisateur", "arbitre_par")

    @_action_schema(
        "Confirmer ma déclaration d'indépendance",
        serializers.DeclarationSerializer,
        request=serializers.ConfirmationSerializer,
    )
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def confirm(self, request: Request, pk: str | None = None) -> Response:
        declaration = self.get_object()
        exiger(declaration.affectation.utilisateur_id == self.acteur.pk)
        corps = serializers.ConfirmationSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        svc_declarations.confirmer_declaration(
            declaration,
            by=self.acteur,
            conflit=corps.validated_data["conflit"],
            description_conflit=corps.validated_data["description_conflit"],
            adresse_ip=self.adresse_ip,
        )
        return Response(self.lire(declaration.pk))

    @_action_schema(
        "Arbitrer une situation déclarée",
        serializers.DeclarationSerializer,
        request=serializers.ArbitrageSerializer,
    )
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def arbitrate(self, request: Request, pk: str | None = None) -> Response:
        declaration = self.get_object()
        exiger_rai(self.acteur)
        corps = serializers.ArbitrageSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        svc_declarations.arbitrer_conflit(
            declaration, justification=corps.validated_data["justification"], by=self.acteur
        )
        return Response(self.lire(declaration.pk))

    def mission_de(self, objet: Any) -> Mission:
        return cast(Mission, objet.affectation.mission)


# --------------------------------------------------------------------------- étapes


@extend_schema_view(
    list=extend_schema(
        tags=[TAG],
        summary="Les 18 étapes d'une mission",
        responses={
            200: serializers.EtapeSerializer(many=True),
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
        },
    ),
    retrieve=extend_schema(
        tags=[TAG],
        summary="Détail : étape",
        responses={200: serializers.EtapeSerializer, **ERROR_RESPONSES, **ERROR_404},
    ),
    partial_update=extend_schema(
        tags=[TAG],
        summary="Planifier une étape (dates prévues et charges)",
        responses={
            200: serializers.EtapeSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
    ),
)
class EtapeViewSet(
    MissionApiViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
):
    serializer_class = serializers.EtapeSerializer
    queryset = EtapeMission.objects.none()
    pagination_class = None
    http_method_names = ["get", "post", "patch", "head", "options"]
    filterset_class = filters.EtapeFilter
    ordering = ("numero",)
    # Lecture seule pour l'audité : le plan d'actions (étape XVI) a besoin de l'état des étapes.
    audite_actions = frozenset({"list", "retrieve"})
    _mission_liste: Mission | None = None
    _statuts_liste: dict[int, str] | None = None

    def get_queryset(self) -> QuerySet[EtapeMission]:
        queryset = EtapeMission.objects.filter(
            mission__in=acces.missions_visibles(self.acteur)
        ).select_related("terminee_par", "validee_par")
        if self.action != "list":
            queryset = queryset.prefetch_related(
                Prefetch("evenements", queryset=EvenementEtape.objects.select_related("par"))
            )
        return queryset

    def get_serializer_context(self) -> dict[str, Any]:
        contexte = dict(super().get_serializer_context())
        contexte["detail"] = self.action != "list"
        if self.action == "list" and self._mission_liste is not None:
            contexte["contexte_actions"] = svc_etapes.contexte_actions(
                self._mission_liste, self.acteur, statuts=self._statuts_liste
            )
        return contexte

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        brut = request.query_params.get("mission")
        if not brut:
            raise ValidationError({"mission": ["Ce paramètre est obligatoire."]})
        try:
            identifiant = UUID(brut)
        except ValueError as e:
            raise ValidationError({"mission": ["Identifiant invalide."]}) from e
        self._mission_liste = mission_visible(self.acteur, identifiant)
        etapes = list(self.get_queryset().filter(mission=self._mission_liste).order_by("numero"))
        self._statuts_liste = {e.numero: e.statut for e in etapes}
        return Response(self.get_serializer(etapes, many=True).data)

    def perform_update(self, serializer: BaseSerializer[EtapeMission]) -> None:
        etape = svc_etapes.planifier_etape(
            self._cible(serializer), by=self.acteur, **serializer.validated_data
        )
        self._publier(serializer, etape)

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        # Droit (403) avant le corps (400).
        svc_etapes.exiger_droit(self.get_object(), ActionEtape.PLANIFIER, self.acteur)
        return super().update(request, *args, **kwargs)

    def _transition(
        self, request: Request, service: Any, action_etape: str, *, motif: bool = False
    ) -> Response:
        etape = self.get_object()
        svc_etapes.exiger_droit(etape, action_etape, self.acteur)
        svc_etapes.exiger_action_generique(etape, action_etape)
        if motif:
            corps = serializers.MotifSerializer(data=request.data)
            corps.is_valid(raise_exception=True)
            service(etape, motif=corps.validated_data["motif"], by=self.acteur)
        else:
            service(etape, by=self.acteur)
        return Response(self.lire(etape.pk))

    @_action_schema(
        "Démarrer l'étape (motif facultatif : dérogation du RAI à l'ordre des étapes)",
        serializers.EtapeSerializer,
        request=serializers.DerogationSerializer,
    )
    @action(detail=True, methods=["post"], filter_backends=[])
    def start(self, request: Request, pk: str | None = None) -> Response:
        etape = self.get_object()
        svc_etapes.exiger_droit(etape, ActionEtape.DEMARRER, self.acteur)
        svc_etapes.exiger_action_generique(etape, ActionEtape.DEMARRER)
        corps = serializers.DerogationSerializer(data=request.data or {})
        corps.is_valid(raise_exception=True)
        svc_etapes.demarrer_etape(
            etape, by=self.acteur, derogation=corps.validated_data.get("motif", "")
        )
        return Response(self.lire(etape.pk))

    @_action_schema("Terminer l'étape", serializers.EtapeSerializer)
    @action(detail=True, methods=["post"], filter_backends=[])
    def complete(self, request: Request, pk: str | None = None) -> Response:
        return self._transition(request, svc_etapes.terminer_etape, ActionEtape.TERMINER)

    @_action_schema("Valider le jalon", serializers.EtapeSerializer)
    @action(detail=True, methods=["post"], filter_backends=[])
    def validate(self, request: Request, pk: str | None = None) -> Response:
        return self._transition(request, svc_etapes.valider_etape, ActionEtape.VALIDER)

    @_action_schema(
        "Renvoyer le jalon",
        serializers.EtapeSerializer,
        request=serializers.MotifSerializer,
    )
    @action(detail=True, methods=["post"], url_path="return", filter_backends=[])
    def send_back(self, request: Request, pk: str | None = None) -> Response:
        return self._transition(
            request, svc_etapes.renvoyer_etape, ActionEtape.RENVOYER, motif=True
        )

    @_action_schema(
        "Rouvrir l'étape",
        serializers.EtapeSerializer,
        request=serializers.MotifSerializer,
    )
    @action(detail=True, methods=["post"], filter_backends=[])
    def reopen(self, request: Request, pk: str | None = None) -> Response:
        return self._transition(request, svc_etapes.rouvrir_etape, ActionEtape.ROUVRIR, motif=True)

    @_action_schema(
        "Marquer l'étape non applicable",
        serializers.EtapeSerializer,
        request=serializers.MotifSerializer,
    )
    @action(detail=True, methods=["post"], url_path="not-applicable", filter_backends=[])
    def not_applicable(self, request: Request, pk: str | None = None) -> Response:
        return self._transition(
            request, svc_etapes.marquer_non_applicable, ActionEtape.NON_APPLICABLE, motif=True
        )

    @_action_schema("Rétablir l'étape non applicable", serializers.EtapeSerializer)
    @action(detail=True, methods=["post"], filter_backends=[])
    def restore(self, request: Request, pk: str | None = None) -> Response:
        return self._transition(request, svc_etapes.retablir_etape, ActionEtape.RETABLIR)


# --------------------------------------------------------------------------- réunions


def _numero_etape_reunion() -> Case:
    return Case(
        *[When(type=type_, then=Value(numero)) for type_, numero in ETAPE_DE_REUNION.items()],
        default=Value(0),
        output_field=IntegerField(),
    )


@crud_schema(serializers.ReunionSerializer, TAG, "réunions", creation_404=True)
class ReunionViewSet(MissionApiViewSet, ModelViewSet[Reunion]):
    serializer_class = serializers.ReunionSerializer
    queryset = Reunion.objects.none()
    filterset_class = filters.ReunionFilter
    ordering_fields = ("date",)
    ordering = ("date",)
    audite_actions = LECTURE
    actions_contribution = frozenset({"partial_update", "destroy", "mark_held"})

    def get_queryset(self) -> QuerySet[Reunion]:
        queryset: QuerySet[Reunion] = (
            Reunion.objects.filter(mission__in=acces.missions_visibles(self.acteur))
            .annotate(numero_etape=_numero_etape_reunion())
            .annotate(
                etape_statut=Subquery(
                    EtapeMission.objects.filter(
                        mission=OuterRef("mission"), numero=OuterRef("numero_etape")
                    ).values("statut")[:1]
                )
            )
            .prefetch_related("participants")
        )
        return queryset

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self.creer_pour_mission(request)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer: BaseSerializer[Reunion]) -> None:
        donnees = dict(serializer.validated_data)
        reunion = svc_reunions.creer_reunion(
            donnees.pop("mission"),
            type=donnees.pop("type"),
            date=donnees.pop("date"),
            participants=donnees.pop("participants", ()),
            by=self.acteur,
            **donnees,
        )
        self._publier(serializer, reunion)

    def perform_update(self, serializer: BaseSerializer[Reunion]) -> None:
        instance = self._cible(serializer)
        changements = self.retirer_immuables(
            serializer.validated_data, instance, ("mission", "type")
        )
        reunion = svc_reunions.modifier_reunion(instance, by=self.acteur, **changements)
        self._publier(serializer, reunion)

    def perform_destroy(self, instance: Reunion) -> None:
        svc_reunions.supprimer_reunion(instance, by=self.acteur)

    @_action_schema("Marquer la réunion comme tenue", serializers.ReunionSerializer)
    @action(
        detail=True,
        methods=["post"],
        url_path="mark-held",
        pagination_class=None,
        filter_backends=[],
    )
    def mark_held(self, request: Request, pk: str | None = None) -> Response:
        reunion = self.get_object()
        svc_reunions.marquer_reunion_tenue(reunion, by=self.acteur)
        return Response(self.lire(reunion.pk))


# --------------------------------------------------------------------------- entretiens


@crud_schema(serializers.EntretienSerializer, TAG, "entretiens", creation_404=True)
class EntretienViewSet(MissionApiViewSet, ModelViewSet[Entretien]):
    serializer_class = serializers.EntretienSerializer
    queryset = Entretien.objects.none()
    filterset_class = filters.EntretienFilter
    ordering_fields = ("date_prevue",)
    ordering = ("date_prevue",)
    audite_actions = LECTURE
    actions_contribution = frozenset({"partial_update", "destroy", "mark_done", "cancel"})

    def get_queryset(self) -> QuerySet[Entretien]:
        queryset = Entretien.objects.filter(mission__in=acces.missions_visibles(self.acteur))
        if self.acteur.role == Role.AUDITE:
            queryset = queryset.filter(interlocuteurs=self.acteur)
        return queryset.select_related("etape").prefetch_related("auditeurs", "interlocuteurs")

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self.creer_pour_mission(request)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer: BaseSerializer[Entretien]) -> None:
        donnees = dict(serializer.validated_data)
        entretien = svc_entretiens.creer_entretien(
            donnees.pop("mission"),
            objet=donnees.pop("objet"),
            date_prevue=donnees.pop("date_prevue"),
            etape=donnees.pop("etape", None),
            auditeurs=donnees.pop("auditeurs", ()),
            interlocuteurs=donnees.pop("interlocuteurs", ()),
            by=self.acteur,
            **donnees,
        )
        self._publier(serializer, entretien)

    def perform_update(self, serializer: BaseSerializer[Entretien]) -> None:
        instance = self._cible(serializer)
        changements = self.retirer_immuables(serializer.validated_data, instance, ("mission",))
        entretien = svc_entretiens.modifier_entretien(instance, by=self.acteur, **changements)
        self._publier(serializer, entretien)

    def perform_destroy(self, instance: Entretien) -> None:
        svc_entretiens.supprimer_entretien(instance, by=self.acteur)

    @_action_schema("Marquer l'entretien comme réalisé", serializers.EntretienSerializer)
    @action(
        detail=True,
        methods=["post"],
        url_path="mark-done",
        pagination_class=None,
        filter_backends=[],
    )
    def mark_done(self, request: Request, pk: str | None = None) -> Response:
        entretien = self.get_object()
        svc_entretiens.marquer_entretien_realise(entretien, by=self.acteur)
        return Response(self.lire(entretien.pk))

    @_action_schema(
        "Annuler l'entretien",
        serializers.EntretienSerializer,
        request=serializers.MotifSerializer,
    )
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def cancel(self, request: Request, pk: str | None = None) -> Response:
        entretien = self.get_object()
        corps = serializers.MotifSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        svc_entretiens.annuler_entretien(
            entretien, motif=corps.validated_data["motif"], by=self.acteur
        )
        return Response(self.lire(entretien.pk))


# --------------------------------------------------------------------------- risques


@crud_schema(serializers.RisqueMissionSerializer, TAG, "risques de mission", creation_404=True)
class RisqueMissionViewSet(MissionApiViewSet, ModelViewSet[RisqueMission]):
    serializer_class = serializers.RisqueMissionSerializer
    queryset = RisqueMission.objects.none()
    filterset_class = filters.RisqueMissionFilter
    ordering_fields = ("score", "code_source")
    ordering = ("created_at",)
    actions_contribution = frozenset({"partial_update", "destroy"})

    def get_queryset(self) -> QuerySet[RisqueMission]:
        return RisqueMission.objects.filter(
            mission__in=acces.missions_visibles(self.acteur)
        ).select_related("mission", "processus", "risque_source")

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        params = request.query_params
        if params.get("nouveau", "").lower() in ("true", "1") and not params.get("mission"):
            # Risques proposés par les missions : lecture réservée au RAI.
            exiger_rai(self.acteur)
        return super().list(request, *args, **kwargs)

    def filter_queryset(self, queryset: QuerySet[Any]) -> QuerySet[Any]:
        params = self.request.query_params
        if (
            self.action == "list"
            and params.get("nouveau", "").lower() in ("true", "1")
            and not params.get("mission")
        ):
            queryset = svc_risques.risques_proposes().select_related("risque_source")
        return super().filter_queryset(queryset)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self.creer_pour_mission(request)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer: BaseSerializer[RisqueMission]) -> None:
        donnees = dict(serializer.validated_data)
        risque = svc_risques.ajouter_risque_mission(
            donnees.pop("mission"), by=self.acteur, **donnees
        )
        self._publier(serializer, risque)

    def perform_update(self, serializer: BaseSerializer[RisqueMission]) -> None:
        instance = self._cible(serializer)
        changements = self.retirer_immuables(
            serializer.validated_data, instance, ("mission", "risque_source", "processus")
        )
        risque = svc_risques.modifier_risque_mission(instance, by=self.acteur, **changements)
        self._publier(serializer, risque)

    def perform_destroy(self, instance: RisqueMission) -> None:
        svc_risques.retirer_risque_mission(instance, by=self.acteur)
