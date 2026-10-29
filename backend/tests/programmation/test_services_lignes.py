from datetime import date
from decimal import Decimal
from typing import Any, cast

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.core.exceptions import RegleMetierError
from apps.programmation.models import LigneProgramme
from apps.programmation.services import (
    creer_ligne,
    modifier_ligne,
    supprimer_ligne,
    synthese,
)
from apps.referentiel.models import Direction, ObjetAuditable, Processus
from apps.users.models import User
from tests import factories as f

from .factories import ligne, programme


def _direction(**kw: Any) -> Direction:
    return cast(Direction, f.DirectionFactory(**kw))


def _processus(**kw: Any) -> Processus:
    return cast(Processus, f.ProcessusFactory(**kw))


def _objet(**kw: Any) -> ObjetAuditable:
    return cast(ObjetAuditable, f.ObjetAuditableFactory(**kw))


def _creer(p: Any, by: User, **kw: Any) -> LigneProgramme:
    base: dict[str, Any] = {
        "titre": "Achats",
        "type": "ASSURANCE",
        "processus": _processus(),
        "debut_prevu": date(2026, 3, 1),
        "fin_prevue": date(2026, 4, 30),
    }
    base.update(kw)
    return creer_ligne(programme=p, by=by, **base)


def test_creer_ligne_numerote_et_trace(rai: User) -> None:
    p = programme(annee=2026)
    d = _direction()
    l1 = _creer(p, rai, entites=[d], charge_prevue_jours=Decimal("12.5"))
    l2 = _creer(p, rai)
    assert (l1.numero, l2.numero) == (1, 2)
    assert l1.created_by == rai and list(l1.entites.all()) == [d]


def test_objet_d_un_autre_processus_refuse(rai: User) -> None:
    p = programme(annee=2026)
    fep, gsi = _processus(code="FEP"), _processus(code="GSI")
    objet = _objet(processus=gsi)
    with pytest.raises(RegleMetierError) as exc:
        _creer(p, rai, processus=fep, objet_auditable=objet)
    assert exc.value.errors["objet_auditable"] == [
        "L'objet auditable doit appartenir au processus de la mission prévue."
    ]


def test_numero_supprime_jamais_reattribue(rai: User) -> None:
    p = programme(annee=2026)
    _creer(p, rai)
    l2 = _creer(p, rai)
    supprimer_ligne(l2, by=rai)
    assert _creer(p, rai).numero == 3


def test_debut_hors_annee_refuse(rai: User) -> None:
    p = programme(annee=2026)
    with pytest.raises(RegleMetierError) as exc:
        _creer(p, rai, debut_prevu=date(2027, 1, 5), fin_prevue=date(2027, 2, 1))
    assert exc.value.errors["debut_prevu"] == [
        "La mission prévue doit commencer pendant l'année 2026."
    ]


def test_fin_sur_annee_suivante_acceptee(rai: User) -> None:
    p = programme(annee=2026)
    nouvelle = _creer(p, rai, debut_prevu=date(2026, 12, 31), fin_prevue=date(2027, 1, 15))
    assert nouvelle.fin_prevue == date(2027, 1, 15)


def test_fin_avant_debut_et_charge_negative(rai: User) -> None:
    p = programme(annee=2026)
    with pytest.raises(RegleMetierError) as exc:
        _creer(
            p,
            rai,
            debut_prevu=date(2026, 5, 1),
            fin_prevue=date(2026, 4, 1),
            charge_prevue_jours=Decimal("-1"),
        )
    assert exc.value.errors["fin_prevue"] == ["La fin prévue doit suivre le début prévu."]
    assert exc.value.errors["charge_prevue_jours"] == [
        "La charge prévue ne peut pas être négative."
    ]


def test_processus_ou_entite_supprimes_refuses(rai: User) -> None:
    p = programme(annee=2026)
    proc = _processus()
    proc.soft_delete(rai)
    with pytest.raises(RegleMetierError) as exc:
        _creer(p, rai, processus=proc)
    assert exc.value.errors["processus"] == ["Ce processus n'existe plus dans le référentiel."]

    objet = _objet()
    objet.soft_delete(rai)
    with pytest.raises(RegleMetierError) as exc:
        _creer(p, rai, processus=objet.processus, objet_auditable=objet)
    assert exc.value.errors["objet_auditable"] == [
        "Cet objet auditable n'existe plus dans le référentiel."
    ]

    d = _direction(code="DEF")
    d.soft_delete(rai)
    with pytest.raises(RegleMetierError) as exc:
        _creer(p, rai, entites=[d])
    assert exc.value.errors["entites"] == ["L'entité DEF n'existe plus dans le référentiel."]
    assert not LigneProgramme.objects.exists()


def test_modifier_ligne_champs_et_entites(rai: User) -> None:
    p = programme(annee=2026)
    base = _creer(p, rai, entites=[_direction()])
    d2 = _direction()
    modifier_ligne(base, titre="Nouveau", entites=[d2], fin_prevue=date(2026, 6, 30), by=rai)
    base.refresh_from_db()
    assert base.titre == "Nouveau" and base.fin_prevue == date(2026, 6, 30)
    assert list(base.entites.all()) == [d2]
    assert base.updated_by == rai


def test_modifier_ligne_revalide_les_regles(rai: User) -> None:
    p = programme(annee=2026)
    base = _creer(p, rai)
    with pytest.raises(RegleMetierError) as exc:
        modifier_ligne(base, debut_prevu=date(2025, 12, 31), fin_prevue=date(2026, 1, 5), by=rai)
    assert "debut_prevu" in exc.value.errors
    with pytest.raises(RegleMetierError) as exc:
        modifier_ligne(base, objet_auditable=_objet(), by=rai)
    assert "objet_auditable" in exc.value.errors


def test_ligne_ne_change_pas_de_programme(rai: User) -> None:
    p, autre = programme(annee=2026), programme(annee=2027)
    base = _creer(p, rai)
    with pytest.raises(RegleMetierError) as exc:
        modifier_ligne(base, programme=autre, by=rai)
    assert exc.value.errors["programme"] == ["Une mission prévue ne peut pas changer de programme."]


def test_synthese_comptes_et_sommes(rai: User) -> None:
    p = programme(annee=2026)
    ligne(
        programme=p,
        numero=1,
        type="ASSURANCE",
        debut_prevu=date(2026, 2, 1),
        fin_prevue=date(2026, 2, 5),
        charge_prevue_jours=Decimal("10.5"),
    )
    ligne(
        programme=p,
        numero=2,
        type="CONSEIL",
        debut_prevu=date(2026, 8, 1),
        fin_prevue=date(2026, 8, 5),
        charge_prevue_jours=Decimal("4"),
    )
    ligne(
        programme=p,
        numero=3,
        type="ASSURANCE",
        debut_prevu=date(2026, 9, 30),
        fin_prevue=date(2026, 10, 5),
    )
    ligne(programme=p, numero=4).soft_delete(rai)
    with CaptureQueriesContext(connection) as ctx:
        s = synthese(p)
    assert len(ctx) == 1
    assert s.nb_lignes == 3
    assert s.charge_totale_jours == Decimal("14.5")
    assert s.par_type == {"ASSURANCE": 2, "CONSEIL": 1}
    assert s.par_trimestre == {1: 1, 2: 0, 3: 2, 4: 0}


def test_synthese_vide(rai: User) -> None:
    s = synthese(programme(annee=2026))
    assert s.nb_lignes == 0 and s.charge_totale_jours == Decimal("0")
    assert s.par_trimestre == {1: 0, 2: 0, 3: 0, 4: 0}
