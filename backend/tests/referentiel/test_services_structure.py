import pytest

from apps.core.exceptions import RegleMetierError
from apps.referentiel.models import Direction, NatureObjet, TypeEntite
from apps.referentiel.services import (
    creer_direction,
    creer_objet,
    creer_processus,
    modifier_direction,
    modifier_objet,
    modifier_processus,
    supprimer_direction,
    supprimer_objet,
    supprimer_processus,
)
from apps.users.models import User
from tests.referentiel import typed

pytestmark = pytest.mark.django_db

MSG_CODE = "Le code ne peut pas être modifié après création."


def test_creer_direction_renseigne_created_by(rai: User) -> None:
    d = creer_direction(code="DG", libelle="Direction générale", type=TypeEntite.DIRECTION, by=rai)
    assert d.created_by == rai
    assert d.updated_by == rai


def test_departement_exige_une_direction_parente(rai: User) -> None:
    with pytest.raises(RegleMetierError) as exc:
        creer_direction(code="DEP1", libelle="Dép", type=TypeEntite.DEPARTEMENT, by=rai)
    assert exc.value.errors["parent"] == ["Un département doit être rattaché à une direction."]


def test_departement_sous_un_departement_refuse(rai: User) -> None:
    direction = typed.direction()
    dep = typed.direction(type=TypeEntite.DEPARTEMENT, parent=direction)
    with pytest.raises(RegleMetierError) as exc:
        creer_direction(code="DEP2", libelle="Dép", type=TypeEntite.DEPARTEMENT, parent=dep, by=rai)
    assert "parent" in exc.value.errors


def test_departement_sous_une_direction(rai: User) -> None:
    direction = typed.direction()
    dep = creer_direction(
        code="DEP3", libelle="Dép", type=TypeEntite.DEPARTEMENT, parent=direction, by=rai
    )
    assert dep.parent == direction


def test_code_non_modifiable(rai: User) -> None:
    d = typed.direction(code="DAF")
    with pytest.raises(RegleMetierError) as exc:
        modifier_direction(d, code="XXX", by=rai)
    assert exc.value.errors["code"] == [MSG_CODE]
    p = typed.processus(code="FEP")
    with pytest.raises(RegleMetierError) as exc:
        modifier_processus(p, code="XXX", by=rai)
    assert exc.value.errors["code"] == [MSG_CODE]


def test_modifier_avec_le_meme_code_est_accepte(rai: User) -> None:
    d = typed.direction(code="DAF")
    d = modifier_direction(d, code="DAF", libelle="Nouveau", by=rai)
    assert d.libelle == "Nouveau"
    assert d.updated_by == rai


def test_supprimer_direction_rattachee_refuse(rai: User) -> None:
    d = typed.direction()
    p = typed.processus()
    p.directions.add(d)
    with pytest.raises(RegleMetierError) as exc:
        supprimer_direction(d, by=rai)
    assert exc.value.message == (
        "Cette direction est rattachée à un processus ou porte des départements actifs."
    )
    p.soft_delete(rai)
    supprimer_direction(d, by=rai)
    assert Direction.objects.filter(pk=d.pk).count() == 0


def test_supprimer_direction_avec_departements_refuse(rai: User) -> None:
    d = typed.direction()
    typed.direction(type=TypeEntite.DEPARTEMENT, parent=d)
    with pytest.raises(RegleMetierError):
        supprimer_direction(d, by=rai)


def test_creer_processus_avec_directions(rai: User) -> None:
    d = typed.direction()
    p = creer_processus(code="GRH", libelle="RH", famille="SUPPORT", directions=[d], by=rai)
    assert list(p.directions.all()) == [d]
    assert p.created_by == rai


def test_code_processus_invalide_refuse(rai: User) -> None:
    with pytest.raises(RegleMetierError) as exc:
        creer_processus(code="ÉST", libelle="x", famille="SUPPORT", by=rai)
    assert "code" in exc.value.errors


def test_code_processus_deja_pris_refuse(rai: User) -> None:
    typed.processus(code="FEP")
    with pytest.raises(RegleMetierError) as exc:
        creer_processus(code="FEP", libelle="x", famille="SUPPORT", by=rai)
    assert "code" in exc.value.errors


def test_supprimer_processus_avec_risque_actif_refuse(rai: User) -> None:
    r = typed.risque()
    with pytest.raises(RegleMetierError) as exc:
        supprimer_processus(r.processus, by=rai)
    assert exc.value.message == (
        "Ce processus porte des risques ou des objets auditables actifs : supprimez-les d'abord."
    )
    r.soft_delete(rai)
    supprimer_processus(r.processus, by=rai)
    r.processus.refresh_from_db()
    assert r.processus.deleted_at is not None


def test_supprimer_processus_avec_objet_actif_refuse(rai: User) -> None:
    o = typed.objet()
    with pytest.raises(RegleMetierError):
        supprimer_processus(o.processus, by=rai)


def test_creer_objet_domaine_puis_operation(rai: User) -> None:
    p = typed.processus()
    dom = creer_objet(processus=p, nature=NatureObjet.DOMAINE, libelle="Domaine", by=rai)
    op = creer_objet(processus=p, nature=NatureObjet.OPERATION, libelle="Op", parent=dom, by=rai)
    assert op.parent == dom
    assert op.created_by == rai


def test_operation_hors_processus_refusee(rai: User) -> None:
    dom_autre = typed.objet()
    p = typed.processus()
    for parent in (dom_autre, None):
        with pytest.raises(RegleMetierError) as exc:
            creer_objet(
                processus=p, nature=NatureObjet.OPERATION, libelle="Op", parent=parent, by=rai
            )
        assert exc.value.errors["parent"] == [
            "Une opération doit être rattachée à un domaine du même processus."
        ]


def test_domaine_avec_parent_refuse(rai: User) -> None:
    dom = typed.objet()
    with pytest.raises(RegleMetierError) as exc:
        creer_objet(
            processus=dom.processus,
            nature=NatureObjet.DOMAINE,
            libelle="D2",
            parent=dom,
            by=rai,
        )
    assert "parent" in exc.value.errors


def test_modifier_objet_et_supprimer(rai: User) -> None:
    dom = typed.objet()
    dom = modifier_objet(dom, libelle="Renommé", by=rai)
    assert dom.libelle == "Renommé"
    supprimer_objet(dom, by=rai)
    dom.refresh_from_db()
    assert dom.deleted_at is not None


def test_supprimer_objet_avec_operations_ou_risques_refuse(rai: User) -> None:
    dom = typed.objet()
    typed.objet(processus=dom.processus, nature=NatureObjet.OPERATION, parent=dom)
    with pytest.raises(RegleMetierError):
        supprimer_objet(dom, by=rai)
    obj = typed.objet()
    typed.risque(processus=obj.processus, objet_auditable=obj)
    with pytest.raises(RegleMetierError):
        supprimer_objet(obj, by=rai)
