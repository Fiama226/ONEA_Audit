"""Gardes complémentaires : déplacement de ligne, bulk_update et table `entites`."""

from typing import cast

import pytest
from django.db import transaction

from apps.core.exceptions import RegleMetierError
from apps.programmation.exceptions import ProgrammeFigeError
from apps.programmation.models import LigneProgramme, ProgrammeAnnuel
from apps.referentiel.models import Direction
from tests.factories import DirectionFactory

from .factories import ligne, programme

pytestmark = pytest.mark.django_db


def _premiere_ligne(prog: ProgrammeAnnuel) -> LigneProgramme:
    li = prog.lignes.first()
    assert li is not None
    return li


def _direction() -> Direction:
    return cast(Direction, DirectionFactory())


def test_ligne_ne_quitte_pas_un_programme_valide_par_save(
    programme_valide: ProgrammeAnnuel,
) -> None:
    li = _premiere_ligne(programme_valide)
    li.programme = programme()
    with pytest.raises(ProgrammeFigeError):
        li.save()
    with pytest.raises(ProgrammeFigeError):
        li.save(update_fields=["programme"])
    assert LigneProgramme.objects.get(pk=li.pk).programme_id == programme_valide.pk


def test_ligne_n_entre_pas_dans_un_programme_valide_par_save(
    programme_valide: ProgrammeAnnuel,
) -> None:
    li = ligne()
    li.programme = programme_valide
    with pytest.raises(ProgrammeFigeError):
        li.save()
    with pytest.raises(ProgrammeFigeError):
        ligne(programme=programme_valide, numero=50)


def test_ligne_ne_change_pas_de_programme_par_save() -> None:
    li = ligne()
    li.programme = programme()
    with pytest.raises(RegleMetierError, match="ne peut pas changer de programme"):
        li.save()


def test_bulk_update_ligne_ne_change_pas_de_programme() -> None:
    li = ligne()
    with pytest.raises(RegleMetierError, match="ne peut pas changer de programme"):
        LigneProgramme.objects.bulk_update([li], ["programme"])


def test_bulk_update_programme_valide_refuse(programme_valide: ProgrammeAnnuel) -> None:
    programme_valide.libelle = "x"
    with pytest.raises(ProgrammeFigeError):
        ProgrammeAnnuel.objects.bulk_update([programme_valide], ["libelle"])


def test_entites_ajout_refuse_sur_programme_valide(programme_valide: ProgrammeAnnuel) -> None:
    li = _premiere_ligne(programme_valide)
    with pytest.raises(ProgrammeFigeError), transaction.atomic():
        li.entites.add(_direction())
    assert li.entites.count() == 0


def test_entites_retrait_refuse_sur_programme_valide(programme_valide: ProgrammeAnnuel) -> None:
    li = _premiere_ligne(programme_valide)
    d = _direction()
    # Pose directe sur la table de liaison (test uniquement) : le récepteur est contourné.
    LigneProgramme.entites.through.objects.create(ligneprogramme_id=li.pk, direction_id=d.pk)
    with pytest.raises(ProgrammeFigeError), transaction.atomic():
        li.entites.remove(d)
    assert li.entites.count() == 1


def test_entites_vidage_refuse_sur_programme_valide(programme_valide: ProgrammeAnnuel) -> None:
    li = _premiere_ligne(programme_valide)
    d = _direction()
    LigneProgramme.entites.through.objects.create(ligneprogramme_id=li.pk, direction_id=d.pk)
    with pytest.raises(ProgrammeFigeError), transaction.atomic():
        li.entites.clear()
    with pytest.raises(ProgrammeFigeError), transaction.atomic():
        li.entites.set([])
    assert li.entites.count() == 1


def test_entites_cote_inverse_refuse_sur_programme_valide(
    programme_valide: ProgrammeAnnuel,
) -> None:
    li = _premiere_ligne(programme_valide)
    d = _direction()
    with pytest.raises(ProgrammeFigeError), transaction.atomic():
        d.lignes_programme.add(li)
    LigneProgramme.entites.through.objects.create(ligneprogramme_id=li.pk, direction_id=d.pk)
    with pytest.raises(ProgrammeFigeError), transaction.atomic():
        d.lignes_programme.remove(li)
    with pytest.raises(ProgrammeFigeError), transaction.atomic():
        d.lignes_programme.clear()
    assert li.entites.count() == 1


def test_entites_modifiables_sur_programme_brouillon() -> None:
    li = ligne()
    d = _direction()
    li.entites.add(d)
    li.entites.remove(d)
    li.entites.add(d)
    li.entites.clear()
    assert li.entites.count() == 0
