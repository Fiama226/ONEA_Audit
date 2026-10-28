from typing import cast

import pytest
from auditlog.models import LogEntry
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.referentiel.models import (
    CartographieVersion,
    Direction,
    NatureObjet,
    NiveauRisque,
    PrioriteRisque,
    Processus,
    Risque,
    TypeEntite,
)
from apps.referentiel.scoring import niveau_pour_score, priorite_par_defaut
from apps.users.models import User
from tests.factories import (
    CartographieVersionFactory,
    DirectionFactory,
    ObjetAuditableFactory,
    ProcessusFactory,
    RisqueFactory,
)

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(("p", "i"), [(0, 3), (6, 3), (3, 0), (3, 6)])
def test_probabilite_impact_hors_bornes_rejetes_par_la_base(p: int, i: int) -> None:
    with (
        pytest.raises(IntegrityError, match="risque_probabilite_1_5|risque_impact_1_5"),
        transaction.atomic(),
    ):
        RisqueFactory(probabilite=p, impact=i)


@pytest.mark.parametrize(("p", "i"), [(None, 3), (3, None)])
def test_probabilite_impact_nuls_rejetes_par_la_base(p: int | None, i: int | None) -> None:
    with pytest.raises(IntegrityError, match="not-null|null value"), transaction.atomic():
        RisqueFactory(probabilite=p, impact=i)


def test_modifier_probabilite_recalcule_score_et_niveau() -> None:
    r = cast(Risque, RisqueFactory(probabilite=1, impact=1))
    r.refresh_from_db()
    assert (r.score, r.niveau) == (1, NiveauRisque.FAIBLE)
    r.probabilite = 5
    r.impact = 5
    r.save()
    r.refresh_from_db()
    assert (r.score, r.niveau) == (25, NiveauRisque.ELEVE)


def test_score_et_niveau_generes_concordent_avec_scoring() -> None:
    version = CartographieVersionFactory()
    processus = ProcessusFactory()
    for p in range(1, 6):
        for i in range(1, 6):
            r = cast(
                Risque, RisqueFactory(version=version, processus=processus, probabilite=p, impact=i)
            )
            r.refresh_from_db()
            assert (r.score, r.niveau) == (p * i, niveau_pour_score(p * i))


@pytest.mark.parametrize(
    ("score", "niveau"),
    [(1, "FAIBLE"), (7, "FAIBLE"), (8, "MOYEN"), (14, "MOYEN"), (15, "ELEVE"), (25, "ELEVE")],
)
def test_niveau_pour_score(score: int, niveau: str) -> None:
    assert niveau_pour_score(score) == niveau


def test_priorite_par_defaut() -> None:
    assert priorite_par_defaut(NiveauRisque.ELEVE) == PrioriteRisque.PRIORITAIRE
    assert priorite_par_defaut(NiveauRisque.MOYEN) == PrioriteRisque.AMELIORATION
    assert priorite_par_defaut(NiveauRisque.FAIBLE) == PrioriteRisque.OBSERVATION


def test_code_unique_par_version_mais_pas_entre_versions() -> None:
    processus = ProcessusFactory()
    v1, v2 = CartographieVersionFactory(), CartographieVersionFactory()
    RisqueFactory(version=v1, processus=processus, numero=1, rang=1)
    RisqueFactory(version=v2, processus=processus, numero=1, rang=1)  # même code, autre version
    with (
        pytest.raises(IntegrityError, match="risque_code_unique_par_version"),
        transaction.atomic(),
    ):
        RisqueFactory(
            version=v1, processus=processus, numero=2, rang=2, code=f"1-{processus.code}-R1"
        )


def test_une_seule_cartographie_par_annee_hors_supprimees(rai: User) -> None:
    v = cast(CartographieVersion, CartographieVersionFactory(annee=2030))
    with (
        pytest.raises(IntegrityError, match="cartographie_annee_unique_actif"),
        transaction.atomic(),
    ):
        CartographieVersionFactory(annee=2030)
    v.soft_delete(rai)
    CartographieVersionFactory(annee=2030)
    assert CartographieVersion.objects.filter(annee=2030).count() == 1


def test_annee_hors_plage_rejetee() -> None:
    with (
        pytest.raises(IntegrityError, match="cartographie_annee_2000_2100"),
        transaction.atomic(),
    ):
        CartographieVersionFactory(annee=1999)


def test_code_processus_reutilisable_apres_soft_delete(rai: User) -> None:
    p = cast(Processus, ProcessusFactory(code="EST"))
    with (
        pytest.raises(IntegrityError, match="processus_code_unique_actif"),
        transaction.atomic(),
    ):
        ProcessusFactory(code="EST")
    p.soft_delete(rai)
    ProcessusFactory(code="EST")
    assert Processus.objects.filter(code="EST").count() == 1


def test_departement_sans_parent_rejete() -> None:
    with pytest.raises(IntegrityError, match="direction_parent_coherent"), transaction.atomic():
        DirectionFactory(type=TypeEntite.DEPARTEMENT, parent=None)


def test_direction_avec_parent_rejetee() -> None:
    parent = DirectionFactory()
    with pytest.raises(IntegrityError, match="direction_parent_coherent"), transaction.atomic():
        DirectionFactory(type=TypeEntite.DIRECTION, parent=parent)


def test_departement_avec_parent_accepte() -> None:
    parent = cast(Direction, DirectionFactory())
    dep = cast(Direction, DirectionFactory(type=TypeEntite.DEPARTEMENT, parent=parent))
    assert list(Direction.objects.get(pk=parent.pk).departements.all()) == [dep]


def test_domaine_avec_parent_rejete() -> None:
    domaine = ObjetAuditableFactory()
    with pytest.raises(IntegrityError, match="objet_parent_coherent"), transaction.atomic():
        ObjetAuditableFactory(nature=NatureObjet.DOMAINE, parent=domaine)


def test_operation_sans_parent_rejetee() -> None:
    with pytest.raises(IntegrityError, match="objet_parent_coherent"), transaction.atomic():
        ObjetAuditableFactory(nature=NatureObjet.OPERATION, parent=None)


def test_code_processus_accentue_refuse() -> None:
    p = ProcessusFactory.build(code="ÉST")
    with pytest.raises(ValidationError) as exc:
        p.full_clean(exclude=["directions"])
    assert "code" in exc.value.message_dict


def test_code_direction_et_risque_invalides_refuses() -> None:
    with pytest.raises(ValidationError) as exc:
        DirectionFactory.build(code="dg").full_clean()
    assert "code" in exc.value.message_dict
    with pytest.raises(ValidationError) as exc:
        RisqueFactory.build(code="0-EST-R1").full_clean(exclude=["version", "processus"])
    assert "code" in exc.value.message_dict


def test_creation_et_m2m_historisees(db: None) -> None:
    risque = RisqueFactory()
    assert LogEntry.objects.get_for_object(risque).filter(action=LogEntry.Action.CREATE).exists()

    processus = cast(Processus, ProcessusFactory())
    direction = cast(Direction, DirectionFactory())
    processus.directions.add(direction)
    entries = LogEntry.objects.get_for_object(processus)
    m2m = [e.changes_dict["directions"] for e in entries if "directions" in e.changes_dict]
    assert len(m2m) == 1
    assert m2m[0]["operation"] == "add"
    assert str(direction) in m2m[0]["objects"]
