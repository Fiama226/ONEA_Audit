from typing import Any

import django_filters
from django.db.models import QuerySet
from django_filters import rest_framework as rf_filters

from apps.constats.models import PrioriteRecommandation, Recommandation
from apps.core.filters import IsoDateFilter

from .models import (
    DemandeReport,
    PreuveMiseEnOeuvre,
    StatutDemandeReport,
    StatutRecommandationSuivi,
    StatutSuivi,
    SuiviAction,
)
from .services.commun import EXPR_EN_RETARD, aujourd_hui

_ISO = ["%Y-%m-%d"]


class SuiviActionFilter(django_filters.FilterSet):
    mission = django_filters.UUIDFilter(field_name="mission_id")
    recommandation = django_filters.UUIDFilter(field_name="recommandation_id")
    entite = django_filters.UUIDFilter(field_name="entite_id")
    responsable = django_filters.NumberFilter(field_name="responsable_id")
    statut = django_filters.MultipleChoiceFilter(
        choices=StatutSuivi.choices, help_text="Un ou plusieurs statuts de suivi."
    )
    en_retard = rf_filters.BooleanFilter(
        method="filtrer_en_retard", help_text="Vrai : relançable et échéance dépassée."
    )
    mine = rf_filters.BooleanFilter(
        method="filtrer_mine", help_text="Vrai : seulement les actions dont je suis responsable."
    )
    echeance_avant = IsoDateFilter(
        field_name="echeance", lookup_expr="lte", input_formats=_ISO, help_text="AAAA-MM-JJ"
    )
    echeance_apres = IsoDateFilter(
        field_name="echeance", lookup_expr="gte", input_formats=_ISO, help_text="AAAA-MM-JJ"
    )
    annee = django_filters.NumberFilter(
        field_name="mission__annee",
        min_value=2000,
        max_value=2100,
        help_text="Année de la mission.",
    )

    class Meta:
        model = SuiviAction
        fields: list[str] = []

    def filtrer_en_retard(self, queryset: QuerySet[Any], name: str, value: bool) -> QuerySet[Any]:
        if value is None:
            return queryset
        critere = EXPR_EN_RETARD(aujourd_hui())
        return queryset.filter(critere) if value else queryset.exclude(critere)

    def filtrer_mine(self, queryset: QuerySet[Any], name: str, value: bool) -> QuerySet[Any]:
        if value is None:
            return queryset
        utilisateur = self.request.user
        return (
            queryset.filter(responsable=utilisateur)
            if value
            else queryset.exclude(responsable=utilisateur)
        )


class RecommandationSuiviFilter(django_filters.FilterSet):
    mission = django_filters.UUIDFilter(field_name="mission_id")
    entite = django_filters.UUIDFilter(field_name="constat__entite_id")
    priorite = django_filters.ChoiceFilter(choices=PrioriteRecommandation.choices)
    statut_suivi = django_filters.MultipleChoiceFilter(
        choices=StatutRecommandationSuivi.choices, help_text="Statut dérivé (un ou plusieurs)."
    )
    annee = django_filters.NumberFilter(
        field_name="mission__annee",
        min_value=2000,
        max_value=2100,
        help_text="Année de la mission.",
    )
    en_retard = rf_filters.BooleanFilter(
        method="filtrer_en_retard", help_text="Vrai : au moins une action en retard."
    )

    class Meta:
        model = Recommandation
        fields: list[str] = []

    def filtrer_en_retard(self, queryset: QuerySet[Any], name: str, value: bool) -> QuerySet[Any]:
        if value is None:
            return queryset
        return (
            queryset.filter(actions_en_retard__gt=0)
            if value
            else queryset.filter(actions_en_retard=0)
        )


class PreuveFilter(django_filters.FilterSet):
    action = django_filters.UUIDFilter(field_name="suivi_id", help_text="Obligatoire.")

    class Meta:
        model = PreuveMiseEnOeuvre
        fields: list[str] = []


class DemandeReportFilter(django_filters.FilterSet):
    action = django_filters.UUIDFilter(field_name="suivi_id")
    statut = django_filters.ChoiceFilter(choices=StatutDemandeReport.choices)
    mission = django_filters.UUIDFilter(field_name="mission_id")

    class Meta:
        model = DemandeReport
        fields: list[str] = []
