from datetime import date
from typing import cast

import pytest
from auditlog.models import LogEntry
from django.db import IntegrityError, transaction

from apps.programmation import models as m
from apps.referentiel.models import Direction
from tests.factories import DirectionFactory, make_user

from .factories import ligne, programme

pytestmark = pytest.mark.django_db


def test_un_seul_programme_par_annee_hors_supprimes() -> None:
    p = programme(annee=2030)
    with pytest.raises(IntegrityError), transaction.atomic():
        programme(annee=2030)
    p.soft_delete(make_user())
    assert programme(annee=2030).annee == 2030


@pytest.mark.parametrize("annee", [1999, 2101])
def test_annee_hors_bornes_rejetee(annee: int) -> None:
    with pytest.raises(IntegrityError, match="programme_annee_2000_2100"), transaction.atomic():
        programme(annee=annee)


def test_programme_valide_sans_signature_rejete() -> None:
    with pytest.raises(IntegrityError, match="programme_valide_signe"), transaction.atomic():
        programme(statut=m.StatutProgramme.VALIDE)


def test_periode_non_ordonnee_rejetee_par_la_base() -> None:
    with pytest.raises(IntegrityError):
        ligne(debut_prevu=date(2026, 5, 1), fin_prevue=date(2026, 4, 30))


def test_numero_unique_meme_supprime() -> None:
    p = programme()
    first = ligne(programme=p, numero=1)
    first.soft_delete(make_user())
    with pytest.raises(IntegrityError, match="ligne_numero_unique"), transaction.atomic():
        ligne(programme=p, numero=1)


def test_numero_zero_et_charge_negative_rejetes() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        ligne(numero=0)
    with pytest.raises(IntegrityError), transaction.atomic():
        ligne(charge_prevue_jours=-1)


def test_champs_execution_vide_par_defaut() -> None:
    assert m.CHAMPS_EXECUTION == frozenset()


def test_creation_et_m2m_historisees() -> None:
    li = ligne()
    assert LogEntry.objects.get_for_object(li).filter(action=LogEntry.Action.CREATE).exists()
    direction = cast(Direction, DirectionFactory())
    li.entites.add(direction)
    entries = LogEntry.objects.get_for_object(li)
    m2m = [e.changes_dict["entites"] for e in entries if "entites" in e.changes_dict]
    assert len(m2m) == 1
    assert m2m[0]["operation"] == "add"
    assert str(direction) in m2m[0]["objects"]


def test_str_programme() -> None:
    assert str(programme(annee=2031)) == "Programme annuel 2031"
