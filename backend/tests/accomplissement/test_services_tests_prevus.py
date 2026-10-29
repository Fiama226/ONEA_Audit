from datetime import date
from decimal import Decimal

import pytest
from rest_framework.exceptions import PermissionDenied

from apps.accomplissement.models import (
    FicheDeTest,
    InstantaneProgramme,
    ProgrammeDeTravail,
    StatutTest,
    TestPrevu,
)
from apps.accomplissement.services import tests_prevus as svc
from apps.core.exceptions import RegleMetierError
from apps.missions.exceptions import EtapeCloseError
from apps.missions.models import Mission, StatutEtape
from apps.missions.services.etapes import rouvrir_etape, terminer_etape, valider_etape
from apps.users.models import Role, User
from tests.accomplissement.factories import FicheFactory
from tests.factories import RisqueMissionFactory, make_user
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def _creer(programme: ProgrammeDeTravail, chef: User, **kw: object) -> TestPrevu:
    return svc.creer_test(
        programme, libelle="Vérifier", nature="EXAMEN_DOCUMENTAIRE", by=chef, **kw
    )


def test_creer_test_attribue_un_code(programme_viii: ProgrammeDeTravail, chef: User) -> None:
    t1 = _creer(programme_viii, chef)
    t2 = _creer(programme_viii, chef)
    assert (t1.code, t2.code) == ("T-01", "T-02")
    assert t1.mission_id == programme_viii.mission_id


def test_code_jamais_reattribue(programme_viii: ProgrammeDeTravail, chef: User) -> None:
    t1 = _creer(programme_viii, chef)
    svc.supprimer_test(t1, by=chef)
    assert _creer(programme_viii, chef).code == "T-02"


def test_echec_de_validation_ne_brule_pas_de_numero(
    programme_viii: ProgrammeDeTravail, chef: User
) -> None:
    with pytest.raises(RegleMetierError):
        svc.creer_test(programme_viii, libelle="  ", nature="AUTRE", by=chef)
    with pytest.raises(RegleMetierError):
        svc.creer_test(programme_viii, libelle="x", nature="INCONNUE", by=chef)
    assert TestPrevu.all_objects.count() == 0
    assert _creer(programme_viii, chef).code == "T-01"


def test_auditeur_hors_equipe_refuse(
    mission_viii: Mission, programme_viii: ProgrammeDeTravail, chef: User
) -> None:
    forcer_etapes(mission_viii, {9: StatutEtape.EN_COURS})
    etranger = make_user(Role.AUDITEUR)
    with pytest.raises(RegleMetierError) as e:
        _creer(programme_viii, chef, auditeur=etranger)
    assert e.value.errors["auditeur"] == ["L'auditeur doit être un intervenant de la mission."]
    assert TestPrevu.all_objects.count() == 0


def test_references_croisees_refusees(programme_viii: ProgrammeDeTravail, chef: User) -> None:
    forcer_etapes(programme_viii.mission, {4: StatutEtape.EN_COURS})
    risque_autre = RisqueMissionFactory()
    with pytest.raises(RegleMetierError) as e:
        _creer(programme_viii, chef, risque_mission=risque_autre)
    assert e.value.errors["risque_mission"] == ["Ce risque n'appartient pas à la mission."]
    ok = RisqueMissionFactory(mission=programme_viii.mission)
    forcer_etapes(programme_viii.mission, {4: StatutEtape.VALIDEE})
    assert _creer(programme_viii, chef, risque_mission=ok).risque_mission_id == ok.pk


def test_valeurs_negatives_ou_dates_incoherentes_refusees(
    programme_viii: ProgrammeDeTravail, chef: User
) -> None:
    forcer_etapes(programme_viii.mission, {9: StatutEtape.EN_COURS})
    with pytest.raises(RegleMetierError) as e:
        _creer(programme_viii, chef, charge_prevue_jours=Decimal("-1"))
    assert "charge_prevue_jours" in e.value.errors
    with pytest.raises(RegleMetierError) as e:
        _creer(
            programme_viii,
            chef,
            date_debut_prevue=date(2026, 5, 2),
            date_fin_prevue=date(2026, 5, 1),
        )
    assert "date_fin_prevue" in e.value.errors
    assert TestPrevu.all_objects.count() == 0


def test_groupes_de_champs_d5(
    mission_viii: Mission, programme_viii: ProgrammeDeTravail, chef: User
) -> None:
    test = _creer(programme_viii, chef)
    # IX pas commencée : les ressources sont refusées, le contenu passe.
    with pytest.raises(RegleMetierError, match="Commencez l'étape IX"):
        svc.modifier_test(test, by=chef, charge_prevue_jours=Decimal("2"))
    svc.modifier_test(test, by=chef, procedure="P")
    forcer_etapes(mission_viii, {8: StatutEtape.TERMINEE, 9: StatutEtape.EN_COURS})
    svc.modifier_test(test, by=chef, auditeur=chef, charge_prevue_jours=Decimal("2"))
    with pytest.raises(EtapeCloseError) as e:
        svc.modifier_test(test, by=chef, procedure="Q")
    assert e.value.romain == "VIII"
    forcer_etapes(mission_viii, {9: StatutEtape.TERMINEE})
    with pytest.raises(EtapeCloseError) as e:
        svc.modifier_test(test, by=chef, charge_prevue_jours=Decimal("3"))
    assert e.value.romain == "IX"
    test.refresh_from_db()
    assert test.charge_prevue_jours == Decimal("2.0")


def test_ressources_reservees_au_chef_superviseur_rai(
    mission_viii: Mission,
    programme_viii: ProgrammeDeTravail,
    chef: User,
    auditeur_mission: User,
) -> None:
    forcer_etapes(mission_viii, {9: StatutEtape.EN_COURS})
    test = _creer(programme_viii, chef)
    with pytest.raises(PermissionDenied):
        svc.modifier_test(test, by=auditeur_mission, charge_prevue_jours=Decimal("2"))
    svc.modifier_test(test, by=auditeur_mission, procedure="ok")  # le contenu : contributeur


def test_supprimer_test_refuse_si_fiche(
    mission_viii: Mission, programme_viii: ProgrammeDeTravail, chef: User
) -> None:
    test = _creer(programme_viii, chef)
    FicheFactory(mission=mission_viii, test=test)
    with pytest.raises(RegleMetierError, match="fiche"):
        svc.supprimer_test(test, by=chef)
    assert TestPrevu.objects.filter(pk=test.pk).exists()


def test_complementaire_seulement_en_XII(
    mission_programme_complet: Mission, chef: User, rai: User, auditeur_mission: User
) -> None:
    programme = mission_programme_complet.programmes.first()
    with pytest.raises(RegleMetierError, match="Commencez l'étape XII"):
        svc.creer_test_complementaire(programme, libelle="Compl.", nature="AUTRE", by=chef)
    forcer_etapes(mission_programme_complet, {12: StatutEtape.EN_COURS})
    with pytest.raises(PermissionDenied):
        svc.creer_test_complementaire(
            programme, libelle="Compl.", nature="AUTRE", by=auditeur_mission
        )
    t = svc.creer_test_complementaire(programme, libelle="Compl.", nature="AUTRE", by=chef)
    assert t.complementaire and t.code == "T-03"
    t2 = svc.creer_test_complementaire(
        programme, libelle="Compl. 2", nature="AUTRE", by=rai, charge_prevue_jours=Decimal("1")
    )
    assert t2.code == "T-04"
    forcer_etapes(mission_programme_complet, {12: StatutEtape.TERMINEE})
    with pytest.raises(EtapeCloseError):
        svc.creer_test_complementaire(programme, libelle="Compl.", nature="AUTRE", by=chef)


def test_abandon_exige_motif(mission_programme_complet: Mission, chef: User) -> None:
    forcer_etapes(mission_programme_complet, {12: StatutEtape.EN_COURS})
    test = mission_programme_complet.tests_prevus.first()
    for motif in ("", "   "):
        with pytest.raises(RegleMetierError) as e:
            svc.abandonner_test(test, motif=motif, by=chef)
        assert e.value.errors["motif"] == ["Le motif est obligatoire."]
    svc.abandonner_test(test, motif="Non testable sur la période", by=chef)
    test.refresh_from_db()
    assert test.statut == StatutTest.ABANDONNE
    with pytest.raises(RegleMetierError):
        svc.abandonner_test(test, motif="encore", by=chef)


def test_abandon_hors_xii_ou_fiche_validee(mission_programme_complet: Mission, chef: User) -> None:
    test = mission_programme_complet.tests_prevus.first()
    with pytest.raises(RegleMetierError, match="Commencez l'étape XII"):
        svc.abandonner_test(test, motif="x", by=chef)
    forcer_etapes(mission_programme_complet, {12: StatutEtape.EN_COURS})
    fiche = FicheFactory(mission=mission_programme_complet, test=test)
    FicheDeTest.objects.filter(pk=fiche.pk).update(conclusion="SATISFAISANT", statut="VALIDE")
    with pytest.raises(RegleMetierError, match="validée"):
        svc.abandonner_test(test, motif="x", by=chef)


def test_modifier_test_abandonne_refuse(mission_programme_complet: Mission, chef: User) -> None:
    forcer_etapes(mission_programme_complet, {12: StatutEtape.EN_COURS})
    test = mission_programme_complet.tests_prevus.first()
    svc.abandonner_test(test, motif="x", by=chef)
    test.refresh_from_db()
    with pytest.raises(RegleMetierError):
        svc.modifier_test(test, by=chef, procedure="y")


def test_rouvrir_VIII_puis_modifier(
    mission_programme_complet: Mission, chef: User, rai: User
) -> None:
    m = mission_programme_complet
    terminer_etape(m.etapes.get(numero=10), by=chef)
    valider_etape(m.etapes.get(numero=10), by=rai)
    assert InstantaneProgramme.objects.filter(mission=m).count() == 1
    rouvrir_etape(m.etapes.get(numero=8), motif="Ajout d'un test", by=rai)
    assert m.etapes.get(numero=10).statut == StatutEtape.A_REVALIDER
    test = m.tests_prevus.first()
    svc.modifier_test(test, by=chef, procedure="Procédure révisée")
    terminer_etape(m.etapes.get(numero=8), by=chef)
    valider_etape(m.etapes.get(numero=10), by=rai)
    assert InstantaneProgramme.objects.filter(mission=m).count() == 2
    dernier = InstantaneProgramme.objects.filter(mission=m).order_by("-valide_le").first()
    assert "Procédure révisée" in str(dernier.donnees)
