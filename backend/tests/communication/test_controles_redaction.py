import pytest

from apps.communication.models import Rapport
from apps.core.exceptions import RegleMetierError
from apps.missions.models import EtapeMission, StatutEtape
from apps.missions.services.etapes import terminer_etape
from apps.users.models import User
from tests.missions.conftest import forcer_etapes


def _livrables(rapport: Rapport, numero: int, chef: User) -> list[str]:
    etape = EtapeMission.objects.get(mission=rapport.mission, numero=numero)
    with pytest.raises(RegleMetierError) as e:
        terminer_etape(etape, by=chef)
    return list(e.value.errors["livrables"])


def test_terminer_xvii_xvi_non_close(rapport_redige: Rapport, chef: User) -> None:
    messages = _livrables(rapport_redige, 17, chef)
    assert "Terminez l'étape XVI avant de terminer la rédaction du rapport." in messages


def test_terminer_xvii_sections_manquantes(rapport_brouillon: Rapport, chef: User) -> None:
    forcer_etapes(rapport_brouillon.mission, {16: StatutEtape.TERMINEE})
    # synthèse et conclusion saisies, appréciation globale absente
    messages = _livrables(rapport_brouillon, 17, chef)
    assert messages == ["Rédigez la synthèse, l'appréciation globale et la conclusion du rapport."]


def test_terminer_xvii_sans_rapport(mission_en_communication, chef: User) -> None:  # type: ignore[no-untyped-def]
    forcer_etapes(mission_en_communication, {16: StatutEtape.TERMINEE})
    etape = EtapeMission.objects.get(mission=mission_en_communication, numero=17)
    with pytest.raises(RegleMetierError) as e:
        terminer_etape(etape, by=chef)
    assert "Rédigez la synthèse" in e.value.errors["livrables"][0]


def test_terminer_xvii_ok(rapport_redige: Rapport, chef: User) -> None:
    forcer_etapes(rapport_redige.mission, {16: StatutEtape.TERMINEE})
    etape = EtapeMission.objects.get(mission=rapport_redige.mission, numero=17)
    assert terminer_etape(etape, by=chef).statut == StatutEtape.TERMINEE


def test_terminer_xvii_synthese_blanche_refusee(rapport_redige: Rapport, chef: User) -> None:
    forcer_etapes(rapport_redige.mission, {16: StatutEtape.TERMINEE})
    Rapport.objects.filter(pk=rapport_redige.pk).update(synthese="   ")
    assert "Rédigez la synthèse" in _livrables(rapport_redige, 17, chef)[0]


def test_terminer_xviii_generique_refuse(rapport_redige: Rapport, chef: User) -> None:
    forcer_etapes(rapport_redige.mission, {15: "TERMINEE", 16: "TERMINEE", 17: "TERMINEE"})
    assert _livrables(rapport_redige, 18, chef) == [
        "Soumettez le rapport depuis l'écran du rapport."
    ]


def test_terminer_xviii_accepte_quand_le_rapport_est_soumis(
    rapport_soumis: Rapport, chef: User
) -> None:
    forcer_etapes(rapport_soumis.mission, {15: "TERMINEE", 16: "TERMINEE", 17: "TERMINEE"})
    etape = EtapeMission.objects.get(mission=rapport_soumis.mission, numero=18)
    assert terminer_etape(etape, by=chef).statut == StatutEtape.TERMINEE
