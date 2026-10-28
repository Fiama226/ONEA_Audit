from datetime import date
from typing import Any, cast

import pytest
from auditlog.models import LogEntry

from apps.core.exceptions import RegleMetierError
from apps.programmation.models import LigneProgramme, ProgrammeAnnuel
from apps.programmation.services import (
    creer_ligne,
    modifier_ligne,
    modifier_programme,
    supprimer_programme,
    valider_programme,
)
from apps.referentiel.models import Direction, ObjetAuditable, Processus
from apps.users.models import User
from tests import factories as f

from .factories import programme


def _direction(**kw: Any) -> Direction:
    return cast(Direction, f.DirectionFactory(**kw))


def _processus(**kw: Any) -> Processus:
    return cast(Processus, f.ProcessusFactory(**kw))


def _objet(**kw: Any) -> ObjetAuditable:
    return cast(ObjetAuditable, f.ObjetAuditableFactory(**kw))


def _creer(p: ProgrammeAnnuel, by: User, **kw: Any) -> LigneProgramme:
    base: dict[str, Any] = {
        "titre": "Achats",
        "type": "ASSURANCE",
        "processus": _processus(),
        "debut_prevu": date(2026, 3, 1),
        "fin_prevue": date(2026, 4, 30),
    }
    base.update(kw)
    return creer_ligne(programme=p, by=by, **base)


def test_entites_historisees_avec_l_acteur_hors_requete(rai: User) -> None:
    base = _creer(programme(annee=2026), rai, entites=[_direction()])
    modifier_ligne(base, entites=[_direction()], by=rai)
    entrees = LogEntry.objects.filter(content_type__model="ligneprogramme", object_pk=str(base.pk))
    m2m = [e for e in entrees if "entites" in e.changes]
    assert len(m2m) >= 2
    assert all(e.actor == rai for e in m2m)


def test_numero_et_statut_refuses_en_422(rai: User) -> None:
    p = programme(annee=2026)
    base = _creer(p, rai)
    with pytest.raises(RegleMetierError) as exc:
        modifier_ligne(base, numero=9, by=rai)
    assert "numero" in exc.value.errors
    with pytest.raises(RegleMetierError) as exc:
        modifier_programme(p, statut="VALIDE", by=rai)
    assert "statut" in exc.value.errors
    with pytest.raises(RegleMetierError) as exc:
        modifier_programme(p, valide_par=rai, by=rai)
    assert "valide_par" in exc.value.errors


def test_changer_processus_en_gardant_l_objet_refuse(rai: User) -> None:
    objet = _objet()
    base = _creer(programme(annee=2026), rai, processus=objet.processus, objet_auditable=objet)
    with pytest.raises(RegleMetierError) as exc:
        modifier_ligne(base, processus=_processus(), by=rai)
    assert "objet_auditable" in exc.value.errors


def test_modifier_ligne_entite_supprimee_refusee(rai: User) -> None:
    base = _creer(programme(annee=2026), rai)
    d = _direction(code="DEG")
    d.soft_delete(rai)
    with pytest.raises(RegleMetierError) as exc:
        modifier_ligne(base, entites=[d], by=rai)
    assert exc.value.errors["entites"] == ["L'entité DEG n'existe plus dans le référentiel."]


def test_supprimer_programme_sans_ligne(rai: User) -> None:
    p = programme(annee=2026)
    supprimer_programme(p, by=rai)
    assert not ProgrammeAnnuel.objects.filter(pk=p.pk).exists()


def test_programme_vide_erreur_non_field(rai: User) -> None:
    with pytest.raises(RegleMetierError) as exc:
        valider_programme(programme(annee=2026), by=rai)
    assert exc.value.errors["non_field_errors"]
