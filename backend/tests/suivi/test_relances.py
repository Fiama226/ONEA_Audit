"""Relances automatiques J-15 / J / J+15 : planification, regroupement, envoi (lot 8, T7)."""

import re
from datetime import date, timedelta
from io import StringIO
from smtplib import SMTPException
from typing import Any

import pytest
from django.core import mail
from django.core.management import call_command
from django.test import override_settings

from apps.missions.models import Mission, StatutEtape, StatutMission
from apps.notifications.models import Notification, TypeNotification
from apps.recommandations.models import Action
from apps.suivi import relances, tasks
from apps.suivi.models import (
    PalierRelance,
    Relance,
    StatutRelance,
    StatutSuivi,
    SuiviAction,
)
from apps.users.models import Role, User
from tests.factories import make_user
from tests.missions.conftest import forcer_etapes
from tests.recommandations.factories import ActionFactory
from tests.suivi.factories import SuiviActionFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def mission_suivie(mission_en_suivi: Mission, chef: User) -> Mission:
    Mission.objects.filter(pk=mission_en_suivi.pk).update(statut=StatutMission.EN_SUIVI)
    mission_en_suivi.refresh_from_db()
    return mission_en_suivi


def suivi_relancable(
    mission: Mission, responsable: User, echeance: date, **action: Any
) -> SuiviAction:
    modele = Action.objects.filter(mission=mission).first()
    assert modele is not None
    # L'étape XVI (plan d'actions) est validée : on la rouvre le temps de créer l'action.
    forcer_etapes(mission, {16: StatutEtape.EN_COURS})
    a = ActionFactory(
        recommandation=modele.recommandation,
        mission=mission,
        responsable=responsable,
        echeance=echeance,
        **action,
    )
    forcer_etapes(mission, {16: StatutEtape.VALIDEE})
    return SuiviActionFactory(action=a)


def lancer(jour: date) -> None:
    relances.executer_relances(jour)


@pytest.mark.parametrize(
    ("decalage", "attendu"),
    [
        (-16, None),
        (-15, PalierRelance.J_MOINS_15),
        (-1, PalierRelance.J_MOINS_15),
        (0, PalierRelance.J),
        (14, PalierRelance.J),
        (15, PalierRelance.J_PLUS_15),
        (90, PalierRelance.J_PLUS_15),
    ],
)
def test_palier_atteint_bornes(decalage: int, attendu: str | None) -> None:
    echeance = date(2026, 11, 13)
    assert relances.palier_atteint(echeance, echeance + timedelta(days=decalage)) == attendu


def test_rattrapage_palier_le_plus_haut(
    mission_suivie: Mission, responsable: User, chef: User, mailoutbox: list[Any]
) -> None:
    s = suivi_relancable(mission_suivie, responsable, date(2026, 10, 1))
    lancer(date(2026, 10, 20))
    assert list(s.relances.values_list("palier", flat=True)) == ["J_PLUS_15"]
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == [responsable.email]
    assert mailoutbox[0].cc == [chef.email]
    relance = s.relances.get()
    assert relance.statut == StatutRelance.ENVOYEE and relance.envoyee_le is not None
    assert relance.copie == chef


def test_pas_de_copie_avant_j_plus_15(
    mission_suivie: Mission, responsable: User, chef: User, mailoutbox: list[Any]
) -> None:
    suivi_relancable(mission_suivie, responsable, date(2026, 10, 20))
    lancer(date(2026, 10, 20))
    assert len(mailoutbox) == 1 and mailoutbox[0].cc == []


def test_copie_ignoree_si_chef_sans_adresse(
    mission_suivie: Mission, responsable: User, chef: User, mailoutbox: list[Any]
) -> None:
    User.objects.filter(pk=chef.pk).update(email="")
    suivi_relancable(mission_suivie, responsable, date(2026, 10, 1))
    lancer(date(2026, 10, 20))
    assert len(mailoutbox) == 1 and mailoutbox[0].cc == []


def test_relances_idempotentes(
    mission_suivie: Mission, responsable: User, mailoutbox: list[Any]
) -> None:
    s = suivi_relancable(mission_suivie, responsable, date(2026, 11, 13))
    for _ in range(2):
        lancer(date(2026, 10, 29))
    assert s.relances.count() == 1 and len(mailoutbox) == 1


def test_report_ouvre_un_nouveau_cycle(
    mission_suivie: Mission, responsable: User, mailoutbox: list[Any]
) -> None:
    s = suivi_relancable(mission_suivie, responsable, date(2026, 11, 13))
    lancer(date(2026, 10, 29))
    SuiviAction.objects.filter(pk=s.pk).update(echeance=date(2026, 12, 13))
    lancer(date(2026, 11, 29))
    refs = sorted(s.relances.values_list("echeance_reference", flat=True))
    assert refs == [date(2026, 11, 13), date(2026, 12, 13)]
    assert len(mailoutbox) == 2


def test_action_close_avant_envoi_non_relancee(
    mission_suivie: Mission, responsable: User, mailoutbox: list[Any]
) -> None:
    s = suivi_relancable(mission_suivie, responsable, date(2026, 11, 13))
    relances.planifier_relances(date(2026, 10, 29))
    relance = s.relances.get()
    SuiviAction.objects.filter(pk=s.pk).update(statut=StatutSuivi.CLOTUREE)
    lancer(date(2026, 10, 29))
    # Envoi direct d'un lot périmé : écarté sans rien envoyer.
    relances.envoyer_lot(responsable.pk, [str(relance.pk)])
    relance.refresh_from_db()
    assert relance.statut == StatutRelance.A_ENVOYER and relance.tentatives == 0
    assert mailoutbox == []


def test_echeance_modifiee_avant_envoi_ecarte(
    mission_suivie: Mission, responsable: User, mailoutbox: list[Any]
) -> None:
    s = suivi_relancable(mission_suivie, responsable, date(2026, 11, 13))
    relances.planifier_relances(date(2026, 10, 29))
    relance = s.relances.get()
    SuiviAction.objects.filter(pk=s.pk).update(echeance=date(2027, 1, 13))
    relances.envoyer_lot(responsable.pk, [str(relance.pk)])
    relance.refresh_from_db()
    assert relance.statut == StatutRelance.A_ENVOYER and mailoutbox == []


def test_responsable_change_ne_recoit_pas(
    mission_suivie: Mission, responsable: User, mailoutbox: list[Any]
) -> None:
    s = suivi_relancable(mission_suivie, responsable, date(2026, 11, 13))
    relances.planifier_relances(date(2026, 10, 29))
    relance = s.relances.get()
    SuiviAction.objects.filter(pk=s.pk).update(responsable=make_user(Role.AUDITE))
    relances.envoyer_lot(responsable.pk, [str(relance.pk)])
    assert mailoutbox == []


def test_destinataire_incoherent_refuse(
    mission_suivie: Mission, responsable: User, mailoutbox: list[Any]
) -> None:
    s = suivi_relancable(mission_suivie, responsable, date(2026, 11, 13))
    relances.planifier_relances(date(2026, 10, 29))
    relance = s.relances.get()
    autre = make_user(Role.AUDITE)
    relances.envoyer_lot(autre.pk, [str(relance.pk)])
    assert mailoutbox == []


def test_sans_adresse_et_desactive(
    mission_suivie: Mission, responsable: User, mailoutbox: list[Any]
) -> None:
    sans = make_user(Role.AUDITE, email="")
    desactive = make_user(Role.AUDITE, is_active=False)
    a = suivi_relancable(mission_suivie, sans, date(2026, 11, 13))
    b = suivi_relancable(mission_suivie, desactive, date(2026, 11, 13))
    lancer(date(2026, 10, 29))
    assert a.relances.get().statut == StatutRelance.SANS_ADRESSE
    assert b.relances.count() == 0
    assert mailoutbox == []


@pytest.mark.parametrize("statut", [StatutMission.CLOTUREE, StatutMission.SUSPENDUE])
def test_mission_cloturee_ou_suspendue_non_relancee(
    mission_suivie: Mission, responsable: User, statut: str, mailoutbox: list[Any]
) -> None:
    s = suivi_relancable(mission_suivie, responsable, date(2026, 11, 13))
    Mission.objects.filter(pk=mission_suivie.pk).update(statut=statut)
    lancer(date(2026, 10, 29))
    assert s.relances.count() == 0 and mailoutbox == []


def test_interrupteur_relances_actives(
    mission_suivie: Mission, responsable: User, mailoutbox: list[Any], settings: Any
) -> None:
    s = suivi_relancable(mission_suivie, responsable, date.today())
    settings.RELANCES_ACTIVES = False
    tasks.relances_quotidiennes()
    assert s.relances.count() == 0 and mailoutbox == []
    settings.RELANCES_ACTIVES = True
    tasks.relances_quotidiennes()
    assert s.relances.count() == 1 and len(mailoutbox) == 1


def test_un_email_par_destinataire(
    mission_suivie: Mission, responsable: User, mailoutbox: list[Any]
) -> None:
    for libelle in ("Premier chantier", "Deuxième chantier", "Troisième chantier"):
        suivi_relancable(mission_suivie, responsable, date(2026, 11, 13), libelle=libelle)
    lancer(date(2026, 10, 29))
    assert len(mailoutbox) == 1
    corps = mailoutbox[0].body
    assert all(x in corps for x in ("Premier", "Deuxième", "Troisième"))
    assert "3 action(s) à traiter" in mailoutbox[0].subject


def test_plafond_par_execution(
    mission_suivie: Mission, mailoutbox: list[Any], settings: Any
) -> None:
    settings.RELANCES_MAX_EMAILS_PAR_EXECUTION = 1
    for _ in range(2):
        suivi_relancable(mission_suivie, make_user(Role.AUDITE), date(2026, 11, 13))
    lancer(date(2026, 10, 29))
    assert len(mailoutbox) == 1
    lancer(date(2026, 10, 29))
    assert len(mailoutbox) == 2
    lancer(date(2026, 10, 29))
    assert len(mailoutbox) == 2


def test_echec_smtp_puis_reprise(
    mission_suivie: Mission,
    responsable: User,
    mailoutbox: list[Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = suivi_relancable(mission_suivie, responsable, date(2026, 11, 13))
    reel = relances.send_mail_template

    def panne(*args: Any, **kwargs: Any) -> None:
        raise SMTPException("relais indisponible : mot de passe=secret")

    monkeypatch.setattr(relances, "send_mail_template", panne)
    lancer(date(2026, 10, 29))
    relance = s.relances.get()
    assert relance.statut == StatutRelance.ECHEC and relance.tentatives == 1
    assert relance.erreur and len(relance.erreur) <= 500
    monkeypatch.setattr(relances, "send_mail_template", reel)
    lancer(date(2026, 10, 29))
    relance.refresh_from_db()
    assert relance.statut == StatutRelance.ENVOYEE and len(mailoutbox) == 1


def test_echec_abandonne_apres_le_maximum_de_tentatives(
    mission_suivie: Mission, responsable: User, mailoutbox: list[Any], settings: Any
) -> None:
    s = suivi_relancable(mission_suivie, responsable, date(2026, 11, 13))
    relances.planifier_relances(date(2026, 10, 29))
    Relance.objects.filter(suivi=s).update(
        statut=StatutRelance.ECHEC, tentatives=settings.RELANCES_TENTATIVES_MAX
    )
    lancer(date(2026, 10, 29))
    assert mailoutbox == []


def test_email_francais_sans_texte_de_constat(
    mission_suivie: Mission, responsable: User, mailoutbox: list[Any], settings: Any
) -> None:
    settings.PLATEFORME_URL = "https://audit.onea.bf"
    s = suivi_relancable(mission_suivie, responsable, date(2026, 11, 13))
    fait = s.recommandation.constat.fait_constate
    texte_reco = s.recommandation.libelle
    lancer(date(2026, 10, 29))
    message = mailoutbox[0]
    html = message.alternatives[0][0]
    lien = f"https://audit.onea.bf/recommandations/actions/{s.action_id}"
    for contenu in (message.body, html):
        assert fait not in contenu and texte_reco not in contenu
        assert "13/11/2026" in contenu
        assert lien in contenu
        assert mission_suivie.reference in contenu
        assert "Échéance dans 15 jours" in contenu
        assert "Ne répondez pas à cet e-mail." in contenu
    assert message.subject == "[ONEA Audit] Suivi des recommandations : 1 action(s) à traiter"
    assert "http://" not in message.body


def test_libelle_hostile_neutralise(
    mission_suivie: Mission, responsable: User, mailoutbox: list[Any]
) -> None:
    hostile = 'Faire\r\nBcc: pirate@evil.test\n<script>alert(1)</script> "x"'
    suivi_relancable(mission_suivie, responsable, date(2026, 11, 13), libelle=hostile)
    lancer(date(2026, 10, 29))
    message = mailoutbox[0]
    assert "pirate@evil.test" not in message.bcc and message.bcc == []
    assert not re.search(r"^Bcc:", message.body, re.M)
    html = message.alternatives[0][0]
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_notifications_relance_et_rai(
    mission_suivie: Mission, responsable: User, mailoutbox: list[Any]
) -> None:
    rai = make_user(Role.RAI)
    s = suivi_relancable(mission_suivie, responsable, date(2026, 10, 1))
    lancer(date(2026, 10, 20))
    lancer(date(2026, 10, 20))
    relance = s.relances.get()
    notif = Notification.objects.get(destinataire=responsable, type=TypeNotification.RELANCE)
    assert notif.cle == f"relance:{relance.pk}"
    assert Notification.objects.filter(destinataire=rai, type=TypeNotification.RELANCE).count() == 1
    nb_rai = User.objects.filter(role=Role.RAI).count()
    assert Notification.objects.filter(type=TypeNotification.RELANCE).count() == 1 + nb_rai
    # Aucun autre destinataire hors périmètre (ex. un AUDITE étranger à l'action).
    assert not Notification.objects.filter(destinataire=make_user(Role.AUDITE)).exists()


def test_pas_de_notification_rai_avant_j_plus_15(
    mission_suivie: Mission, responsable: User
) -> None:
    rai = make_user(Role.RAI)
    suivi_relancable(mission_suivie, responsable, date(2026, 11, 13))
    lancer(date(2026, 10, 29))
    assert not Notification.objects.filter(destinataire=rai).exists()


def test_commande_simulation_ne_fait_rien(
    mission_suivie: Mission, responsable: User, mailoutbox: list[Any]
) -> None:
    s = suivi_relancable(mission_suivie, responsable, date(2026, 11, 13))
    sortie = StringIO()
    call_command("envoyer_relances", "--date", "2026-10-29", "--simulation", stdout=sortie)
    assert s.relances.count() == 0 and mailoutbox == []
    assert "J-15" in sortie.getvalue()


def test_commande_envoie(mission_suivie: Mission, responsable: User, mailoutbox: list[Any]) -> None:
    s = suivi_relancable(mission_suivie, responsable, date(2026, 11, 13))
    call_command("envoyer_relances", "--date", "2026-10-29", stdout=StringIO())
    assert s.relances.get().statut == StatutRelance.ENVOYEE and len(mailoutbox) == 1


def test_commande_date_invalide(db: None) -> None:
    with pytest.raises(Exception, match="date"):
        call_command("envoyer_relances", "--date", "29/10/2026", stdout=StringIO())


def test_aucun_envoi_hors_backend_memoire() -> None:
    from django.conf import settings

    assert settings.EMAIL_BACKEND.endswith("locmem.EmailBackend")
    assert mail.outbox == []


@override_settings(PLATEFORME_URL="https://audit.onea.bf")
def test_lien_sans_double_barre(
    mission_suivie: Mission, responsable: User, mailoutbox: list[Any]
) -> None:
    suivi_relancable(mission_suivie, responsable, date(2026, 11, 13))
    lancer(date(2026, 10, 29))
    assert "https://audit.onea.bf/recommandations/actions/" in mailoutbox[0].body
    assert "//recommandations" not in mailoutbox[0].body
