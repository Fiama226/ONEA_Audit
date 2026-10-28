"""Factories de l'app programmation (typées pour mypy)."""

from datetime import date
from typing import Any, cast

import factory

from apps.programmation.models import LigneProgramme, ProgrammeAnnuel
from tests.factories import ProcessusFactory


class ProgrammeAnnuelFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProgrammeAnnuel

    annee = factory.Sequence(lambda n: 2000 + n % 101)
    libelle = factory.LazyAttribute(lambda o: f"Programme annuel {o.annee}")


class LigneProgrammeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LigneProgramme

    programme = factory.SubFactory(ProgrammeAnnuelFactory)
    numero = factory.Sequence(lambda n: n + 1)
    titre = factory.Sequence(lambda n: f"Intervention {n}")
    type = "ASSURANCE"
    processus = factory.SubFactory(ProcessusFactory)
    debut_prevu = factory.LazyAttribute(lambda o: date(o.programme.annee, 3, 1))
    fin_prevue = factory.LazyAttribute(lambda o: date(o.programme.annee, 3, 31))


def programme(**kw: Any) -> ProgrammeAnnuel:
    return cast(ProgrammeAnnuel, ProgrammeAnnuelFactory(**kw))


def ligne(**kw: Any) -> LigneProgramme:
    return cast(LigneProgramme, LigneProgrammeFactory(**kw))


def reset_sequences() -> None:
    ProgrammeAnnuelFactory.reset_sequence()
    LigneProgrammeFactory.reset_sequence()
