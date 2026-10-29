import django_filters
from django.db.models import QuerySet

from .models import LigneProgramme, ProgrammeAnnuel, StatutProgramme, TypeIntervention

TRIMESTRES = [(str(n), str(n)) for n in range(1, 5)]


class ProgrammeFilter(django_filters.FilterSet):
    annee = django_filters.NumberFilter(field_name="annee")
    statut = django_filters.ChoiceFilter(choices=StatutProgramme.choices)

    class Meta:
        model = ProgrammeAnnuel
        fields: list[str] = []


class LigneFilter(django_filters.FilterSet):
    programme = django_filters.UUIDFilter(field_name="programme_id")
    processus = django_filters.UUIDFilter(field_name="processus_id")
    objet_auditable = django_filters.UUIDFilter(field_name="objet_auditable_id")
    entite = django_filters.UUIDFilter(field_name="entites__id")
    type = django_filters.ChoiceFilter(choices=TypeIntervention.choices)
    trimestre = django_filters.ChoiceFilter(
        choices=TRIMESTRES,
        method="filter_trimestre",
        help_text="Trimestre du début prévu (1 à 4).",
    )
    q = django_filters.CharFilter(
        method="filter_q", help_text="Recherche insensible à la casse sur le titre."
    )

    class Meta:
        model = LigneProgramme
        fields: list[str] = []

    def filter_trimestre(
        self, queryset: QuerySet[LigneProgramme], name: str, value: str
    ) -> QuerySet[LigneProgramme]:
        quarter = int(value)
        return queryset.filter(debut_prevu__month__in=range(3 * quarter - 2, 3 * quarter + 1))

    def filter_q(
        self, queryset: QuerySet[LigneProgramme], name: str, value: str
    ) -> QuerySet[LigneProgramme]:
        return queryset.filter(titre__icontains=value)
