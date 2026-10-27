import datetime as dt
from typing import Any

import django_filters
from auditlog.models import LogEntry
from django import forms
from django.apps import apps
from django.db.models import QuerySet
from django.utils import timezone

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


def _start_of_day(value: dt.date) -> dt.datetime:
    return timezone.make_aware(dt.datetime.combine(value, dt.time.min))


class AuditLogFilter(django_filters.FilterSet):
    model = ModelLabelFilter(method="filter_model", help_text="app_label.model, e.g. users.user")
    object_id = django_filters.CharFilter(field_name="object_pk")
    actor = django_filters.NumberFilter(field_name="actor_id")
    action = django_filters.ChoiceFilter(
        choices=[(name, name) for name in ACTIONS], method="filter_action"
    )
    date_from = django_filters.DateFilter(method="filter_date_from", help_text="ISO date")
    date_to = django_filters.DateFilter(
        method="filter_date_to", help_text="ISO date, inclusive of the whole day"
    )

    class Meta:
        model = LogEntry
        fields: list[str] = []

    def filter_model(
        self, queryset: QuerySet[LogEntry], name: str, value: str
    ) -> QuerySet[LogEntry]:
        app_label, model_name = value.split(".", 1)
        return queryset.filter(content_type__app_label=app_label, content_type__model=model_name)

    def filter_action(
        self, queryset: QuerySet[LogEntry], name: str, value: str
    ) -> QuerySet[LogEntry]:
        return queryset.filter(action=ACTIONS[value])

    def filter_date_from(
        self, queryset: QuerySet[LogEntry], name: str, value: dt.date
    ) -> QuerySet[LogEntry]:
        return queryset.filter(timestamp__gte=_start_of_day(value))

    def filter_date_to(
        self, queryset: QuerySet[LogEntry], name: str, value: dt.date
    ) -> QuerySet[LogEntry]:
        return queryset.filter(timestamp__lt=_start_of_day(value + dt.timedelta(days=1)))
