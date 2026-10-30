from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied

from apps.core.exceptions import RegleMetierError
from apps.missions.models import Mission
from apps.notifications.models import Notification, TypeNotification
from apps.suivi.models import (
    EvenementSuivi,
    StatutDemandeReport,
    StatutSuivi,
    SuiviAction,
    TypeEvenementSuivi,
)
from apps.suivi.services.reports import accepter_report, demander_report, refuser_report
from apps.users.models import User


def suivi_de(user: User) -> SuiviAction:
    suivi: SuiviAction = SuiviAction.objects.filter(responsable=user).first()
    return suivi


def test_accepter_report_ouvre_un_nouveau_cycle(
    mission_en_suivi: Mission, responsable: User, rai: User
) -> None:
    s = suivi_de(responsable)
    ancienne = s.echeance
    d = demander_report(
        s, nouvelle_echeance=ancienne + timedelta(days=30), motif="Budget 2027", by=responsable
    )
    accepter_report(d, by=rai)
    s.refresh_from_db()
    assert (s.echeance, s.nombre_reports, s.echeance_initiale) == (
        ancienne + timedelta(days=30),
        1,
        ancienne,
    )
    d.refresh_from_db()
    assert d.statut == StatutDemandeReport.ACCEPTEE and d.decidee_par == rai and d.decidee_le
    types = set(EvenementSuivi.objects.filter(suivi=s).values_list("type", flat=True))
    assert {TypeEvenementSuivi.REPORT_DEMANDE, TypeEvenementSuivi.REPORT_ACCEPTE} <= types
    assert Notification.objects.filter(
        destinataire=rai, type=TypeNotification.REPORT_DEMANDE
    ).exists()
    assert Notification.objects.filter(
        destinataire=responsable, type=TypeNotification.REPORT_DECIDE
    ).exists()


def test_refuser_report_laisse_l_echeance(
    mission_en_suivi: Mission, responsable: User, rai: User
) -> None:
    s = suivi_de(responsable)
    ancienne = s.echeance
    d = demander_report(
        s, nouvelle_echeance=ancienne + timedelta(days=10), motif="Retard", by=responsable
    )
    refuser_report(d, commentaire="Trop tardif", by=rai)
    s.refresh_from_db()
    assert (s.echeance, s.nombre_reports) == (ancienne, 0)
    d.refresh_from_db()
    assert d.statut == StatutDemandeReport.REFUSEE and d.commentaire_decision == "Trop tardif"
    # Après décision, une nouvelle demande est de nouveau possible.
    demander_report(
        s, nouvelle_echeance=ancienne + timedelta(days=20), motif="Autre", by=responsable
    )


def test_un_seul_report_en_attente(mission_en_suivi: Mission, responsable: User) -> None:
    s = suivi_de(responsable)
    demander_report(s, nouvelle_echeance=s.echeance + timedelta(days=5), motif="a", by=responsable)
    with pytest.raises(RegleMetierError) as exc:
        demander_report(
            s, nouvelle_echeance=s.echeance + timedelta(days=9), motif="b", by=responsable
        )
    assert exc.value.message == "Une demande de report est déjà en attente pour cette action."


def test_report_date_anterieure_refusee(mission_en_suivi: Mission, responsable: User) -> None:
    s = suivi_de(responsable)
    for date in (s.echeance, s.echeance - timedelta(days=1)):
        with pytest.raises(RegleMetierError) as exc:
            demander_report(s, nouvelle_echeance=date, motif="x", by=responsable)
        assert "nouvelle_echeance" in exc.value.errors
    with pytest.raises(RegleMetierError):
        demander_report(
            s, nouvelle_echeance=s.echeance + timedelta(days=1), motif="  ", by=responsable
        )


def test_refus_exige_commentaire(mission_en_suivi: Mission, responsable: User, rai: User) -> None:
    s = suivi_de(responsable)
    d = demander_report(
        s, nouvelle_echeance=s.echeance + timedelta(days=5), motif="a", by=responsable
    )
    with pytest.raises(RegleMetierError):
        refuser_report(d, commentaire="  ", by=rai)
    d.refresh_from_db()
    assert d.statut == StatutDemandeReport.EN_ATTENTE


def test_report_reserve_au_responsable_ou_rai(
    mission_en_suivi: Mission,
    responsable: User,
    rai: User,
    autre_audite: User,
    autre_auditeur: User,
    dg: User,
) -> None:
    s = suivi_de(responsable)
    nouvelle = s.echeance + timedelta(days=5)
    for intrus in (autre_audite, autre_auditeur, dg):
        with pytest.raises(PermissionDenied):
            demander_report(s, nouvelle_echeance=nouvelle, motif="x", by=intrus)
    d = demander_report(s, nouvelle_echeance=nouvelle, motif="x", by=responsable)
    for intrus in (
        responsable,
        autre_audite,
        autre_auditeur,
        dg,
    ):  # seule la décision du RAI compte
        with pytest.raises(PermissionDenied):
            accepter_report(d, by=intrus)
        with pytest.raises(PermissionDenied):
            refuser_report(d, commentaire="non", by=intrus)
    accepter_report(d, by=rai)


def test_report_par_le_rai_pour_le_compte(
    mission_en_suivi: Mission, responsable: User, rai: User
) -> None:
    s = suivi_de(responsable)
    demander_report(s, nouvelle_echeance=s.echeance + timedelta(days=5), motif="Budget", by=rai)
    evenement = EvenementSuivi.objects.get(suivi=s, type=TypeEvenementSuivi.REPORT_DEMANDE)
    assert evenement.pour_compte_de == responsable
    assert evenement.texte.startswith("Saisi par le RAI pour le compte de ")


@pytest.mark.parametrize(
    "statut",
    [StatutSuivi.REALISEE, StatutSuivi.VERIFIEE, StatutSuivi.CLOTUREE, StatutSuivi.ABANDON_PROPOSE],
)
def test_report_refuse_si_action_realisee(
    mission_en_suivi: Mission, responsable: User, statut: str
) -> None:
    s = suivi_de(responsable)
    SuiviAction.objects.filter(pk=s.pk).update(statut=statut, justification_abandon="x")
    s.refresh_from_db()
    with pytest.raises(RegleMetierError):
        demander_report(
            s, nouvelle_echeance=s.echeance + timedelta(days=5), motif="x", by=responsable
        )


def test_acceptation_refusee_si_action_declaree_entre_temps(
    mission_en_suivi: Mission, responsable: User, rai: User
) -> None:
    s = suivi_de(responsable)
    d = demander_report(
        s, nouvelle_echeance=s.echeance + timedelta(days=5), motif="x", by=responsable
    )
    SuiviAction.objects.filter(pk=s.pk).update(statut=StatutSuivi.REALISEE)
    with pytest.raises(RegleMetierError):
        accepter_report(d, by=rai)
    refuser_report(d, commentaire="Action déjà réalisée", by=rai)  # le refus reste possible


def test_decision_unique(mission_en_suivi: Mission, responsable: User, rai: User) -> None:
    s = suivi_de(responsable)
    d = demander_report(
        s, nouvelle_echeance=s.echeance + timedelta(days=5), motif="x", by=responsable
    )
    accepter_report(d, by=rai)
    with pytest.raises(RegleMetierError):
        accepter_report(d, by=rai)
    s.refresh_from_db()
    assert s.nombre_reports == 1
