import datetime

import pytest
from django.db import IntegrityError, transaction

from apps.core.exceptions import RegleMetierError
from apps.missions.exceptions import MissionFigeeError
from apps.missions.models import Mission, StatutMission
from apps.suivi.exceptions import (
    AjoutSeulSuiviError,
    PreuveImmuableError,
    RelanceImmuableError,
    SuiviImmuableError,
)
from apps.suivi.models import (
    DemandeReport,
    EvenementSuivi,
    PalierRelance,
    PreuveMiseEnOeuvre,
    Relance,
    StatutDemandeReport,
    StatutRelance,
    StatutSuivi,
    SuiviAction,
    TypeEvenementSuivi,
)
from tests.factories import DirectionFactory
from tests.suivi.factories import (
    DemandeReportFactory,
    PreuveFactory,
    RelanceFactory,
    SuiviActionFactory,
)


def _premier(mission: Mission) -> SuiviAction:
    suivi: SuiviAction = mission.suivis_actions.first()
    return suivi


def test_champs_copies_immuables(mission_en_suivi: Mission) -> None:
    s = _premier(mission_en_suivi)
    s.echeance_initiale = s.echeance_initiale + datetime.timedelta(days=1)
    with pytest.raises(SuiviImmuableError):
        s.save()
    with pytest.raises(SuiviImmuableError):
        SuiviAction.objects.filter(pk=s.pk).update(entite=DirectionFactory())


def test_champs_copies_immuables_bulk_update_et_upsert(mission_en_suivi: Mission) -> None:
    s = _premier(mission_en_suivi)
    s.diffuse_le = s.diffuse_le + datetime.timedelta(days=1)
    with pytest.raises(SuiviImmuableError):
        SuiviAction.objects.bulk_update([s], ["diffuse_le"])
    with pytest.raises(RegleMetierError):
        SuiviAction.objects.bulk_create([s], update_conflicts=True, unique_fields=["id"])


def test_champs_courants_modifiables(mission_en_suivi: Mission) -> None:
    s = _premier(mission_en_suivi)
    nouvelle = s.echeance + datetime.timedelta(days=30)
    s.echeance = nouvelle
    s.save()
    assert SuiviAction.objects.filter(pk=s.pk).update(nombre_reports=1) == 1
    s.refresh_from_db()
    assert s.echeance == nouvelle


def test_transitions_r2(mission_en_suivi: Mission) -> None:
    s = _premier(mission_en_suivi)
    s.demarrer()
    s.declarer_realisee()
    s.verifier()
    s.cloturer()
    assert s.statut == StatutSuivi.CLOTUREE
    s.rouvrir()
    assert s.statut == StatutSuivi.EN_COURS


def test_abandon_exige_justification_en_base(mission_en_suivi: Mission) -> None:
    s = _premier(mission_en_suivi)
    with pytest.raises(IntegrityError), transaction.atomic():
        SuiviAction.objects.filter(pk=s.pk).update(statut=StatutSuivi.ABANDON_PROPOSE)
    SuiviAction.objects.filter(pk=s.pk).update(
        statut=StatutSuivi.ABANDON_PROPOSE, justification_abandon="Action sans objet."
    )


def test_echeance_jamais_avant_initiale(mission_en_suivi: Mission) -> None:
    s = _premier(mission_en_suivi)
    with pytest.raises(IntegrityError), transaction.atomic():
        SuiviAction.objects.filter(pk=s.pk).update(
            echeance=s.echeance_initiale - datetime.timedelta(days=1)
        )


def test_un_seul_report_en_attente_en_base(mission_en_suivi: Mission) -> None:
    s = _premier(mission_en_suivi)
    premiere = DemandeReportFactory(suivi=s)
    with pytest.raises(IntegrityError), transaction.atomic():
        DemandeReportFactory(suivi=s)
    DemandeReport.objects.filter(pk=premiere.pk).update(statut=StatutDemandeReport.REFUSEE)
    DemandeReportFactory(suivi=s)
    premiere.refresh_from_db()
    assert premiere.statut == StatutDemandeReport.REFUSEE


def test_report_exige_date_posterieure_et_motif(mission_en_suivi: Mission) -> None:
    s = _premier(mission_en_suivi)
    with pytest.raises(IntegrityError), transaction.atomic():
        DemandeReportFactory(suivi=s, nouvelle_echeance=s.echeance)
    with pytest.raises(IntegrityError), transaction.atomic():
        DemandeReportFactory(suivi=s, motif="")


def test_preuve_champs_fichier_immuables(mission_en_suivi: Mission) -> None:
    p = PreuveFactory(suivi=_premier(mission_en_suivi))
    p.empreinte_sha256 = "f" * 64
    with pytest.raises(PreuveImmuableError, match="déposez-en une nouvelle"):
        p.save()
    with pytest.raises(PreuveImmuableError):
        PreuveMiseEnOeuvre.objects.filter(pk=p.pk).update(cle_stockage="autre")
    p.refresh_from_db()
    p.description = "Précision"
    p.save()


def test_preuve_empreinte_sha256_en_base(mission_en_suivi: Mission) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        PreuveFactory(suivi=_premier(mission_en_suivi), empreinte_sha256="xyz")


def test_relance_unique_par_palier_et_echeance(mission_en_suivi: Mission) -> None:
    s = _premier(mission_en_suivi)
    RelanceFactory(suivi=s)
    with pytest.raises(IntegrityError), transaction.atomic():
        RelanceFactory(suivi=s)
    RelanceFactory(suivi=s, palier=PalierRelance.J)
    RelanceFactory(suivi=s, echeance_reference=s.echeance + datetime.timedelta(days=30))


def test_relance_seul_envoi_change(mission_en_suivi: Mission) -> None:
    r = RelanceFactory(suivi=_premier(mission_en_suivi))
    r.statut = StatutRelance.ENVOYEE
    r.tentatives = 1
    r.save()
    r.palier = PalierRelance.J_PLUS_15
    with pytest.raises(RelanceImmuableError):
        r.save()
    with pytest.raises(RelanceImmuableError):
        Relance.objects.filter(pk=r.pk).update(palier=PalierRelance.J)
    assert Relance.objects.filter(pk=r.pk).update(statut=StatutRelance.ECHEC, erreur="SMTP") == 1


def test_evenement_ajout_seul(mission_en_suivi: Mission, rai: object) -> None:
    s = _premier(mission_en_suivi)
    e = EvenementSuivi.journaliser(s, TypeEvenementSuivi.OUVERT, par=None, texte="Ouvert")
    assert e.statut_apres == StatutSuivi.A_LANCER
    e.texte = "Autre"
    with pytest.raises(AjoutSeulSuiviError):
        e.save()
    with pytest.raises(AjoutSeulSuiviError):
        EvenementSuivi.objects.filter(pk=e.pk).update(texte="x")
    with pytest.raises(AjoutSeulSuiviError):
        e.soft_delete(rai)  # type: ignore[arg-type]


def test_ecriture_refusee_mission_cloturee(mission_en_suivi: Mission) -> None:
    s = _premier(mission_en_suivi)
    Mission.objects.filter(pk=mission_en_suivi.pk).update(statut=StatutMission.CLOTUREE)
    s.nombre_reports = 3
    with pytest.raises(MissionFigeeError):
        s.save()
    with pytest.raises(MissionFigeeError):
        SuiviAction.objects.filter(pk=s.pk).update(nombre_reports=2)
    with pytest.raises(MissionFigeeError):
        SuiviActionFactory(mission=mission_en_suivi)


def test_un_suivi_par_action(mission_en_suivi: Mission) -> None:
    s = _premier(mission_en_suivi)
    with pytest.raises(IntegrityError), transaction.atomic():
        SuiviActionFactory(action=s.action)
