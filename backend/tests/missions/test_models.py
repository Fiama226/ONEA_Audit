import datetime
from collections.abc import Callable

import pytest
from auditlog.models import LogEntry
from django.db import IntegrityError, transaction

from apps.core.exceptions import RegleMetierError
from apps.missions.models import (
    AffectationMission,
    EvenementEtape,
    Mission,
    Phase,
    RoleMission,
    StatutDeclaration,
    StatutEtape,
    StatutMission,
    TypeEvenementEtape,
)
from tests.factories import (
    AffectationFactory,
    DeclarationFactory,
    DirectionFactory,
    EntretienFactory,
    EtapeMissionFactory,
    MissionFactory,
    ProcessusFactory,
    ReunionFactory,
    RisqueFactory,
    RisqueMissionFactory,
    make_user,
)

pytestmark = pytest.mark.django_db


def _viole(action: Callable[[], object]) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        action()


def test_mission_brouillon_sans_reference_et_phase_none() -> None:
    m = MissionFactory()
    assert m.statut == StatutMission.BROUILLON
    assert m.reference == ""
    assert m.phase is None
    assert m.cartographie.statut == "VALIDEE"


def test_phase_depuis_le_statut() -> None:
    assert MissionFactory.build(statut=StatutMission.EN_PLANIFICATION).phase == Phase.PLANIFICATION
    assert MissionFactory.build(statut=StatutMission.EN_COMMUNICATION).phase == Phase.COMMUNICATION


def test_reference_unique_meme_supprimee() -> None:
    m = MissionFactory(reference="DAI/2026/M01", statut=StatutMission.PLANIFIEE)
    m.soft_delete(make_user())
    _viole(lambda: MissionFactory(reference="DAI/2026/M01", statut=StatutMission.PLANIFIEE))


def test_references_vides_multiples_permises() -> None:
    MissionFactory()
    MissionFactory()


def test_annee_numero_unique() -> None:
    MissionFactory(annee=2026, numero=3, reference="DAI/2026/M03", statut="PLANIFIEE")
    _viole(lambda: MissionFactory(annee=2026, numero=3, reference="DAI/2026/X", statut="PLANIFIEE"))


def test_hors_brouillon_exige_une_reference() -> None:
    _viole(lambda: MissionFactory(statut=StatutMission.PLANIFIEE, reference=""))


def test_dates_prevues_ordonnees_en_base() -> None:
    _viole(
        lambda: MissionFactory(
            date_debut_prevue=datetime.date(2026, 5, 1), date_fin_prevue=datetime.date(2026, 4, 1)
        )
    )
    _viole(
        lambda: MissionFactory(
            periode_debut=datetime.date(2026, 5, 1), periode_fin=datetime.date(2026, 4, 1)
        )
    )
    MissionFactory(
        date_debut_prevue=datetime.date(2026, 5, 1), date_fin_prevue=datetime.date(2026, 5, 1)
    )


def test_budget_negatif_rejete() -> None:
    _viole(lambda: MissionFactory(budget_jours=-1))


def test_un_seul_chef_et_un_seul_superviseur_actifs() -> None:
    m = MissionFactory()
    AffectationFactory(mission=m, role_mission=RoleMission.CHEF_MISSION)
    _viole(lambda: AffectationFactory(mission=m, role_mission=RoleMission.CHEF_MISSION))
    AffectationFactory(mission=m, role_mission=RoleMission.SUPERVISEUR)
    _viole(lambda: AffectationFactory(mission=m, role_mission=RoleMission.SUPERVISEUR))
    AffectationFactory(mission=m, role_mission=RoleMission.AUDITEUR)
    AffectationFactory(mission=m, role_mission=RoleMission.AUDITEUR)


def test_un_utilisateur_une_seule_fois_par_mission() -> None:
    m = MissionFactory()
    u = make_user()
    AffectationFactory(mission=m, utilisateur=u, role_mission=RoleMission.AUDITEUR)
    _viole(lambda: AffectationFactory(mission=m, utilisateur=u, role_mission=RoleMission.AUDITE))


def test_chef_remplace_apres_desaffectation_logique() -> None:
    m = MissionFactory()
    a = AffectationFactory(mission=m, role_mission=RoleMission.CHEF_MISSION)
    a.soft_delete(make_user())
    AffectationFactory(mission=m, role_mission=RoleMission.CHEF_MISSION)


def test_declaration_conflit_exige_description() -> None:
    a = AffectationFactory(role_mission=RoleMission.AUDITEUR)
    _viole(
        lambda: DeclarationFactory(
            affectation=a, statut=StatutDeclaration.CONFLIT_DECLARE, description_conflit=""
        )
    )


def test_arbitrage_exige_un_conflit_declare() -> None:
    a = AffectationFactory(role_mission=RoleMission.AUDITEUR)
    _viole(
        lambda: DeclarationFactory(
            affectation=a,
            statut=StatutDeclaration.CONFIRMEE,
            arbitrage_justification="ok",
        )
    )


def test_declaration_levee() -> None:
    assert not DeclarationFactory.build(statut=StatutDeclaration.EN_ATTENTE).levee
    assert DeclarationFactory.build(statut=StatutDeclaration.CONFIRMEE).levee
    conflit = DeclarationFactory.build(
        statut=StatutDeclaration.CONFLIT_DECLARE, description_conflit="lien familial"
    )
    assert not conflit.levee
    conflit.arbitre_le = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
    conflit.arbitre_par = make_user()
    conflit.arbitrage_justification = "Maintenu"
    assert conflit.levee


def test_etape_numero_hors_bornes_et_unicite() -> None:
    m = MissionFactory()
    _viole(lambda: EtapeMissionFactory(mission=m, numero=0))
    _viole(lambda: EtapeMissionFactory(mission=m, numero=19))
    EtapeMissionFactory(mission=m, numero=5)
    _viole(lambda: EtapeMissionFactory(mission=m, numero=5))


def test_etape_charge_negative_rejetee() -> None:
    _viole(lambda: EtapeMissionFactory(charge_prevue_jours=-1))


def test_etape_definition_et_transitions() -> None:
    e = EtapeMissionFactory(numero=4)
    assert e.definition.titre == "Identifier et évaluer les risques"
    assert e.statut == StatutEtape.A_FAIRE
    e.demarrer()
    assert e.statut == StatutEtape.EN_COURS
    e.terminer()
    e.renvoyer()
    assert e.statut == StatutEtape.RENVOYEE
    e.terminer()
    e.valider()
    assert e.statut == StatutEtape.VALIDEE
    e.a_revalider()
    assert e.statut == StatutEtape.A_REVALIDER
    e.rouvrir()
    assert e.statut == StatutEtape.EN_COURS
    e.non_applicable()
    e.retablir()
    assert e.statut == StatutEtape.A_FAIRE


def test_evenement_etape_ajout_seul() -> None:
    e = EtapeMissionFactory()
    u = make_user()
    ev = EvenementEtape.journaliser(
        e, TypeEvenementEtape.DEMARREE, par=u, motif="", statut_avant=StatutEtape.A_FAIRE
    )
    assert ev.statut_avant == StatutEtape.A_FAIRE
    assert ev.statut_apres == e.statut
    ev.motif = "modifié"
    with pytest.raises(RegleMetierError):
        ev.save()
    with pytest.raises(RegleMetierError):
        EvenementEtape.objects.filter(pk=ev.pk).update(motif="x")


def test_risque_mission_hors_bornes_rejete() -> None:
    _viole(lambda: RisqueMissionFactory(probabilite=0))
    _viole(lambda: RisqueMissionFactory(probabilite=6))
    _viole(lambda: RisqueMissionFactory(impact=0))
    _viole(lambda: RisqueMissionFactory(impact=6))


def test_code_source_vide_si_et_seulement_si_nouveau() -> None:
    nouveau = RisqueMissionFactory()
    assert nouveau.nouveau
    _viole(lambda: RisqueMissionFactory(code_source="X"))
    source = RisqueFactory()
    _viole(lambda: RisqueMissionFactory(risque_source=source, code_source=""))
    ok = RisqueMissionFactory(risque_source=source, code_source=source.code)
    assert not ok.nouveau


def test_risque_mission_score_et_niveau_generes() -> None:
    r = RisqueMissionFactory(probabilite=5, impact=4)
    r.refresh_from_db()
    assert (r.score, r.niveau) == (20, "ELEVE")
    r = RisqueMissionFactory(probabilite=2, impact=4)
    r.refresh_from_db()
    assert (r.score, r.niveau) == (8, "MOYEN")


def test_risque_source_unique_par_mission() -> None:
    m = MissionFactory()
    source = RisqueFactory()
    RisqueMissionFactory(mission=m, risque_source=source, code_source=source.code)
    _viole(lambda: RisqueMissionFactory(mission=m, risque_source=source, code_source=source.code))
    RisqueMissionFactory(mission=m)
    RisqueMissionFactory(mission=m)


def test_reunion_unique_par_type_et_mission() -> None:
    m = MissionFactory()
    ReunionFactory(mission=m, type="OUVERTURE")
    _viole(lambda: ReunionFactory(mission=m, type="OUVERTURE"))
    ReunionFactory(mission=m, type="LANCEMENT")


def test_entretien_duree_hors_bornes() -> None:
    _viole(lambda: EntretienFactory(duree_minutes=0))
    _viole(lambda: EntretienFactory(duree_minutes=601))
    EntretienFactory(duree_minutes=600)
    EntretienFactory(duree_minutes=None)


def test_m2m_historises() -> None:
    m = MissionFactory()
    m.processus.add(ProcessusFactory())
    m.entites.add(DirectionFactory())
    champs = {k for e in LogEntry.objects.filter(object_pk=str(m.pk)) for k in e.changes_dict}
    assert {"processus", "entites"} <= champs
    r = ReunionFactory()
    r.participants.add(make_user())
    champs = {k for e in LogEntry.objects.filter(object_pk=str(r.pk)) for k in e.changes_dict}
    assert "participants" in champs
    en = EntretienFactory()
    en.auditeurs.add(make_user())
    en.interlocuteurs.add(make_user())
    champs = {k for e in LogEntry.objects.filter(object_pk=str(en.pk)) for k in e.changes_dict}
    assert {"auditeurs", "interlocuteurs"} <= champs


def test_creation_historisee() -> None:
    m = MissionFactory()
    assert LogEntry.objects.filter(object_pk=str(m.pk)).exists()
    a = AffectationFactory(mission=m)
    assert LogEntry.objects.filter(object_pk=str(a.pk)).exists()
    assert AffectationMission.objects.count() == 1
    assert Mission.objects.count() == 1
