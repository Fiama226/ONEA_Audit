import django_filters

from .models import DestinataireDiffusion, Rapport, RapportProvisoire, ReponseRapport


class RapportFilter(django_filters.FilterSet):
    mission = django_filters.UUIDFilter(
        field_name="mission_id",
        help_text="Mission. Sans elle, la liste se limite aux rapports diffusés visibles.",
    )

    class Meta:
        model = Rapport
        fields: list[str] = []


class ProvisoireFilter(django_filters.FilterSet):
    rapport = django_filters.UUIDFilter(field_name="rapport_id", help_text="Rapport ou mission.")
    mission = django_filters.UUIDFilter(field_name="mission_id", help_text="Mission ou rapport.")

    class Meta:
        model = RapportProvisoire
        fields: list[str] = []


class ReponseFilter(django_filters.FilterSet):
    provisoire = django_filters.UUIDFilter(
        field_name="provisoire_id", help_text="Obligatoire pour la liste."
    )
    constat = django_filters.UUIDFilter(field_name="constat_id")

    class Meta:
        model = ReponseRapport
        fields: list[str] = []


class DestinataireFilter(django_filters.FilterSet):
    rapport = django_filters.UUIDFilter(
        field_name="rapport_id", help_text="Obligatoire pour la liste."
    )

    class Meta:
        model = DestinataireDiffusion
        fields: list[str] = []
