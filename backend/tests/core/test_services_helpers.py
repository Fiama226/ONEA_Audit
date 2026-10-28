from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.http import Http404

from apps.core.exceptions import RegleMetierError
from apps.core.services import appliquer, enregistrer, refuser, relire, verrouiller_actif
from apps.referentiel.models import Direction
from apps.users.models import User
from tests.referentiel.typed import direction as DirectionFactory

pytestmark = pytest.mark.django_db


def test_helpers_deplaces_sans_regression(rai: User) -> None:
    err = refuser("Message.", code="Oups.")
    assert isinstance(err, RegleMetierError)
    assert err.message == "Message." and err.errors == {"code": ["Oups."]}

    d = DirectionFactory()
    assert relire(d) == d
    assert verrouiller_actif(d, "parent") == d

    d.soft_delete(by=rai)
    with pytest.raises(Http404):
        relire(Direction(pk=uuid4()))
    with pytest.raises(RegleMetierError) as e:
        verrouiller_actif(d, "parent")
    assert e.value.errors == {"parent": ["Cet élément a été supprimé."]}


def test_enregistrer_valide_et_trace_l_acteur(rai: User) -> None:
    d = Direction(code="D1", libelle="x" * 500, type="DIRECTION")
    with pytest.raises(RegleMetierError) as e:
        enregistrer(d, by=rai, creation=True)
    assert e.value.message == "Données invalides." and "libelle" in e.value.errors
    d.libelle = "Direction"
    enregistrer(d, by=rai, creation=True)
    d.refresh_from_db()
    assert d.created_by == rai and d.updated_by == rai


def test_enregistrer_controle_optionnel(rai: User) -> None:
    def controle() -> None:
        raise refuser("Refusé.", code="Pris.")

    with pytest.raises(RegleMetierError):
        enregistrer(
            Direction(code="D2", libelle="Direction", type="DIRECTION"),
            by=rai,
            creation=True,
            controle=controle,
        )
    assert not Direction.objects.filter(code="D2").exists()


def test_appliquer_ignore_les_m2m_et_refuse_les_inconnus() -> None:
    obj = SimpleNamespace(libelle="a", directions="intact")
    appliquer(
        obj, {"libelle": "b", "directions": [1]}, {"libelle", "directions"}, m2m={"directions"}
    )
    assert obj.libelle == "b" and obj.directions == "intact"
    with pytest.raises(ValueError):
        appliquer(obj, {"autre": 1}, {"libelle"})
