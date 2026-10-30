"""Journal des relances (lecture seule, RAI) : aucune logique métier."""

from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, serializers
from rest_framework.viewsets import GenericViewSet

from apps.core.filters import StableOrderingFilter
from apps.core.schema import ERROR_400, ERROR_RESPONSES
from apps.users.permissions import IsRAI
from apps.users.serializers import UtilisateurResumeSerializer

from .filtres_relances import RelanceFilter
from .models import PalierRelance, Relance, StatutRelance

TAG = "Relances"


class RelanceSerializer(serializers.ModelSerializer[Relance]):
    mission_id = serializers.UUIDField(source="suivi.mission_id", read_only=True)
    mission_reference = serializers.CharField(source="suivi.mission.reference", read_only=True)
    action_libelle = serializers.CharField(source="suivi.action.libelle", read_only=True)
    palier = serializers.ChoiceField(choices=PalierRelance.choices, read_only=True)
    statut = serializers.ChoiceField(choices=StatutRelance.choices, read_only=True)
    destinataire = UtilisateurResumeSerializer(read_only=True)
    copie = UtilisateurResumeSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Relance
        fields = (
            "id",
            "suivi",
            "mission_id",
            "mission_reference",
            "action_libelle",
            "palier",
            "echeance_reference",
            "destinataire",
            "copie",
            "statut",
            "tentatives",
            "envoyee_le",
            "erreur",
            "created_at",
        )
        read_only_fields = fields


@extend_schema_view(
    list=extend_schema(
        tags=[TAG],
        summary="Journal des relances",
        responses={200: RelanceSerializer(many=True), **ERROR_400, **ERROR_RESPONSES},
    ),
)
class RelanceViewSet(mixins.ListModelMixin, GenericViewSet[Relance]):
    permission_classes = [IsRAI]
    serializer_class = RelanceSerializer
    filter_backends = [DjangoFilterBackend, StableOrderingFilter]
    filterset_class = RelanceFilter
    ordering_fields = ("created_at", "echeance_reference")
    ordering = ("-created_at",)

    def get_queryset(self) -> QuerySet[Relance]:
        return Relance.objects.select_related(
            "suivi__mission", "suivi__action", "destinataire", "copie"
        )
