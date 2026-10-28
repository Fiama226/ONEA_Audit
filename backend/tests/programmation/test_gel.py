import pytest

from apps.core.exceptions import RegleMetierError
from apps.programmation.exceptions import ProgrammeFigeError
from apps.programmation.models import LigneProgramme, ProgrammeAnnuel, StatutProgramme
from tests.factories import make_user

from .factories import LigneProgrammeFactory, ligne, programme

pytestmark = pytest.mark.django_db


def test_ligne_d_un_programme_valide_immuable_hors_service(
    programme_valide: ProgrammeAnnuel,
) -> None:
    li = programme_valide.lignes.first()
    assert li is not None
    li.titre = "contournement"
    with pytest.raises(ProgrammeFigeError):
        li.save()
    with pytest.raises(ProgrammeFigeError):
        LigneProgramme.objects.filter(pk=li.pk).update(titre="x")
    with pytest.raises(ProgrammeFigeError):
        LigneProgramme.objects.bulk_create(
            [LigneProgrammeFactory.build(programme=programme_valide, numero=9)]
        )
    with pytest.raises(ProgrammeFigeError):
        LigneProgramme.objects.bulk_update([li], ["titre"])


def test_message_programme_fige(programme_valide: ProgrammeAnnuel) -> None:
    with pytest.raises(ProgrammeFigeError) as exc:
        programme_valide.save()
    assert str(exc.value) == (
        f"Le programme annuel {programme_valide.annee} est validé : il ne peut plus être modifié."
    )


def test_programme_valide_ni_modifiable_ni_supprimable_par_save(
    programme_valide: ProgrammeAnnuel,
) -> None:
    programme_valide.libelle = "x"
    with pytest.raises(ProgrammeFigeError):
        programme_valide.save()
    with pytest.raises(ProgrammeFigeError):
        programme_valide.soft_delete(make_user())
    with pytest.raises(ProgrammeFigeError):
        ProgrammeAnnuel.objects.filter(pk=programme_valide.pk).update(libelle="x")


def test_ligne_supprimee_logiquement_d_un_programme_valide_refusee(
    programme_valide: ProgrammeAnnuel,
) -> None:
    li = programme_valide.lignes.first()
    assert li is not None
    with pytest.raises(ProgrammeFigeError):
        li.soft_delete(make_user())


def test_statut_non_modifiable_par_update() -> None:
    p = programme()
    with pytest.raises(RegleMetierError, match="ne change que par sa validation"):
        ProgrammeAnnuel.objects.filter(pk=p.pk).update(statut=StatutProgramme.VALIDE)
    p.statut = StatutProgramme.VALIDE
    with pytest.raises(RegleMetierError, match="ne change que par sa validation"):
        ProgrammeAnnuel.objects.bulk_update([p], ["statut"])


def test_ligne_ne_change_pas_de_programme_par_update() -> None:
    li = ligne()
    autre = programme()
    with pytest.raises(RegleMetierError, match="ne peut pas changer de programme"):
        LigneProgramme.objects.filter(pk=li.pk).update(programme=autre)
    with pytest.raises(RegleMetierError, match="ne peut pas changer de programme"):
        LigneProgramme.objects.filter(pk=li.pk).update(programme_id=autre.pk)


def test_programme_brouillon_modifiable() -> None:
    li = ligne()
    li.titre = "nouveau"
    li.save()
    assert LigneProgramme.objects.filter(pk=li.pk).update(titre="autre") == 1
