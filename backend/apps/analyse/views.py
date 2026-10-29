"""ViewSets de l'analyse : aucune logique métier, tout passe par `services`.

Ordre des refus : rôle global (403) -> mission invisible (404) -> droit de contribuer (403)
-> sérialiseur (400) -> règle métier, gel ou fenêtre d'écriture (422, portés par les services).
"""

from typing import Any
from uuid import UUID

from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q, QuerySet
from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.viewsets import ModelViewSet

from apps.core.schema import ERROR_400, ERROR_404, ERROR_422, ERROR_RESPONSES, crud_schema
from apps.missions import acces
from apps.missions.models import Mission
from apps.missions.permissions import exiger, exiger_contribution, mission_visible
from apps.missions.views import LECTURE, MissionApiViewSet, _action_schema
from apps.signatures.services import verifier
from apps.users.models import Role

from . import filters, serializers
from .droits import droits_analyse
from .models import (
    Appreciation,
    DescriptionProcessus,
    ForceFaiblesse,
    GrilleSeparation,
    LigneMARC,
    ObjectifAudit,
    Questionnaire,
    QuestionQuestionnaire,
    RapportOrientation,
    StatutReferentiel,
)
from .permissions import AnalyseAccessPermission, exiger_referentiel_visible
from .services import descriptions as svc_descriptions
from .services import forces_faiblesses as svc_ff
from .services import grilles as svc_grilles
from .services import marc as svc_marc
from .services import objectifs as svc_objectifs
from .services import orientation as svc_orientation
from .services import questionnaires as svc_questionnaires
from .services import referentiel as svc_referentiel

TAG_TRAVAUX = "Analyse"
TAG_REFERENTIEL = "Référentiel d'audit"
TAG_OBJECTIFS = "Objectifs d'audit"
MSG_PARAMETRE = "Ce paramètre est obligatoire."


def _uuid(brut: Any) -> UUID | None:
    try:
        return UUID(str(brut))
    except ValueError:
        return None


class AnalyseViewSet(MissionApiViewSet):
    """Base : liste bornée à une mission visible, référentiel masqué à l'audité non diffusé."""

    permission_classes = [AnalyseAccessPermission]
    actions_contribution = frozenset({"partial_update", "destroy"})
    parametre_liste = "mission"

    def get_object(self) -> Any:
        objet = super().get_object()
        if self.acteur.role == Role.AUDITE:
            exiger_referentiel_visible(self.acteur, self.mission_de(objet))
        return objet

    def mission_de_liste(self, brut: UUID) -> Mission:
        return mission_visible(self.acteur, brut)

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        brut = request.query_params.get(self.parametre_liste)
        if not brut:
            raise ValidationError({self.parametre_liste: [MSG_PARAMETRE]})
        identifiant = _uuid(brut)
        if identifiant is None:
            raise ValidationError({self.parametre_liste: ["Identifiant invalide."]})
        mission = self.mission_de_liste(identifiant)
        if self.acteur.role == Role.AUDITE:
            exiger_referentiel_visible(self.acteur, mission)
        return super().list(request, *args, **kwargs)  # type: ignore[misc, no-any-return]

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self.creer_pour_mission(request)
        return super().create(request, *args, **kwargs)  # type: ignore[misc, no-any-return]

    def reponse_liste(self, mission: Mission, lignes: QuerySet[Any]) -> Response:
        return Response(self.get_serializer(lignes, many=True).data)


# --------------------------------------------------------------------------- étape III


@crud_schema(serializers.QuestionnaireSerializer, TAG_TRAVAUX, "questionnaires", creation_404=True)
class QuestionnaireViewSet(AnalyseViewSet, ModelViewSet[Questionnaire]):
    serializer_class = serializers.QuestionnaireSerializer
    queryset = Questionnaire.objects.none()
    filterset_class = filters.QuestionnaireFilter
    ordering_fields = ("created_at",)
    ordering = ("created_at",)

    def get_queryset(self) -> QuerySet[Questionnaire]:
        actives = Q(questions__deleted_at__isnull=True)
        repondue = Q(questions__appreciation__in=Appreciation.values) | Q(
            questions__reponse__regex=r"\S"
        )
        queryset: QuerySet[Questionnaire] = (
            Questionnaire.objects.filter(mission__in=acces.missions_visibles(self.acteur))
            .select_related("processus", "mission")
            .annotate(
                nb_questions=Count("questions", filter=actives),
                nb_repondues=Count("questions", filter=actives & repondue),
            )
        )
        return queryset

    def perform_create(self, serializer: BaseSerializer[Questionnaire]) -> None:
        donnees = dict(serializer.validated_data)
        questionnaire = svc_questionnaires.creer_questionnaire(
            donnees.pop("mission"),
            type=donnees.pop("type"),
            processus=donnees.pop("processus", None),
            titre=donnees.pop("titre", ""),
            by=self.acteur,
        )
        self._publier(serializer, questionnaire)

    def perform_update(self, serializer: BaseSerializer[Questionnaire]) -> None:
        instance = self._cible(serializer)
        changements = self.retirer_immuables(
            serializer.validated_data, instance, ("mission", "type", "processus")
        )
        questionnaire = svc_questionnaires.modifier_questionnaire(
            instance, by=self.acteur, **changements
        )
        self._publier(serializer, questionnaire)

    def perform_destroy(self, instance: Questionnaire) -> None:
        svc_questionnaires.retirer_questionnaire(instance, by=self.acteur)


@crud_schema(serializers.QuestionSerializer, TAG_TRAVAUX, "questions", creation_404=True)
class QuestionViewSet(AnalyseViewSet, ModelViewSet[QuestionQuestionnaire]):
    serializer_class = serializers.QuestionSerializer
    queryset = QuestionQuestionnaire.objects.none()
    filterset_class = filters.QuestionFilter
    pagination_class = None
    ordering_fields = ("ordre",)
    ordering = ("ordre",)
    parametre_liste = "questionnaire"

    def get_queryset(self) -> QuerySet[QuestionQuestionnaire]:
        return QuestionQuestionnaire.objects.filter(
            mission__in=acces.missions_visibles(self.acteur)
        ).select_related("questionnaire", "mission")

    def _questionnaire_visible(self, identifiant: UUID) -> Questionnaire:
        trouve: Questionnaire | None = (
            Questionnaire.objects.filter(
                pk=identifiant, mission__in=acces.missions_visibles(self.acteur)
            )
            .select_related("mission")
            .first()
        )
        if trouve is None:
            raise Http404("Non trouvé.")
        return trouve

    def mission_de_liste(self, brut: UUID) -> Mission:
        return self._questionnaire_visible(brut).mission

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        brut = request.data.get("questionnaire") if hasattr(request.data, "get") else None
        identifiant = _uuid(brut) if brut is not None else None
        if identifiant is not None:
            exiger_contribution(self.acteur, self._questionnaire_visible(identifiant).mission)
        return ModelViewSet.create(self, request, *args, **kwargs)

    def perform_create(self, serializer: BaseSerializer[QuestionQuestionnaire]) -> None:
        donnees = dict(serializer.validated_data)
        with transaction.atomic():
            question = svc_questionnaires.ajouter_question(
                donnees.pop("questionnaire"),
                theme=donnees.pop("theme"),
                libelle=donnees.pop("libelle"),
                ordre=donnees.pop("ordre", None),
                by=self.acteur,
            )
            if donnees:
                question = svc_questionnaires.modifier_question(question, by=self.acteur, **donnees)
        self._publier(serializer, question)

    def perform_update(self, serializer: BaseSerializer[QuestionQuestionnaire]) -> None:
        instance = self._cible(serializer)
        changements = self.retirer_immuables(
            serializer.validated_data, instance, ("questionnaire",)
        )
        question = svc_questionnaires.modifier_question(instance, by=self.acteur, **changements)
        self._publier(serializer, question)

    def perform_destroy(self, instance: QuestionQuestionnaire) -> None:
        svc_questionnaires.retirer_question(instance, by=self.acteur)


class _UpsertViewSet(AnalyseViewSet):
    """POST d'un objet unique par (mission, processus) : crée ou met à jour (200 si existait)."""

    existait = False

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self.existait = False
        reponse: Response = super().create(request, *args, **kwargs)
        if self.existait and reponse.status_code == status.HTTP_201_CREATED:
            reponse.status_code = status.HTTP_200_OK
        return reponse


@crud_schema(
    serializers.DescriptionProcessusSerializer,
    TAG_TRAVAUX,
    "descriptions de processus",
    creation_404=True,
)
class DescriptionProcessusViewSet(_UpsertViewSet, ModelViewSet[DescriptionProcessus]):
    serializer_class = serializers.DescriptionProcessusSerializer
    queryset = DescriptionProcessus.objects.none()
    filterset_class = filters.DescriptionFilter
    ordering_fields = ("created_at",)
    ordering = ("created_at",)

    def get_queryset(self) -> QuerySet[DescriptionProcessus]:
        return DescriptionProcessus.objects.filter(
            mission__in=acces.missions_visibles(self.acteur)
        ).select_related("processus", "mission")

    def perform_create(self, serializer: BaseSerializer[DescriptionProcessus]) -> None:
        donnees = dict(serializer.validated_data)
        mission = donnees.pop("mission")
        processus = donnees.pop("processus")
        self.existait = DescriptionProcessus.objects.filter(
            mission=mission, processus=processus
        ).exists()
        description = svc_descriptions.enregistrer_description(
            mission, processus=processus, by=self.acteur, **donnees
        )
        self._publier(serializer, description)

    def perform_update(self, serializer: BaseSerializer[DescriptionProcessus]) -> None:
        instance = self._cible(serializer)
        changements = self.retirer_immuables(
            serializer.validated_data, instance, ("mission", "processus")
        )
        description = svc_descriptions.enregistrer_description(
            instance.mission, processus=instance.processus, by=self.acteur, **changements
        )
        self._publier(serializer, description)

    def perform_destroy(self, instance: DescriptionProcessus) -> None:
        svc_descriptions.retirer_description(instance, by=self.acteur)


@crud_schema(
    serializers.GrilleSeparationSerializer,
    TAG_TRAVAUX,
    "grilles de séparation des tâches",
    creation_404=True,
)
class GrilleSeparationViewSet(_UpsertViewSet, ModelViewSet[GrilleSeparation]):
    serializer_class = serializers.GrilleSeparationSerializer
    queryset = GrilleSeparation.objects.none()
    filterset_class = filters.GrilleFilter
    ordering_fields = ("created_at",)
    ordering = ("created_at",)

    def get_queryset(self) -> QuerySet[GrilleSeparation]:
        return GrilleSeparation.objects.filter(
            mission__in=acces.missions_visibles(self.acteur)
        ).select_related("processus", "mission")

    def perform_create(self, serializer: BaseSerializer[GrilleSeparation]) -> None:
        donnees = dict(serializer.validated_data)
        mission = donnees.pop("mission")
        processus = donnees.pop("processus")
        self.existait = GrilleSeparation.objects.filter(
            mission=mission, processus=processus
        ).exists()
        grille = svc_grilles.enregistrer_grille(
            mission,
            processus=processus,
            taches=donnees.pop("taches", []),
            acteurs=donnees.pop("acteurs", []),
            cellules=donnees.pop("cellules", []),
            commentaire=donnees.pop("commentaire", ""),
            by=self.acteur,
        )
        self._publier(serializer, grille)

    def perform_update(self, serializer: BaseSerializer[GrilleSeparation]) -> None:
        instance = self._cible(serializer)
        changements = self.retirer_immuables(
            serializer.validated_data, instance, ("mission", "processus")
        )
        grille = svc_grilles.enregistrer_grille(
            instance.mission,
            processus=instance.processus,
            taches=changements.get("taches", instance.taches),
            acteurs=changements.get("acteurs", instance.acteurs),
            cellules=changements.get("cellules", instance.cellules),
            commentaire=changements.get("commentaire", instance.commentaire),
            by=self.acteur,
        )
        self._publier(serializer, grille)

    def perform_destroy(self, instance: GrilleSeparation) -> None:
        svc_grilles.retirer_grille(instance, by=self.acteur)


# --------------------------------------------------------------------------- étapes V et VI


@crud_schema(
    serializers.LigneMARCSerializer, TAG_REFERENTIEL, "lignes de la MARC", creation_404=True
)
class LigneMARCViewSet(AnalyseViewSet, ModelViewSet[LigneMARC]):
    serializer_class = serializers.LigneMARCSerializer
    queryset = LigneMARC.objects.none()
    filterset_class = filters.LigneMARCFilter
    ordering_fields = ("ordre", "risque__score")
    ordering = ("ordre",)
    audite_actions = LECTURE

    def get_queryset(self) -> QuerySet[LigneMARC]:
        queryset: QuerySet[LigneMARC] = (
            LigneMARC.objects.filter(mission__in=acces.missions_visibles(self.acteur))
            .select_related("risque", "risque__processus", "objet_auditable", "mission")
            .annotate(a_objectif=Exists(ObjectifAudit.objects.filter(ligne_marc=OuterRef("pk"))))
        )
        return queryset

    def perform_create(self, serializer: BaseSerializer[LigneMARC]) -> None:
        donnees = dict(serializer.validated_data)
        ligne = svc_marc.ajouter_ligne_marc(
            donnees.pop("mission"), risque=donnees.pop("risque"), by=self.acteur, **donnees
        )
        self._publier(serializer, ligne)

    def perform_update(self, serializer: BaseSerializer[LigneMARC]) -> None:
        instance = self._cible(serializer)
        changements = self.retirer_immuables(
            serializer.validated_data, instance, ("mission", "risque")
        )
        ligne = svc_marc.modifier_ligne_marc(instance, by=self.acteur, **changements)
        self._publier(serializer, ligne)

    def perform_destroy(self, instance: LigneMARC) -> None:
        svc_marc.retirer_ligne_marc(instance, by=self.acteur)

    @_action_schema(
        "Initialiser la MARC (une ligne par risque non couvert)",
        serializers.LigneMARCSerializer(many=True),
        request=serializers.MissionRequestSerializer,
        tag=TAG_REFERENTIEL,
    )
    @action(detail=False, methods=["post"], pagination_class=None, filter_backends=[])
    def initialize(self, request: Request) -> Response:
        self.creer_pour_mission(request)
        corps = serializers.MissionRequestSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        creees = svc_marc.initialiser_marc(corps.validated_data["mission"], by=self.acteur)
        lignes = self.get_queryset().filter(pk__in=[ligne.pk for ligne in creees])
        return self.reponse_liste(corps.validated_data["mission"], lignes.order_by("ordre", "pk"))


@crud_schema(
    serializers.ForceFaiblesseSerializer,
    TAG_REFERENTIEL,
    "forces et faiblesses apparentes",
    creation_404=True,
)
class ForceFaiblesseViewSet(AnalyseViewSet, ModelViewSet[ForceFaiblesse]):
    serializer_class = serializers.ForceFaiblesseSerializer
    queryset = ForceFaiblesse.objects.none()
    filterset_class = filters.ForceFaiblesseFilter
    ordering_fields = ("ordre",)
    ordering = ("ordre",)
    audite_actions = LECTURE

    def get_queryset(self) -> QuerySet[ForceFaiblesse]:
        return ForceFaiblesse.objects.filter(
            mission__in=acces.missions_visibles(self.acteur)
        ).select_related("processus", "mission")

    def perform_create(self, serializer: BaseSerializer[ForceFaiblesse]) -> None:
        donnees = dict(serializer.validated_data)
        ff = svc_ff.ajouter_force_faiblesse(
            donnees.pop("mission"),
            type=donnees.pop("type"),
            libelle=donnees.pop("libelle"),
            by=self.acteur,
            **donnees,
        )
        self._publier(serializer, ff)

    def perform_update(self, serializer: BaseSerializer[ForceFaiblesse]) -> None:
        instance = self._cible(serializer)
        changements = self.retirer_immuables(serializer.validated_data, instance, ("mission",))
        ff = svc_ff.modifier_force_faiblesse(instance, by=self.acteur, **changements)
        self._publier(serializer, ff)

    def perform_destroy(self, instance: ForceFaiblesse) -> None:
        svc_ff.retirer_force_faiblesse(instance, by=self.acteur)


@extend_schema(tags=[TAG_REFERENTIEL])
class ReferentielAuditViewSet(MissionApiViewSet):
    """Synthèse du référentiel d'audit d'une mission, instantané validé et avis des audités."""

    permission_classes = [AnalyseAccessPermission]
    serializer_class = serializers.ReferentielAuditSerializer
    queryset = Mission.objects.none()
    pagination_class = None
    filter_backends: list[Any] = []
    http_method_names = ["get", "post", "head", "options"]
    audite_actions = frozenset({"retrieve", "opinions", "snapshot"})

    def get_queryset(self) -> QuerySet[Mission]:
        return acces.missions_visibles(self.acteur)

    @extend_schema(
        summary="Synthèse du référentiel d'audit",
        responses={200: serializers.ReferentielAuditSerializer, **ERROR_RESPONSES, **ERROR_404},
    )
    def retrieve(self, request: Request, pk: str | None = None) -> Response:
        mission: Mission = self.get_object()
        droits = droits_analyse(self.acteur, mission)
        if self.acteur.role == Role.AUDITE and not droits.voir_referentiel:
            donnees: dict[str, Any] = {
                "mission": mission.pk,
                "statut": StatutReferentiel.BROUILLON,
                "statut_v": "A_FAIRE",
                "statut_vi": "A_FAIRE",
                "nb_lignes": 0,
                "nb_forces": 0,
                "nb_faiblesses": 0,
                "risques_non_couverts": [],
                "validation": None,
                "validation_verifiee": False,
                "avis": [],
                "mes_droits": droits,
            }
        else:
            synthese = svc_referentiel.synthese_referentiel(mission)
            donnees = {
                "mission": mission.pk,
                "statut": synthese.statut,
                "statut_v": synthese.statut_v,
                "statut_vi": synthese.statut_vi,
                "nb_lignes": synthese.nb_lignes,
                "nb_forces": synthese.nb_forces,
                "nb_faiblesses": synthese.nb_faiblesses,
                "risques_non_couverts": synthese.risques_non_couverts,
                "validation": synthese.validation,
                "validation_verifiee": bool(synthese.validation and verifier(synthese.validation)),
                "avis": synthese.avis,
                "mes_droits": droits,
            }
        return Response(serializers.ReferentielAuditSerializer(donnees).data)

    @extend_schema(
        summary="Donner son avis sur le référentiel (audité affecté)",
        request=serializers.AvisRequestSerializer,
        responses={
            201: serializers.AvisAuditeSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
    )
    @action(detail=True, methods=["post"])
    def opinions(self, request: Request, pk: str | None = None) -> Response:
        mission: Mission = self.get_object()
        exiger(self.acteur.role == Role.AUDITE)
        corps = serializers.AvisRequestSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        avis = svc_referentiel.deposer_avis(
            mission,
            avis=corps.validated_data["avis"],
            commentaire=corps.validated_data["commentaire"],
            by=self.acteur,
        )
        return Response(serializers.AvisAuditeSerializer(avis).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Instantané du référentiel validé",
        responses={
            200: serializers.InstantaneReferentielSerializer,
            **ERROR_RESPONSES,
            **ERROR_404,
        },
    )
    @action(detail=True, methods=["get"])
    def snapshot(self, request: Request, pk: str | None = None) -> Response:
        mission: Mission = self.get_object()
        exiger_referentiel_visible(self.acteur, mission)
        confirmation = svc_referentiel.referentiel_valide(mission)
        if confirmation is None:
            raise NotFound("Le référentiel d'audit n'a pas encore été validé.")
        return Response(
            serializers.InstantaneReferentielSerializer(
                {"confirmation": confirmation, "donnees": confirmation.donnees}
            ).data
        )


# --------------------------------------------------------------------------- étape VII


@crud_schema(
    serializers.ObjectifAuditSerializer, TAG_OBJECTIFS, "objectifs d'audit", creation_404=True
)
class ObjectifAuditViewSet(AnalyseViewSet, ModelViewSet[ObjectifAudit]):
    serializer_class = serializers.ObjectifAuditSerializer
    queryset = ObjectifAudit.objects.none()
    filterset_class = filters.ObjectifFilter
    ordering_fields = ("numero",)
    ordering = ("numero",)

    def get_queryset(self) -> QuerySet[ObjectifAudit]:
        return ObjectifAudit.objects.filter(
            mission__in=acces.missions_visibles(self.acteur)
        ).select_related("ligne_marc", "ligne_marc__risque", "mission")

    def perform_create(self, serializer: BaseSerializer[ObjectifAudit]) -> None:
        donnees = dict(serializer.validated_data)
        objectif = svc_objectifs.ajouter_objectif(
            donnees.pop("mission"),
            ligne_marc=donnees.pop("ligne_marc"),
            libelle=donnees.pop("libelle", ""),
            by=self.acteur,
        )
        if donnees:
            objectif = svc_objectifs.modifier_objectif(objectif, by=self.acteur, **donnees)
        self._publier(serializer, objectif)

    def perform_update(self, serializer: BaseSerializer[ObjectifAudit]) -> None:
        instance = self._cible(serializer)
        changements = self.retirer_immuables(
            serializer.validated_data, instance, ("mission", "ligne_marc")
        )
        objectif = svc_objectifs.modifier_objectif(instance, by=self.acteur, **changements)
        self._publier(serializer, objectif)

    def perform_destroy(self, instance: ObjectifAudit) -> None:
        svc_objectifs.retirer_objectif(instance, by=self.acteur)

    @_action_schema(
        "Initialiser les objectifs d'audit (un par contrôle clé)",
        serializers.ObjectifAuditSerializer(many=True),
        request=serializers.MissionRequestSerializer,
        tag=TAG_OBJECTIFS,
    )
    @action(detail=False, methods=["post"], pagination_class=None, filter_backends=[])
    def initialize(self, request: Request) -> Response:
        self.creer_pour_mission(request)
        corps = serializers.MissionRequestSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        creees = svc_objectifs.initialiser_objectifs(
            corps.validated_data["mission"], by=self.acteur
        )
        objectifs = self.get_queryset().filter(pk__in=[o.pk for o in creees])
        return self.reponse_liste(corps.validated_data["mission"], objectifs.order_by("numero"))


@extend_schema(tags=[TAG_OBJECTIFS])
class RapportOrientationViewSet(MissionApiViewSet):
    """Rapport d'orientation d'une mission (un par mission ; vide tant qu'il n'est pas saisi)."""

    permission_classes = [AnalyseAccessPermission]
    serializer_class = serializers.RapportOrientationSerializer
    queryset = Mission.objects.none()
    pagination_class = None
    filter_backends: list[Any] = []
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self) -> QuerySet[Mission]:
        return acces.missions_visibles(self.acteur)

    @extend_schema(
        summary="Détail : rapport d'orientation",
        responses={200: serializers.RapportOrientationSerializer, **ERROR_RESPONSES, **ERROR_404},
    )
    def retrieve(self, request: Request, pk: str | None = None) -> Response:
        mission: Mission = self.get_object()
        rapport = svc_orientation.obtenir_rapport(mission) or RapportOrientation(mission=mission)
        return Response(self.get_serializer(rapport).data)

    @extend_schema(
        summary="Modifier : rapport d'orientation",
        responses={
            200: serializers.RapportOrientationSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
    )
    def partial_update(self, request: Request, pk: str | None = None) -> Response:
        mission: Mission = self.get_object()
        exiger_contribution(self.acteur, mission)
        existant = svc_orientation.obtenir_rapport(mission) or RapportOrientation(mission=mission)
        serializer = self.get_serializer(existant, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        rapport = svc_orientation.enregistrer_rapport(
            mission, by=self.acteur, **serializer.validated_data
        )
        rapport.mission = mission
        return Response(self.get_serializer(rapport).data)
