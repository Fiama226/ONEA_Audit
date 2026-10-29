import pytest

from apps.accomplissement.models import InstantaneProgramme
from apps.core.exceptions import RegleMetierError
from apps.missions.models import Mission
from apps.missions.services.etapes import terminer_etape, valider_etape
from apps.signatures.services import empreinte
from apps.users.models import User

pytestmark = pytest.mark.django_db


def test_validation_X_cree_un_instantane_verifiable(
    mission_programme_complet: Mission, rai: User, chef: User
) -> None:
    m = mission_programme_complet
    terminer_etape(m.etapes.get(numero=10), by=chef)
    assert InstantaneProgramme.objects.count() == 0  # seulement à la validation
    valider_etape(m.etapes.get(numero=10), by=rai)
    inst = InstantaneProgramme.objects.get(mission=m)
    assert inst.empreinte == empreinte("programme", inst.donnees)
    assert inst.valide_par == rai
    assert Mission.objects.get(pk=m.pk).statut == "EN_ACCOMPLISSEMENT"
    assert {t["code"] for t in inst.donnees["tests"]} == {"T-01", "T-02"}
    assert (
        inst.donnees["synthese"]["total_charge"] == "6.0"
        or float(inst.donnees["synthese"]["total_charge"]) == 6.0
    )


def test_echec_de_l_instantane_annule_la_validation(
    mission_programme_complet: Mission,
    rai: User,
    chef: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    m = mission_programme_complet
    terminer_etape(m.etapes.get(numero=10), by=chef)

    def echec(*args: object, **kwargs: object) -> None:
        raise RuntimeError("instantané")

    monkeypatch.setattr("apps.accomplissement.recepteurs.creer_instantane", echec)
    with pytest.raises(RuntimeError):
        valider_etape(m.etapes.get(numero=10), by=rai)
    assert m.etapes.get(numero=10).statut == "TERMINEE"


def test_instantane_immuable(mission_programme_complet: Mission, rai: User, chef: User) -> None:
    m = mission_programme_complet
    terminer_etape(m.etapes.get(numero=10), by=chef)
    valider_etape(m.etapes.get(numero=10), by=rai)
    inst = InstantaneProgramme.objects.get(mission=m)
    inst.donnees = {}
    with pytest.raises(RegleMetierError):
        inst.save()
