from decimal import Decimal

import pytest

from apps.accomplissement.models import StatutTest, TestPrevu
from apps.accomplissement.services import synthese as synth
from apps.core.exceptions import RegleMetierError
from apps.missions.models import Mission, StatutEtape
from apps.missions.services.etapes import terminer_etape
from apps.missions.services.livrables import livrables_manquants
from apps.users.models import User
from tests.accomplissement.factories import ProgrammeFactory, TestPrevuFactory
from tests.factories import ObjectifAuditFactory
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def test_terminer_VIII_livrables_manquants(
    mission_viii: Mission, chef: User, auditeur_mission: User
) -> None:
    o1, o2 = mission_viii.objectifs_audit.order_by("numero")
    etape = mission_viii.etapes.get(numero=8)
    assert livrables_manquants(etape) == [
        "Aucun programme de travail pour l'objectif OA-01.",
        "Aucun programme de travail pour l'objectif OA-02.",
    ]
    p1 = ProgrammeFactory(mission=mission_viii, objectif=o1)
    ProgrammeFactory(mission=mission_viii, objectif=o2)
    assert livrables_manquants(etape) == [
        "Aucun test n'est prévu pour l'objectif OA-01.",
        "Aucun test n'est prévu pour l'objectif OA-02.",
    ]
    test = TestPrevuFactory(mission=mission_viii, programme=p1, procedure="  ")
    assert "Le test T-01 n'a pas de procédure." in livrables_manquants(etape)
    TestPrevu.objects.filter(pk=test.pk).update(procedure="Examiner")
    assert livrables_manquants(etape) == ["Aucun test n'est prévu pour l'objectif OA-02."]


def test_terminer_VIII_via_le_moteur(mission_viii: Mission, chef: User) -> None:
    with pytest.raises(RegleMetierError) as e:
        terminer_etape(mission_viii.etapes.get(numero=8), by=chef)
    assert len(e.value.errors["livrables"]) == 2


def test_objectif_non_retenu_ou_test_abandonne_ignores(mission_viii: Mission) -> None:
    o1, o2 = mission_viii.objectifs_audit.order_by("numero")
    forcer_etapes(mission_viii, {7: StatutEtape.EN_COURS})
    mission_viii.objectifs_audit.filter(pk=o2.pk).update(
        retenu=False, motif_non_test="AUTRE", justification="x"
    )
    p1 = ProgrammeFactory(mission=mission_viii, objectif=o1)
    TestPrevuFactory(mission=mission_viii, programme=p1)
    ab = TestPrevuFactory(mission=mission_viii, programme=p1, procedure="")
    TestPrevu.objects.filter(pk=ab.pk).update(statut=StatutTest.ABANDONNE, motif_abandon="x")
    assert livrables_manquants(mission_viii.etapes.get(numero=8)) == []


def test_terminer_IX_sans_auditeur_ni_charge(
    mission_programme_complet: Mission, chef: User
) -> None:
    m = mission_programme_complet
    forcer_etapes(m, {9: StatutEtape.EN_COURS})
    etape = m.etapes.get(numero=9)
    assert livrables_manquants(etape) == []
    t1, t2 = m.tests_prevus.order_by("numero")
    TestPrevu.objects.filter(pk=t1.pk).update(auditeur=None)
    TestPrevu.objects.filter(pk=t2.pk).update(charge_prevue_jours=None)
    assert livrables_manquants(etape) == [
        "Le test T-01 n'a pas d'auditeur.",
        "Le test T-02 n'a pas de charge prévue.",
    ]
    with pytest.raises(RegleMetierError):
        terminer_etape(etape, by=chef)


def test_terminer_X_exige_VIII_et_IX(mission_programme_complet: Mission) -> None:
    m = mission_programme_complet
    etape = m.etapes.get(numero=10)
    assert livrables_manquants(etape) == []
    for numero in (8, 9):
        forcer_etapes(m, {numero: StatutEtape.EN_COURS})
        assert livrables_manquants(etape) == [
            "Terminez les étapes VIII et IX avant de soumettre l'organisation de la mission."
        ]
        forcer_etapes(m, {numero: StatutEtape.A_REVALIDER})
        assert livrables_manquants(etape) == []
        forcer_etapes(m, {numero: StatutEtape.TERMINEE})


def test_depassement_budget_non_bloquant(mission_programme_complet: Mission, chef: User) -> None:
    m = mission_programme_complet
    Mission.objects.filter(pk=m.pk).update(budget_jours=Decimal("2"))
    m.refresh_from_db()
    s = synth.synthese_programme(m)
    assert s.total_charge == Decimal("6.0") and s.depassement_budget is True
    assert livrables_manquants(m.etapes.get(numero=10)) == []
    terminer_etape(m.etapes.get(numero=10), by=chef)  # n'empêche pas de terminer X


def test_references_croisees_dans_controles(mission_viii: Mission) -> None:
    ObjectifAuditFactory()  # autre mission : jamais listé pour celle-ci
    assert len(livrables_manquants(mission_viii.etapes.get(numero=8))) == 2
