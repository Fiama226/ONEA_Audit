from typing import Any, cast

import pytest
from auditlog.models import LogEntry
from django.contrib.contenttypes.models import ContentType

from apps.core.exceptions import RegleMetierError
from apps.programmation.exceptions import ProgrammeFigeError
from apps.programmation.models import (
    LigneProgramme,
    ProgrammeAnnuel,
    StatutProgramme,
)
from apps.programmation.services import (
    creer_ligne,
    creer_programme,
    modifier_ligne,
    modifier_programme,
    supprimer_ligne,
    supprimer_programme,
    valider_programme,
)
from apps.referentiel.models import Processus
from apps.users.models import User
from tests.factories import ProcessusFactory

from .factories import ligne, programme


def test_creer_programme_libelle_par_defaut(rai: User) -> None:
    p = creer_programme(annee=2026, by=rai)
    assert p.libelle == "Programme annuel d'audit interne 2026"
    assert p.statut == StatutProgramme.BROUILLON
    assert p.created_by == rai and p.updated_by == rai


def test_annee_deja_prise_422_sur_annee(rai: User) -> None:
    creer_programme(annee=2026, by=rai)
    with pytest.raises(RegleMetierError) as exc:
        creer_programme(annee=2026, by=rai)
    assert exc.value.errors["annee"] == ["Un programme annuel existe déjà pour l'année 2026."]


def test_annee_non_modifiable(rai: User) -> None:
    p = programme(annee=2026)
    with pytest.raises(RegleMetierError) as exc:
        modifier_programme(p, annee=2027, by=rai)
    assert exc.value.errors["annee"] == ["L'année d'un programme ne peut pas être modifiée."]
    modifier_programme(p, annee=2026, libelle="Nouveau", by=rai)
    p.refresh_from_db()
    assert p.libelle == "Nouveau"


def test_valider_programme_vide_refuse(rai: User) -> None:
    p = programme(annee=2026)
    with pytest.raises(RegleMetierError, match="sans mission prévue"):
        valider_programme(p, by=rai)


def test_validation_renseigne_valideur_et_historisee(rai: User) -> None:
    p = programme(annee=2026)
    ligne(programme=p, numero=1)
    valider_programme(p, by=rai)
    p.refresh_from_db()
    assert p.statut == StatutProgramme.VALIDE
    assert p.valide_par == rai and p.valide_le is not None
    entree = LogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(ProgrammeAnnuel),
        object_pk=str(p.pk),
        action=LogEntry.Action.UPDATE,
    ).latest("timestamp")
    assert entree.actor == rai
    assert entree.changes["statut"] == ["BROUILLON", "VALIDE"]


def test_valider_ignore_les_lignes_supprimees(rai: User) -> None:
    p = programme(annee=2026)
    ligne(programme=p, numero=1).soft_delete(rai)
    with pytest.raises(RegleMetierError):
        valider_programme(p, by=rai)


@pytest.mark.parametrize(
    "ecriture",
    [
        "modifier_programme",
        "supprimer_programme",
        "creer_ligne",
        "modifier_ligne",
        "supprimer_ligne",
    ],
)
def test_programme_valide_toutes_ecritures_refusees(
    ecriture: str, programme_valide: ProgrammeAnnuel, rai: User
) -> None:
    une_ligne = programme_valide.lignes.first()
    assert une_ligne is not None
    appels: dict[str, Any] = {
        "modifier_programme": lambda: modifier_programme(programme_valide, libelle="X", by=rai),
        "supprimer_programme": lambda: supprimer_programme(programme_valide, by=rai),
        "creer_ligne": lambda: creer_ligne(
            programme=programme_valide,
            titre="X",
            type="ASSURANCE",
            processus=cast(Processus, ProcessusFactory()),
            debut_prevu=une_ligne.debut_prevu,
            fin_prevue=une_ligne.fin_prevue,
            by=rai,
        ),
        "modifier_ligne": lambda: modifier_ligne(une_ligne, titre="X", by=rai),
        "supprimer_ligne": lambda: supprimer_ligne(une_ligne, by=rai),
    }
    with pytest.raises(ProgrammeFigeError):
        appels[ecriture]()
    assert LigneProgramme.objects.filter(programme=programme_valide).count() == 2


def test_supprimer_brouillon_supprime_ses_lignes(rai: User) -> None:
    p = programme(annee=2026)
    ligne(programme=p, numero=1)
    ligne(programme=p, numero=2)
    supprimer_programme(p, by=rai)
    assert not ProgrammeAnnuel.objects.filter(pk=p.pk).exists()
    assert not LigneProgramme.objects.filter(programme_id=p.pk).exists()
    supprimees = LigneProgramme.all_objects.filter(programme_id=p.pk, deleted_at__isnull=False)
    assert supprimees.count() == 2
    # l'année est de nouveau disponible
    assert creer_programme(annee=2026, by=rai).annee == 2026
