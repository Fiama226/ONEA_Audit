from typing import Any

import django_filters
from django.db.models import Exists, OuterRef, Q, QuerySet
from django_filters import rest_framework as rf_filters

from apps.referentiel.models import NiveauRisque

from .models import Constat, PrioriteRecommandation, Recommandation, ReponseAudite, StatutConstat
from .permissions import REPONDABLES

_MISSION_AIDE = "Obligatoire pour la liste."


class ConstatFilter(django_filters.FilterSet):
    mission = django_filters.UUIDFilter(field_name="mission_id", help_text=_MISSION_AIDE)
    statut = django_filters.ChoiceFilter(choices=StatutConstat.choices)
    niveau = django_filters.ChoiceFilter(choices=NiveauRisque.choices)
    entite = django_filters.UUIDFilter(field_name="entite_id")
    a_repondre = rf_filters.BooleanFilter(
        method="filtrer_a_repondre",
        help_text="Vrai : constats soumis ou validés sans réponse de l'audité au cycle courant.",
    )

    class Meta:
        model = Constat
        fields: list[str] = []

    def filtrer_a_repondre(self, queryset: QuerySet[Any], name: str, value: bool) -> QuerySet[Any]:
        if value is None:
            return queryset
        condition = Q(statut__in=REPONDABLES) & ~Exists(
            ReponseAudite.objects.filter(constat=OuterRef("pk"), cycle=OuterRef("cycle"))
        )
        return queryset.filter(condition) if value else queryset.exclude(condition)


class ReponseFilter(django_filters.FilterSet):
    constat = django_filters.UUIDFilter(
        field_name="constat_id", help_text="Constat ou mission requis."
    )
    mission = django_filters.UUIDFilter(
        field_name="mission_id", help_text="Mission ou constat requis."
    )

    class Meta:
        model = ReponseAudite
        fields: list[str] = []


class RecommandationFilter(django_filters.FilterSet):
    constat = django_filters.UUIDFilter(
        field_name="constat_id", help_text="Constat ou mission requis."
    )
    mission = django_filters.UUIDFilter(
        field_name="mission_id", help_text="Mission ou constat requis."
    )
    priorite = django_filters.ChoiceFilter(choices=PrioriteRecommandation.choices)

    class Meta:
        model = Recommandation
        fields: list[str] = []
