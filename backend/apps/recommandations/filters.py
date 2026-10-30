from typing import Any

import django_filters
from django.db.models import QuerySet
from django_filters import rest_framework as rf_filters

from .models import AcceptationRisque, Action, EngagementPlanActions

_MISSION_AIDE = "Obligatoire pour la liste."


class ActionFilter(django_filters.FilterSet):
    mission = django_filters.UUIDFilter(field_name="mission_id", help_text=_MISSION_AIDE)
    recommandation = django_filters.UUIDFilter(field_name="recommandation_id")
    constat = django_filters.UUIDFilter(field_name="recommandation__constat_id")
    responsable = django_filters.NumberFilter(field_name="responsable_id")
    mine = rf_filters.BooleanFilter(
        method="filtrer_mine", help_text="Vrai : seulement les actions dont je suis responsable."
    )

    class Meta:
        model = Action
        fields: list[str] = []

    def filtrer_mine(self, queryset: QuerySet[Any], name: str, value: bool) -> QuerySet[Any]:
        if value is None:
            return queryset
        utilisateur = self.request.user
        return (
            queryset.filter(responsable=utilisateur)
            if value
            else queryset.exclude(responsable=utilisateur)
        )


class AcceptationFilter(django_filters.FilterSet):
    mission = django_filters.UUIDFilter(
        field_name="mission_id", help_text="Mission ou recommandation requise."
    )
    recommandation = django_filters.UUIDFilter(
        field_name="recommandation_id", help_text="Recommandation ou mission requise."
    )

    class Meta:
        model = AcceptationRisque
        fields: list[str] = []


class EngagementFilter(django_filters.FilterSet):
    mission = django_filters.UUIDFilter(field_name="mission_id", help_text=_MISSION_AIDE)

    class Meta:
        model = EngagementPlanActions
        fields: list[str] = []
