import django_filters
from django.db.models import Model, Q, QuerySet

from .models import (
    CartographieVersion,
    Direction,
    FamilleProcessus,
    NatureObjet,
    NiveauRisque,
    ObjetAuditable,
    PrioriteRisque,
    Processus,
    ReponseRisque,
    Risque,
    StatutCartographie,
    TypeEntite,
)

Q_AIDE = "Recherche insensible à la casse (sensible aux accents) sur le code et le libellé."


def _recherche[T: Model](queryset: QuerySet[T], value: str, *champs: str) -> QuerySet[T]:
    condition = Q()
    for champ in champs:
        condition |= Q(**{f"{champ}__icontains": value})
    return queryset.filter(condition)


class DirectionFilter(django_filters.FilterSet):
    type = django_filters.ChoiceFilter(choices=TypeEntite.choices)
    parent = django_filters.UUIDFilter(field_name="parent_id")
    q = django_filters.CharFilter(method="filter_q", help_text=Q_AIDE)

    class Meta:
        model = Direction
        fields: list[str] = []

    def filter_q(self, queryset: QuerySet[Direction], name: str, value: str) -> QuerySet[Direction]:
        return _recherche(queryset, value, "code", "libelle")


class ProcessusFilter(django_filters.FilterSet):
    famille = django_filters.ChoiceFilter(choices=FamilleProcessus.choices)
    direction = django_filters.UUIDFilter(field_name="directions__id")
    q = django_filters.CharFilter(method="filter_q", help_text=Q_AIDE)

    class Meta:
        model = Processus
        fields: list[str] = []

    def filter_q(self, queryset: QuerySet[Processus], name: str, value: str) -> QuerySet[Processus]:
        return _recherche(queryset, value, "code", "libelle")


class ObjetAuditableFilter(django_filters.FilterSet):
    processus = django_filters.UUIDFilter(field_name="processus_id")
    parent = django_filters.UUIDFilter(field_name="parent_id")
    nature = django_filters.ChoiceFilter(choices=NatureObjet.choices)
    q = django_filters.CharFilter(
        method="filter_q", help_text="Recherche insensible à la casse sur le libellé."
    )

    class Meta:
        model = ObjetAuditable
        fields: list[str] = []

    def filter_q(
        self, queryset: QuerySet[ObjetAuditable], name: str, value: str
    ) -> QuerySet[ObjetAuditable]:
        return _recherche(queryset, value, "libelle")


class CartographieFilter(django_filters.FilterSet):
    statut = django_filters.ChoiceFilter(choices=StatutCartographie.choices)
    annee = django_filters.NumberFilter(field_name="annee")

    class Meta:
        model = CartographieVersion
        fields: list[str] = []


class RisqueFilter(django_filters.FilterSet):
    version = django_filters.UUIDFilter(field_name="version_id")
    processus = django_filters.UUIDFilter(field_name="processus_id")
    objet_auditable = django_filters.UUIDFilter(field_name="objet_auditable_id")
    niveau = django_filters.ChoiceFilter(choices=NiveauRisque.choices)
    probabilite = django_filters.NumberFilter(field_name="probabilite")
    impact = django_filters.NumberFilter(field_name="impact")
    reponse = django_filters.ChoiceFilter(choices=ReponseRisque.choices)
    priorite = django_filters.ChoiceFilter(choices=PrioriteRisque.choices)
    q = django_filters.CharFilter(method="filter_q", help_text=Q_AIDE)

    class Meta:
        model = Risque
        fields: list[str] = []

    def filter_q(self, queryset: QuerySet[Risque], name: str, value: str) -> QuerySet[Risque]:
        return _recherche(queryset, value, "code", "libelle")
