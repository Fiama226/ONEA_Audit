import pytest
from django.db.models import F

from apps.communication.exceptions import RapportFigeError
from apps.communication.models import Rapport, StatutRapport
from apps.core.exceptions import RegleMetierError
from apps.missions.models import Mission, StatutMission
from tests.communication.factories import RapportFactory
from tests.factories import MissionFactory, make_user

pytestmark = pytest.mark.django_db

STATUTS_FIGES = (StatutRapport.SOUMIS, StatutRapport.VALIDE, StatutRapport.DIFFUSE)


@pytest.mark.parametrize("statut", STATUTS_FIGES)
def test_gel_rapport_par_statut(mission_en_communication: Mission, statut: str) -> None:
    rapport = RapportFactory(mission=mission_en_communication, fige=True, statut=statut)
    rapport.synthese = "modifiée"
    with pytest.raises(RapportFigeError) as exc:
        rapport.save()
    assert str(exc.value).startswith("Le rapport est ")
    assert str(exc.value).endswith(" : il ne peut plus être modifié.")
    with pytest.raises(RapportFigeError):
        rapport.save(update_fields=["synthese"])
    with pytest.raises(RapportFigeError):
        Rapport.objects.filter(pk=rapport.pk).update(synthese="x")
    with pytest.raises(RapportFigeError):
        Rapport.objects.filter(pk=rapport.pk).update(appreciation_globale="MAITRISE")
    with pytest.raises(RapportFigeError):
        Rapport.all_objects.bulk_update([rapport], ["synthese"])
    with pytest.raises(RapportFigeError):
        rapport.soft_delete(make_user())
    with pytest.raises(RapportFigeError):  # même un champ métier hors sections
        Rapport.objects.filter(pk=rapport.pk).update(motif_correction="x")
    assert Rapport.objects.get(pk=rapport.pk).synthese == "Synthèse"


def test_message_gel_cite_le_statut(mission_en_communication: Mission) -> None:
    rapport = RapportFactory(mission=mission_en_communication, fige=True)
    rapport.synthese = "x"
    with pytest.raises(RapportFigeError) as exc:
        rapport.save()
    assert exc.value.message == "Le rapport est soumis au RAI : il ne peut plus être modifié."


@pytest.mark.parametrize("statut", [StatutRapport.BROUILLON, StatutRapport.RENVOYE])
def test_redaction_permise_en_brouillon_et_renvoye(
    mission_en_communication: Mission, statut: str
) -> None:
    rapport = RapportFactory(mission=mission_en_communication, statut=statut)
    rapport.synthese = "nouvelle synthèse"
    rapport.appreciation_globale = "PERFECTIBLE"
    rapport.save()
    Rapport.objects.filter(pk=rapport.pk).update(conclusion="nouvelle conclusion")
    rapport.refresh_from_db()
    assert rapport.synthese == "nouvelle synthèse"
    assert rapport.conclusion == "nouvelle conclusion"
    with pytest.raises(RapportFigeError):  # hors sections : pas modifiable en rédaction
        Rapport.objects.filter(pk=rapport.pk).update(cycle=9)
    with pytest.raises(RegleMetierError):
        Rapport.objects.filter(pk=rapport.pk).update(mission=MissionFactory())


def test_expression_refusee_sur_rapport_fige(mission_en_communication: Mission) -> None:
    rapport = RapportFactory(mission=mission_en_communication, fige=True)
    with pytest.raises(RapportFigeError):
        Rapport.objects.filter(pk=rapport.pk).update(cycle=F("cycle") + 1)


def test_redaction_refusee_hors_phase_communication(mission_en_communication: Mission) -> None:
    rapport = RapportFactory(mission=mission_en_communication)
    Mission.objects.filter(pk=mission_en_communication.pk).update(
        statut=StatutMission.RAPPORT_DIFFUSE
    )
    rapport.synthese = "x"
    with pytest.raises(RegleMetierError) as exc:
        rapport.save()
    assert "phase de communication" in exc.value.message
    with pytest.raises(RegleMetierError):
        Rapport.objects.filter(pk=rapport.pk).update(synthese="y")


def test_rapport_corrige_modifiable_sous_mission_diffusee(
    mission_en_communication: Mission,
) -> None:
    ancien = RapportFactory(mission=mission_en_communication, fige=True, statut="REMPLACE")
    corrige = RapportFactory(mission=mission_en_communication, numero_version=2, corrige_de=ancien)
    Mission.objects.filter(pk=mission_en_communication.pk).update(
        statut=StatutMission.RAPPORT_DIFFUSE
    )
    corrige.synthese = "synthèse corrigée"
    corrige.save()
    assert Rapport.objects.get(pk=corrige.pk).synthese == "synthèse corrigée"


def test_garde_lit_l_etat_en_base(mission_en_communication: Mission) -> None:
    rapport = RapportFactory(mission=mission_en_communication)
    perime = Rapport.objects.get(pk=rapport.pk)  # instance restée BROUILLON en mémoire
    Rapport.objects.filter(pk=rapport.pk).update(
        statut=StatutRapport.SOUMIS,
        cycle=1,
        soumis_par=make_user(),
        soumis_le=rapport.created_at,
        instantane_soumis={"a": 1},
        empreinte_soumise="a" * 64,
    )
    perime.synthese = "tardive"
    with pytest.raises(RegleMetierError):
        perime.save()
    assert Rapport.objects.get(pk=rapport.pk).synthese == "Synthèse"


def test_transition_limitee_a_sa_liste_blanche(mission_en_communication: Mission) -> None:
    rapport = RapportFactory(mission=mission_en_communication)
    # Transition inconnue (BROUILLON -> DIFFUSE).
    with pytest.raises(RegleMetierError):
        Rapport.objects.filter(pk=rapport.pk).update(statut=StatutRapport.DIFFUSE)
    # Une transition ne peut pas glisser une modification de section.
    with pytest.raises(RegleMetierError):
        Rapport.objects.filter(pk=rapport.pk).update(
            statut=StatutRapport.SOUMIS,
            synthese="glissée",
            cycle=1,
            empreinte_soumise="a" * 64,
        )
    soumis = {
        "statut": StatutRapport.SOUMIS,
        "cycle": 1,
        "soumis_par": make_user(),
        "soumis_le": rapport.created_at,
        "instantane_soumis": {"a": 1},
        "empreinte_soumise": "a" * 64,
    }
    Rapport.objects.filter(pk=rapport.pk).update(**soumis)
    # SOUMIS -> VALIDE n'écrit pas le motif de renvoi.
    with pytest.raises(RegleMetierError):
        Rapport.objects.filter(pk=rapport.pk).update(statut=StatutRapport.VALIDE, motif_renvoi="x")
    assert Rapport.objects.get(pk=rapport.pk).statut == StatutRapport.SOUMIS


def test_creation_en_masse_sans_upsert(mission_en_communication: Mission) -> None:
    rapport = RapportFactory(mission=mission_en_communication)
    with pytest.raises(RegleMetierError):
        Rapport.all_objects.bulk_create(
            [rapport], update_conflicts=True, update_fields=["synthese"], unique_fields=["id"]
        )
