import datetime as dt
import re
from typing import Any

import django_filters
from auditlog.models import LogEntry
from django import forms
from django.apps import apps
from django.db.models import Q, QuerySet
from django.utils import timezone
from rest_framework.filters import OrderingFilter
from rest_framework.request import Request
from rest_framework.views import APIView


class StableOrderingFilter(OrderingFilter):
    """`ordering` parameter with the primary key as final tie-breaker (stable pagination)."""

    def filter_queryset(
        self, request: Request, queryset: QuerySet[Any], view: APIView
    ) -> QuerySet[Any]:
        ordered = super().filter_queryset(request, queryset, view)
        return ordered.order_by(*ordered.query.order_by, "pk")


ACTIONS = {
    "create": LogEntry.Action.CREATE,
    "update": LogEntry.Action.UPDATE,
    "delete": LogEntry.Action.DELETE,
}


class ModelLabelField(forms.CharField):
    """Accepts `app_label.model` and rejects unknown models."""

    def clean(self, value: Any) -> Any:
        value = super().clean(value)
        if not value:
            return value
        try:
            model = apps.get_model(value)
        except (LookupError, ValueError) as exc:
            raise forms.ValidationError("Modèle inconnu : attendu app_label.model.") from exc
        return f"{model._meta.app_label}.{model._meta.model_name}"


class ModelLabelFilter(django_filters.CharFilter):
    field_class = ModelLabelField


ISO_DATE = ["%Y-%m-%d"]
# Catégories du journal visible (filtre `categorie`) : modèles (app_label, model) concernés.
CATEGORIES: dict[str, tuple[tuple[str, str], ...]] = {
    "gouvernance": (("gouvernance", "reglegouvernance"),),
}


def filtre_categorie(queryset: QuerySet[LogEntry], categorie: str) -> QuerySet[LogEntry]:
    condition = Q()
    for app_label, model in CATEGORIES[categorie]:
        condition |= Q(content_type__app_label=app_label, content_type__model=model)
    return queryset.filter(condition)


UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$")
MAX_ACTOR_ID = 2**31 - 1


class IntegerFilter(django_filters.Filter):
    field_class = forms.IntegerField


def _start_of_day(value: dt.date) -> dt.datetime:
    return timezone.make_aware(dt.datetime.combine(value, dt.time.min))


class BoundedDateField(forms.DateField):
    """ISO date within a range where day arithmetic and tz conversion cannot overflow."""

    def clean(self, value: Any) -> Any:
        parsed = super().clean(value)
        if parsed is not None and not (dt.date(1900, 1, 1) <= parsed <= dt.date(9998, 12, 31)):
            raise forms.ValidationError("Date hors limites (1900-01-01 à 9998-12-31).")
        return parsed


class IsoDateFilter(django_filters.DateFilter):
    field_class = BoundedDateField


class AuditLogFilter(django_filters.FilterSet):
    model = ModelLabelFilter(method="filter_model", help_text="app_label.model, e.g. users.user")
    object_id = django_filters.CharFilter(
        method="filter_object_id",
        help_text="Primary key of the audited object (UUIDs case-insensitive)",
    )
    actor = IntegerFilter(
        field_name="actor_id",
        min_value=1,
        max_value=MAX_ACTOR_ID,
        help_text="Id of the user who made the change",
    )
    categorie = django_filters.ChoiceFilter(
        choices=[(name, name) for name in CATEGORIES],
        method="filter_categorie",
        help_text="gouvernance : changements des règles de gouvernance",
    )
    action = django_filters.ChoiceFilter(
        choices=[(name, name) for name in ACTIONS],
        method="filter_action",
        help_text="create, update or delete",
    )
    date_from = IsoDateFilter(
        method="filter_date_from", input_formats=ISO_DATE, help_text="ISO date YYYY-MM-DD"
    )
    date_to = IsoDateFilter(
        method="filter_date_to",
        input_formats=ISO_DATE,
        help_text="ISO date YYYY-MM-DD, inclusive of the whole day (Africa/Ouagadougou)",
    )

    class Meta:
        model = LogEntry
        fields: list[str] = []

    def filter_model(
        self, queryset: QuerySet[LogEntry], name: str, value: str
    ) -> QuerySet[LogEntry]:
        app_label, model_name = value.split(".", 1)
        return queryset.filter(content_type__app_label=app_label, content_type__model=model_name)

    def filter_object_id(
        self, queryset: QuerySet[LogEntry], name: str, value: str
    ) -> QuerySet[LogEntry]:
        return queryset.filter(object_pk=value.lower() if UUID_RE.match(value) else value)

    def filter_categorie(
        self, queryset: QuerySet[LogEntry], name: str, value: str
    ) -> QuerySet[LogEntry]:
        return filtre_categorie(queryset, value)

    def filter_action(
        self, queryset: QuerySet[LogEntry], name: str, value: str
    ) -> QuerySet[LogEntry]:
        return queryset.filter(action=ACTIONS[value])

    def filter_date_from(
        self, queryset: QuerySet[LogEntry], name: str, value: dt.date
    ) -> QuerySet[LogEntry]:
        start = _start_of_day(value)
        return queryset.filter(timestamp__gte=start)

    def filter_date_to(
        self, queryset: QuerySet[LogEntry], name: str, value: dt.date
    ) -> QuerySet[LogEntry]:
        end = _start_of_day(value + dt.timedelta(days=1))
        return queryset.filter(timestamp__lt=end)
