import django_filters
from django.db.models import Q, QuerySet

from apps.referentiel.models import NiveauRisque

from .models import (
    AffectationMission,
    DeclarationIndependance,
    Entretien,
    EtapeMission,
    Mission,
    Reunion,
    RisqueMission,
    RoleMission,
    StatutDeclaration,
    StatutEntretien,
    StatutMission,
    TypeMission,
    TypeReunion,
)


class MissionFilter(django_filters.FilterSet):
    statut = django_filters.ChoiceFilter(choices=StatutMission.choices)
    type = django_filters.ChoiceFilter(choices=TypeMission.choices)
    annee = django_filters.NumberFilter(field_name="annee")
    processus = django_filters.UUIDFilter(field_name="processus__id", distinct=True)
    q = django_filters.CharFilter(
        method="filter_q", help_text="Recherche insensible à la casse sur la référence et le titre."
    )

    class Meta:
        model = Mission
        fields: list[str] = []

    def filter_q(self, queryset: QuerySet[Mission], name: str, value: str) -> QuerySet[Mission]:
        return queryset.filter(Q(reference__icontains=value) | Q(titre__icontains=value))


class AffectationFilter(django_filters.FilterSet):
    mission = django_filters.UUIDFilter(field_name="mission_id")
    role_mission = django_filters.ChoiceFilter(choices=RoleMission.choices)

    class Meta:
        model = AffectationMission
        fields: list[str] = []


class DeclarationFilter(django_filters.FilterSet):
    mission = django_filters.UUIDFilter(field_name="affectation__mission_id")
    statut = django_filters.ChoiceFilter(choices=StatutDeclaration.choices)
    mine = django_filters.BooleanFilter(
        method="filter_mine", help_text="Vrai : seulement mes déclarations."
    )

    class Meta:
        model = DeclarationIndependance
        fields: list[str] = []

    def filter_mine(
        self, queryset: QuerySet[DeclarationIndependance], name: str, value: bool
    ) -> QuerySet[DeclarationIndependance]:
        if not value:
            return queryset
        return queryset.filter(affectation__utilisateur=self.request.user)


class ReunionFilter(django_filters.FilterSet):
    mission = django_filters.UUIDFilter(field_name="mission_id")
    type = django_filters.ChoiceFilter(choices=TypeReunion.choices)

    class Meta:
        model = Reunion
        fields: list[str] = []


class EntretienFilter(django_filters.FilterSet):
    mission = django_filters.UUIDFilter(field_name="mission_id")
    etape = django_filters.UUIDFilter(field_name="etape_id")
    statut = django_filters.ChoiceFilter(choices=StatutEntretien.choices)

    class Meta:
        model = Entretien
        fields: list[str] = []


class RisqueMissionFilter(django_filters.FilterSet):
    mission = django_filters.UUIDFilter(field_name="mission_id")
    nouveau = django_filters.BooleanFilter(
        method="filter_nouveau", help_text="Vrai : risques créés dans la mission."
    )
    niveau = django_filters.ChoiceFilter(choices=NiveauRisque.choices)
    processus = django_filters.UUIDFilter(field_name="processus_id")

    class Meta:
        model = RisqueMission
        fields: list[str] = []

    def filter_nouveau(
        self, queryset: QuerySet[RisqueMission], name: str, value: bool
    ) -> QuerySet[RisqueMission]:
        return queryset.filter(risque_source__isnull=value)


class EtapeFilter(django_filters.FilterSet):
    mission = django_filters.UUIDFilter(
        field_name="mission_id", help_text="Obligatoire pour la liste."
    )

    class Meta:
        model = EtapeMission
        fields: list[str] = []
