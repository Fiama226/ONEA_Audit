import pytest

from apps.analyse.gardes import MSG_VI_NON_VALIDEE
from apps.analyse.models import CouvertureOrdre, VarianteOrientation
from apps.analyse.services import orientation
from apps.core.exceptions import RegleMetierError
from apps.missions.models import Mission, StatutEtape
from apps.users.models import User
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


@pytest.fixture
def mission_vii(mission_en_analyse: Mission) -> Mission:
    forcer_etapes(
        mission_en_analyse,
        {5: StatutEtape.TERMINEE, 6: StatutEtape.VALIDEE, 7: StatutEtape.EN_COURS},
    )
    return mission_en_analyse


def test_obtenir_rapport_absent(mission_vii: Mission) -> None:
    assert orientation.obtenir_rapport(mission_vii) is None


def test_enregistrer_rapport_cree_puis_met_a_jour(mission_vii: Mission, chef: User) -> None:
    rapport = orientation.enregistrer_rapport(mission_vii, by=chef, contexte="Contexte.")
    assert rapport.variante == VarianteOrientation.COMPLET
    assert orientation.obtenir_rapport(mission_vii) == rapport
    mis_a_jour = orientation.enregistrer_rapport(
        mission_vii, by=chef, approche="Approche.", couverture_ordre=CouvertureOrdre.EXACTE
    )
    assert mis_a_jour.pk == rapport.pk
    assert (mis_a_jour.contexte, mis_a_jour.approche) == ("Contexte.", "Approche.")
    assert mis_a_jour.couverture_ordre == CouvertureOrdre.EXACTE


@pytest.mark.parametrize("couverture", [CouvertureOrdre.ELARGIE, CouvertureOrdre.PARTIELLE])
def test_rapport_couverture_partielle_exige_justification(
    mission_vii: Mission, chef: User, couverture: str
) -> None:
    with pytest.raises(RegleMetierError) as exc:
        orientation.enregistrer_rapport(mission_vii, by=chef, couverture_ordre=couverture)
    assert set(exc.value.errors) == {"justification_couverture"}
    assert orientation.obtenir_rapport(mission_vii) is None
    rapport = orientation.enregistrer_rapport(
        mission_vii, by=chef, couverture_ordre=couverture, justification_couverture="Motif."
    )
    assert rapport.couverture_ordre == couverture


def test_rapport_variante_invalide_et_champ_inconnu(mission_vii: Mission, chef: User) -> None:
    with pytest.raises(RegleMetierError) as exc:
        orientation.enregistrer_rapport(mission_vii, by=chef, variante="AUTRE")
    assert "variante" in exc.value.errors
    with pytest.raises(ValueError):
        orientation.enregistrer_rapport(mission_vii, by=chef, inconnu=None)


def test_rapport_refuse_si_vi_non_validee(mission_vii: Mission, chef: User) -> None:
    forcer_etapes(mission_vii, {6: StatutEtape.TERMINEE})
    with pytest.raises(RegleMetierError) as exc:
        orientation.enregistrer_rapport(mission_vii, by=chef, contexte="x")
    assert exc.value.message == MSG_VI_NON_VALIDEE


def test_rapport_refuse_hors_vii_active(mission_vii: Mission, chef: User) -> None:
    forcer_etapes(mission_vii, {7: StatutEtape.TERMINEE})
    with pytest.raises(RegleMetierError):
        orientation.enregistrer_rapport(mission_vii, by=chef, contexte="x")
