import django_filters
from django.db.models import Q, QuerySet

from .models import Role, User


class UtilisateurFilter(django_filters.FilterSet):
    role = django_filters.ChoiceFilter(choices=Role.choices)
    direction_code = django_filters.CharFilter(field_name="direction_code", lookup_expr="exact")
    q = django_filters.CharFilter(
        method="filter_q",
        help_text="Recherche insensible à la casse sur l'identifiant, le prénom et le nom.",
    )

    class Meta:
        model = User
        fields: list[str] = []

    def filter_q(self, queryset: QuerySet[User], name: str, value: str) -> QuerySet[User]:
        return queryset.filter(
            Q(username__icontains=value)
            | Q(first_name__icontains=value)
            | Q(last_name__icontains=value)
        )
