import pytest
from django.core.exceptions import PermissionDenied

from apps.communication.models import EvenementRapport, Rapport, StatutRapport
from apps.communication.services.soumission import soumettre_rapport
from apps.constats.models import Constat
from apps.core.exceptions import RegleMetierError
from apps.missions.models import EtapeMission, Mission, StatutEtape, StatutMission
from apps.signatures.services import empreinte
from apps.users.models import User
from tests.communication.factories import RapportFactory
from tests.missions.conftest import forcer_etapes

XV_A_XVII = {15: StatutEtape.TERMINEE, 16: StatutEtape.TERMINEE, 17: StatutEtape.TERMINEE}


def test_soumission_termine_xviii_et_fige(rapport_redige: Rapport, chef: User) -> None:
    forcer_etapes(rapport_redige.mission, XV_A_XVII)
    r = soumettre_rapport(rapport_redige, by=chef)
    assert r.statut == "SOUMIS" and r.cycle == 1
    assert r.empreinte_soumise == empreinte("rapport", r.instantane_soumis)
    assert r.mission.etapes.get(numero=18).statut == "TERMINEE"
    en_base = Rapport.objects.get(pk=r.pk)
    assert en_base.instantane_soumis == r.instantane_soumis
    assert en_base.empreinte_soumise == empreinte("rapport", en_base.instantane_soumis)
    assert en_base.soumis_par == chef and en_base.soumis_le is not None
    assert [c["reference"] for c in en_base.instantane_soumis["constats"]]
    evenement = EvenementRapport.objects.get(rapport=r, type="SOUMIS")
    assert (evenement.statut_avant, evenement.statut_apres) == ("BROUILLON", "SOUMIS")


def test_soumission_demarre_xviii_si_a_faire(rapport_redige: Rapport, chef: User) -> None:
    forcer_etapes(rapport_redige.mission, {**XV_A_XVII, 18: StatutEtape.A_FAIRE})
    soumettre_rapport(rapport_redige, by=chef)
    etape = EtapeMission.objects.get(mission=rapport_redige.mission, numero=18)
    assert etape.statut == StatutEtape.TERMINEE and etape.date_debut_reelle is not None


def test_soumettre_exige_xvii_close(rapport_redige: Rapport, chef: User) -> None:
    forcer_etapes(rapport_redige.mission, {15: "TERMINEE", 16: "TERMINEE"})
    with pytest.raises(RegleMetierError, match="Terminez l'étape XVII avant de soumettre"):
        soumettre_rapport(rapport_redige, by=chef)
    rapport_redige.refresh_from_db()
    assert rapport_redige.statut == StatutRapport.BROUILLON and rapport_redige.cycle == 0


def test_seul_le_chef_soumet(rapport_redige: Rapport, chef: User, rai: User) -> None:
    forcer_etapes(rapport_redige.mission, XV_A_XVII)
    with pytest.raises(PermissionDenied):
        soumettre_rapport(rapport_redige, by=rai)
    rapport_redige.refresh_from_db()
    assert rapport_redige.statut == StatutRapport.BROUILLON


def test_un_auditeur_simple_ne_soumet_pas(
    rapport_redige: Rapport, chef: User, auditeur_mission: User
) -> None:
    forcer_etapes(rapport_redige.mission, XV_A_XVII)
    with pytest.raises(PermissionDenied):
        soumettre_rapport(rapport_redige, by=auditeur_mission)


def test_soumission_refusee_si_deja_soumis(rapport_soumis: Rapport, chef: User) -> None:
    forcer_etapes(rapport_soumis.mission, XV_A_XVII)
    with pytest.raises(RegleMetierError, match="n'est pas en rédaction"):
        soumettre_rapport(rapport_soumis, by=chef)


def test_xviii_non_terminee_si_livrable_manquant_annule_tout(
    rapport_redige: Rapport, chef: User
) -> None:
    """XVIII renvoyée puis soumission : la transaction entière est annulée si XVIII échoue."""
    forcer_etapes(rapport_redige.mission, {**XV_A_XVII, 18: StatutEtape.TERMINEE})
    with pytest.raises(RegleMetierError):
        soumettre_rapport(rapport_redige, by=chef)
    rapport_redige.refresh_from_db()
    assert rapport_redige.statut == StatutRapport.BROUILLON and rapport_redige.cycle == 0
    assert not EvenementRapport.objects.filter(rapport=rapport_redige, type="SOUMIS").exists()


def test_rapport_corrige_ne_touche_aucune_etape(
    constat_valide: Constat, mission_en_communication: Mission, chef: User
) -> None:
    ancien = RapportFactory(mission=mission_en_communication, statut=StatutRapport.REMPLACE)
    forcer_etapes(mission_en_communication, {**XV_A_XVII, 18: StatutEtape.VALIDEE})
    Mission.objects.filter(pk=mission_en_communication.pk).update(
        statut=StatutMission.RAPPORT_DIFFUSE
    )
    mission_en_communication.refresh_from_db()
    corrige = RapportFactory(
        mission=mission_en_communication,
        numero_version=2,
        corrige_de=ancien,
        motif_correction="Erreur matérielle",
        appreciation_globale="PERFECTIBLE",
    )
    r = soumettre_rapport(corrige, by=chef)
    assert r.statut == "SOUMIS" and r.cycle == 1
    assert r.instantane_soumis["rapport"]["corrige_de"] == 1
    assert EtapeMission.objects.get(mission=r.mission, numero=18).statut == StatutEtape.VALIDEE
