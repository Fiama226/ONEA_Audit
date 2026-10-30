# ruff: noqa: F811
import pytest

from apps.communication.models import EvenementRapport, Rapport, StatutRapport
from apps.communication.recepteurs import _sur_rouverte, connecter
from apps.core.exceptions import RegleMetierError
from apps.missions.models import EtapeMission, Mission, StatutEtape
from apps.missions.services.etapes import renvoyer_etape, rouvrir_etape
from apps.missions.signals import etape_changee
from apps.users.models import User
from tests.communication.support_t8 import (  # noqa: F401
    admin,
    dg,
    rapport_diffuse,
    rapport_soumis_reel,
    rapport_valide,
)


def _etape(rapport: Rapport, numero: int) -> EtapeMission:
    return EtapeMission.objects.get(mission_id=rapport.mission_id, numero=numero)


def test_recepteurs_connectes_une_seule_fois() -> None:
    avant = len(etape_changee.receivers)
    connecter()
    connecter()
    assert len(etape_changee.receivers) == avant


def test_renvoi_generique_de_xviii_renvoie_le_rapport(
    rapport_soumis_reel: Rapport, rai: User
) -> None:
    renvoyer_etape(_etape(rapport_soumis_reel, 18), motif="Revoir la synthèse.", by=rai)
    r = Rapport.objects.get(pk=rapport_soumis_reel.pk)
    assert r.statut == StatutRapport.RENVOYE and r.motif_renvoi == "Revoir la synthèse."
    assert EvenementRapport.objects.filter(rapport=r, type="RENVOYE").count() == 1


def test_reouverture_xvii_reinitialise(rapport_valide: Rapport, rai: User) -> None:
    rouvrir_etape(_etape(rapport_valide, 17), motif="Compléments reçus.", by=rai)
    r = Rapport.objects.get(pk=rapport_valide.pk)
    assert r.statut == StatutRapport.BROUILLON
    assert r.valide_par_id is None and r.valide_le is None
    assert r.confirmation_validation_id is None and r.mode_signature == ""
    evenement = EvenementRapport.objects.get(rapport=r, type="REINITIALISE")
    assert (evenement.statut_avant, evenement.statut_apres) == ("VALIDE", "BROUILLON")
    assert evenement.motif == "Compléments reçus."
    assert _etape(r, 17).statut == StatutEtape.EN_COURS


@pytest.mark.parametrize("numero", [15, 16, 18])
def test_reouverture_reinitialise_quelle_que_soit_l_etape(
    rapport_soumis_reel: Rapport, rai: User, numero: int
) -> None:
    rouvrir_etape(_etape(rapport_soumis_reel, numero), motif="Reprise.", by=rai)
    assert Rapport.objects.get(pk=rapport_soumis_reel.pk).statut == StatutRapport.BROUILLON


def test_reouverture_refusee_apres_diffusion(rapport_diffuse: Rapport, rai: User) -> None:
    # Le récepteur refuse même si le moteur d'étapes laissait passer la réouverture.
    etape = _etape(rapport_diffuse, 17)
    with pytest.raises(RegleMetierError, match="émettez un rapport corrigé"):
        _sur_rouverte(
            EtapeMission, etape=etape, par=rai, type_evenement="ROUVERTE", motif="Reprise."
        )
    assert Rapport.objects.get(pk=rapport_diffuse.pk).statut == StatutRapport.DIFFUSE
    # Le chemin complet échoue aussi (étapes non modifiables une fois la mission diffusée).
    with pytest.raises(RegleMetierError):
        rouvrir_etape(etape, motif="Reprise.", by=rai)
    assert _etape(rapport_diffuse, 17).statut == StatutEtape.TERMINEE


def test_reouverture_sans_rapport_est_sans_effet(
    mission_en_communication: Mission, rai: User
) -> None:
    from tests.missions.conftest import forcer_etapes

    forcer_etapes(mission_en_communication, {15: StatutEtape.TERMINEE})
    etape = mission_en_communication.etapes.get(numero=15)
    rouvrir_etape(etape, motif="Reprise.", by=rai)
    assert mission_en_communication.etapes.get(numero=15).statut == StatutEtape.EN_COURS
