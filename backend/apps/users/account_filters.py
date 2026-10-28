from typing import Any

import django_filters
from django import forms
from django.db.models import Q, QuerySet

from .models import KeycloakSyncStatut, OrigineCompte, Role, User

Q_AIDE = (
    "Recherche insensible à la casse sur l'identifiant, le prénom, le nom, l'e-mail "
    "et le matricule."
)
_TRUE = {"true", "1"}
_FALSE = {"false", "0"}


class StrictBooleanField(forms.Field):
    """`true` / `false` (or 1 / 0) only; anything else is a 400, never silently ignored."""

    def to_python(self, value: Any) -> bool | None:
        if value in (None, ""):
            return None
        text = str(value).strip().lower()
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
        raise forms.ValidationError("Valeur booléenne attendue : true ou false.")


class StrictBooleanFilter(django_filters.BooleanFilter):
    field_class = StrictBooleanField


class UserAccountFilter(django_filters.FilterSet):
    role = django_filters.ChoiceFilter(choices=Role.choices)
    is_active = StrictBooleanFilter()
    direction_code = django_filters.CharFilter()
    origine = django_filters.ChoiceFilter(choices=OrigineCompte.choices)
    en_attente_connexion = StrictBooleanFilter(
        method="filter_en_attente", help_text="Compte qui ne s'est jamais connecté."
    )
    keycloak_sync = django_filters.ChoiceFilter(
        field_name="keycloak_sync_statut", choices=KeycloakSyncStatut.choices
    )
    q = django_filters.CharFilter(method="filter_q", help_text=Q_AIDE)

    class Meta:
        model = User
        fields: list[str] = []

    def filter_en_attente(self, queryset: QuerySet[User], name: str, value: bool) -> QuerySet[User]:
        return queryset.filter(premiere_connexion_le__isnull=value)

    def filter_q(self, queryset: QuerySet[User], name: str, value: str) -> QuerySet[User]:
        condition = Q()
        for champ in ("username", "first_name", "last_name", "email", "matricule"):
            condition |= Q(**{f"{champ}__icontains": value})
        return queryset.filter(condition)
