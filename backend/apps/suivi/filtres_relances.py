"""Filtres du journal des relances."""

import django_filters

from apps.core.filters import IsoDateFilter

from .models import PalierRelance, Relance, StatutRelance


class RelanceFilter(django_filters.FilterSet):
    statut = django_filters.ChoiceFilter(choices=StatutRelance.choices)
    palier = django_filters.ChoiceFilter(choices=PalierRelance.choices)
    mission = django_filters.UUIDFilter(field_name="suivi__mission_id")
    date_apres = IsoDateFilter(field_name="created_at", lookup_expr="date__gte")

    class Meta:
        model = Relance
        fields: list[str] = []
