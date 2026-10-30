from typing import Any

import django_filters
from django.db.models import Q, QuerySet
from django_filters import rest_framework as rf_filters

from .models import (
    ConclusionTest,
    FicheDeTest,
    NatureTest,
    PieceJustificative,
    ProgrammeDeTravail,
    StatutFiche,
    StatutTest,
    TestPrevu,
)

_MISSION_AIDE = "Obligatoire pour la liste."


class ProgrammeFilter(django_filters.FilterSet):
    mission = django_filters.UUIDFilter(field_name="mission_id", help_text=_MISSION_AIDE)
    objectif = django_filters.UUIDFilter(field_name="objectif_id")

    class Meta:
        model = ProgrammeDeTravail
        fields: list[str] = []


class TestPrevuFilter(django_filters.FilterSet):
    __test__ = False

    mission = django_filters.UUIDFilter(field_name="mission_id", help_text=_MISSION_AIDE)
    programme = django_filters.UUIDFilter(field_name="programme_id")
    auditeur = django_filters.NumberFilter(field_name="auditeur_id")
    nature = django_filters.ChoiceFilter(choices=NatureTest.choices)
    statut = django_filters.ChoiceFilter(choices=StatutTest.choices)
    complementaire = rf_filters.BooleanFilter()
    mine = rf_filters.BooleanFilter(
        method="filtrer_mine", help_text="Vrai : seulement les tests de l'utilisateur."
    )

    class Meta:
        model = TestPrevu
        fields: list[str] = []

    def filtrer_mine(self, queryset: QuerySet[Any], name: str, value: bool) -> QuerySet[Any]:
        if value is None:
            return queryset
        condition = Q(auditeur=self.request.user)
        return queryset.filter(condition) if value else queryset.exclude(condition)


class FicheFilter(django_filters.FilterSet):
    mission = django_filters.UUIDFilter(field_name="mission_id", help_text=_MISSION_AIDE)
    statut = django_filters.ChoiceFilter(choices=StatutFiche.choices)
    conclusion = django_filters.ChoiceFilter(choices=ConclusionTest.choices)
    auteur = django_filters.NumberFilter(field_name="auteur_id")
    mine = rf_filters.BooleanFilter(
        method="filtrer_mine",
        help_text="Vrai : fiches dont l'utilisateur est l'auteur ou l'auditeur du test.",
    )
    a_valider = rf_filters.BooleanFilter(
        method="filtrer_a_valider", help_text="Vrai : fiches soumises, en attente de validation."
    )

    class Meta:
        model = FicheDeTest
        fields: list[str] = []

    def filtrer_mine(self, queryset: QuerySet[Any], name: str, value: bool) -> QuerySet[Any]:
        if value is None:
            return queryset
        condition = Q(auteur=self.request.user) | Q(test__auditeur=self.request.user)
        return queryset.filter(condition) if value else queryset.exclude(condition)

    def filtrer_a_valider(self, queryset: QuerySet[Any], name: str, value: bool) -> QuerySet[Any]:
        if value is None:
            return queryset
        condition = Q(statut=StatutFiche.SOUMIS)
        return queryset.filter(condition) if value else queryset.exclude(condition)


class PieceFilter(django_filters.FilterSet):
    fiche = django_filters.UUIDFilter(field_name="fiche_id", help_text="Fiche ou mission requise.")
    mission = django_filters.UUIDFilter(
        field_name="mission_id", help_text="Mission ou fiche requise."
    )

    class Meta:
        model = PieceJustificative
        fields: list[str] = []
