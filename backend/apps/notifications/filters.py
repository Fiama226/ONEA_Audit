import django_filters

from .models import Notification


class NotificationFilter(django_filters.FilterSet):
    non_lues = django_filters.BooleanFilter(
        method="filtrer_non_lues", help_text="Vrai : seulement les notifications non lues."
    )

    class Meta:
        model = Notification
        fields: list[str] = []

    def filtrer_non_lues(self, queryset, name, value):  # type: ignore[no-untyped-def]
        return queryset.filter(lue_le__isnull=True) if value else queryset
