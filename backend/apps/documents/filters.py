import django_filters
from django.db.models import QuerySet

from .models import Document, GabaritDocument, StatutGabarit


class GabaritFilter(django_filters.FilterSet):
    type_document = django_filters.CharFilter(field_name="type_document")
    statut = django_filters.ChoiceFilter(choices=StatutGabarit.choices)

    class Meta:
        model = GabaritDocument
        fields: list[str] = []


class DocumentFilter(django_filters.FilterSet):
    mission = django_filters.UUIDFilter(field_name="mission_id")
    type_document = django_filters.CharFilter(field_name="type_document")
    q = django_filters.CharFilter(
        method="filter_q", help_text="Recherche insensible à la casse sur le numéro."
    )

    class Meta:
        model = Document
        fields: list[str] = []

    def filter_q(self, queryset: QuerySet[Document], name: str, value: str) -> QuerySet[Document]:
        return queryset.filter(numero__icontains=value)
