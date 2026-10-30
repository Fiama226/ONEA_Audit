import datetime
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from django.utils import timezone

from apps.accomplissement.models import StatutFiche, StatutTest, TestPrevu
from apps.constats.models import Constat, StatutConstat
from apps.missions.models import (
    EtapeMission,
    EvenementEtape,
    Mission,
    StatutEtape,
    StatutMission,
    TypeEvenementEtape,
)
from apps.referentiel.models import CartographieVersion, NiveauRisque
from apps.suivi.models import PalierRelance, Relance, StatutRelance, StatutSuivi, SuiviAction
from apps.tableaux_de_bord import agregats
from apps.tableaux_de_bord.perimetres import missions_de_l_annee
from apps.users.models import Role, User
from tests.accomplissement.factories import FicheFactory, TestPrevuFactory
from tests.constats.factories import ConstatFactory, ReponseFactory
from tests.factories import (
    CartographieVersionFactory,
    DirectionFactory,
    EtapeMissionFactory,
    MissionFactory,
    RisqueFactory,
    RisqueMissionFactory,
    make_user,
)
from tests.suivi.factories import DemandeReportFactory, RelanceFactory
from tests.tableaux_de_bord.conftest import AUJOURD_HUI, faire_mission


@pytest.mark.parametrize(
    "cloturees, abandonnees, ouvertes, taux",
    [(0, 0, 0, None), (0, 2, 0, None), (3, 1, 1, Decimal("0.75")), (2, 0, 2, Decimal("0.50"))],
)
def test_taux_mise_en_oeuvre_cas_limites(
    cloturees: int, abandonnees: int, ouvertes: int, taux: Decimal | None, fabrique_suivis: Any
) -> None:
    suivis = fabrique_suivis(cloturees=cloturees, abandonnees=abandonnees, ouvertes=ouvertes)
    resultat = agregats.taux_mise_en_oeuvre(suivis, AUJOURD_HUI)
    assert resultat["taux"] == taux
    assert resultat["cloturees"] == cloturees
    assert resultat["abandonnees"] == abandonnees
    assert resultat["total"] == cloturees + abandonnees + ouvertes


def test_taux_echues_restreint_aux_echeances_passees(
    mission_diffusee: Mission, creer_suivi: Callable[..., SuiviAction]
) -> None:
    entite = DirectionFactory()
    passe, futur = datetime.date(2026, 10, 1), datetime.date(2027, 3, 1)
    creer_suivi(mission_diffusee, entite, StatutSuivi.CLOTUREE, passe)
    creer_suivi(mission_diffusee, entite, StatutSuivi.EN_COURS, passe)
    creer_suivi(mission_diffusee, entite, StatutSuivi.ABANDONNEE, passe)
    creer_suivi(mission_diffusee, entite, StatutSuivi.CLOTUREE, futur)
    resultat = agregats.taux_mise_en_oeuvre(SuiviAction.objects.all(), AUJOURD_HUI)
    assert (resultat["echues"], resultat["cloturees_echues"]) == (2, 1)
    assert resultat["taux_echues"] == Decimal("0.50")
    assert resultat["taux"] == Decimal("0.67")
    par_direction = agregats.taux_par_direction(SuiviAction.objects.all(), AUJOURD_HUI)
    assert [(d["code"], d["total"]) for d in par_direction] == [(entite.code, 4)]


def test_actions_par_direction(
    mission_diffusee: Mission, creer_suivi: Callable[..., SuiviAction]
) -> None:
    entite = DirectionFactory()
    creer_suivi(mission_diffusee, entite, StatutSuivi.EN_COURS, datetime.date(2026, 10, 1))
    creer_suivi(mission_diffusee, entite, StatutSuivi.A_LANCER, datetime.date(2026, 12, 1))
    creer_suivi(mission_diffusee, entite, StatutSuivi.CLOTUREE, datetime.date(2026, 10, 1))
    creer_suivi(mission_diffusee, entite, StatutSuivi.ABANDONNEE, datetime.date(2026, 10, 1))
    assert agregats.actions_par_direction(SuiviAction.objects.all(), AUJOURD_HUI) == [
        {
            "direction_id": entite.pk,
            "code": entite.code,
            "libelle": entite.libelle,
            "cloturees": 1,
            "ouvertes_dans_les_delais": 1,
            "en_retard": 1,
            "abandonnees": 1,
        }
    ]


def test_retard_commence_le_lendemain(
    mission_diffusee: Mission, creer_suivi: Callable[..., SuiviAction]
) -> None:
    entite = DirectionFactory()
    creer_suivi(mission_diffusee, entite, StatutSuivi.EN_COURS, AUJOURD_HUI)
    creer_suivi(mission_diffusee, entite, StatutSuivi.VERIFIEE, datetime.date(2026, 10, 1))
    (ligne,) = agregats.actions_par_direction(SuiviAction.objects.all(), AUJOURD_HUI)
    assert ligne["en_retard"] == 0  # le jour J et une action déjà vérifiée ne sont pas en retard
    assert ligne["ouvertes_dans_les_delais"] == 2


def test_missions_par_statut(db: None) -> None:
    faire_mission(StatutMission.EN_PLANIFICATION)
    faire_mission(StatutMission.EN_PLANIFICATION)
    faire_mission(StatutMission.EN_COMMUNICATION)
    lignes = agregats.missions_par_statut(Mission.objects.all())
    assert [(ligne["statut"], ligne["nombre"]) for ligne in lignes] == [
        ("EN_PLANIFICATION", 2),
        ("EN_COMMUNICATION", 1),
    ]
    assert lignes[0]["libelle"] == "En planification"
    assert lignes[0]["phase"] == "PLANIFICATION"


def test_missions_de_l_annee_brouillon_sans_annee(db: None) -> None:
    brouillon = MissionFactory(statut=StatutMission.BROUILLON, annee=None)
    MissionFactory(annee=2025)
    courante = MissionFactory(annee=timezone.now().year)
    resultat = set(missions_de_l_annee(Mission.objects.all(), timezone.now().year))
    assert resultat == {brouillon, courante}


def test_missions_en_retard_exclut_diffusees_et_annulees(db: None) -> None:
    passe, futur = datetime.date(2026, 10, 19), datetime.date(2026, 12, 1)
    en_retard = faire_mission(StatutMission.EN_ACCOMPLISSEMENT, date_fin_prevue=passe)
    for statut in (
        StatutMission.RAPPORT_DIFFUSE,
        StatutMission.EN_SUIVI,
        StatutMission.CLOTUREE,
        StatutMission.ANNULEE,
        StatutMission.SUSPENDUE,
    ):
        faire_mission(statut, date_fin_prevue=passe)
    faire_mission(StatutMission.EN_ACCOMPLISSEMENT, date_fin_prevue=futur)
    faire_mission(StatutMission.EN_ACCOMPLISSEMENT, date_fin_prevue=AUJOURD_HUI)
    lignes = agregats.missions_en_retard(Mission.objects.all(), AUJOURD_HUI)
    assert [(ligne["mission_id"], ligne["jours_retard"]) for ligne in lignes] == [
        (en_retard.pk, 10)
    ]


def test_etapes_en_retard(db: None) -> None:
    passe = datetime.date(2026, 10, 1)
    mission = faire_mission(StatutMission.EN_ACCOMPLISSEMENT)
    suspendue = faire_mission(StatutMission.EN_ACCOMPLISSEMENT)
    for numero, statut in ((1, StatutEtape.EN_COURS), (2, StatutEtape.A_FAIRE)):
        EtapeMissionFactory(mission=mission, numero=numero, statut=statut, date_fin_prevue=passe)
    EtapeMissionFactory(
        mission=mission, numero=3, statut=StatutEtape.VALIDEE, date_fin_prevue=passe
    )
    EtapeMissionFactory(
        mission=mission, numero=4, statut=StatutEtape.EN_COURS, date_fin_prevue=AUJOURD_HUI
    )
    EtapeMissionFactory(
        mission=suspendue, numero=1, statut=StatutEtape.EN_COURS, date_fin_prevue=passe
    )
    Mission.objects.filter(pk=suspendue.pk).update(statut=StatutMission.SUSPENDUE)
    assert agregats.etapes_en_retard(Mission.objects.all(), AUJOURD_HUI) == 2


def test_jalons_a_valider(mission_lancee: Mission) -> None:
    chef_ = make_user(Role.AUDITEUR)
    jalon = EtapeMission.objects.get(mission=mission_lancee, numero=6)
    ordinaire = EtapeMission.objects.get(mission=mission_lancee, numero=3)
    EtapeMission.objects.filter(pk__in=[jalon.pk, ordinaire.pk]).update(statut=StatutEtape.TERMINEE)
    evenement = EvenementEtape.objects.create(
        etape=jalon,
        type=TypeEvenementEtape.TERMINEE,
        par=chef_,
        statut_avant=StatutEtape.EN_COURS,
        statut_apres=StatutEtape.TERMINEE,
    )
    (ligne,) = agregats.jalons_a_valider(Mission.objects.all())
    assert ligne["mission_id"] == mission_lancee.pk
    assert (ligne["numero"], ligne["romain"]) == (6, "VI")
    assert ligne["reference"] == "DAI/2026/M01"
    assert ligne["libelle"]
    assert ligne["terminee_le"] == evenement.le


def test_cartographie_derniere_version_validee(
    db: None, valider_carto: Callable[[CartographieVersion], CartographieVersion]
) -> None:
    ancienne = CartographieVersionFactory(annee=2024)
    RisqueFactory(version=ancienne, probabilite=1, impact=1)
    valider_carto(ancienne)
    recente = CartographieVersionFactory(annee=2025)
    for probabilite, impact in ((5, 5), (5, 5), (2, 3)):
        RisqueFactory(version=recente, probabilite=probabilite, impact=impact)
    valider_carto(recente)
    CartographieVersionFactory(annee=2026)  # brouillon : ignoré
    resultat = agregats.cartographie(2026)
    assert resultat["version_id"] == recente.pk
    assert resultat["annee"] == 2025
    assert resultat["cellules"] == [
        {"probabilite": 2, "impact": 3, "nombre": 1},
        {"probabilite": 5, "impact": 5, "nombre": 2},
    ]
    assert agregats.cartographie(2024)["version_id"] == ancienne.pk
    assert agregats.cartographie(2023) == {"version_id": None, "annee": None, "cellules": []}


def test_risques_eleves_couverture_hors_brouillon_et_annulee(
    db: None, valider_carto: Callable[[CartographieVersion], CartographieVersion]
) -> None:
    version = CartographieVersionFactory(annee=2025)
    couvert = RisqueFactory(version=version, probabilite=5, impact=5)
    seulement_brouillon = RisqueFactory(version=version, probabilite=5, impact=4)
    seulement_annulee = RisqueFactory(version=version, probabilite=4, impact=4)
    hors_annee = RisqueFactory(version=version, probabilite=5, impact=3)
    RisqueFactory(version=version, probabilite=2, impact=2)  # niveau faible : ignoré
    assert couvert.niveau == NiveauRisque.ELEVE
    valider_carto(version)
    mission = faire_mission(StatutMission.EN_ACCOMPLISSEMENT)
    brouillon = faire_mission(StatutMission.BROUILLON)
    annulee = faire_mission(StatutMission.EN_ACCOMPLISSEMENT)
    autre_annee = faire_mission(StatutMission.EN_ACCOMPLISSEMENT, annee=2025)
    RisqueMissionFactory(mission=mission, risque_source=couvert, code_source=couvert.code)
    RisqueMissionFactory(
        mission=brouillon, risque_source=seulement_brouillon, code_source=seulement_brouillon.code
    )
    RisqueMissionFactory(
        mission=annulee, risque_source=seulement_annulee, code_source=seulement_annulee.code
    )
    RisqueMissionFactory(mission=autre_annee, risque_source=hors_annee, code_source=hors_annee.code)
    Mission.objects.filter(pk=annulee.pk).update(statut=StatutMission.ANNULEE)
    resultat = agregats.risques_eleves(2026)
    assert (resultat["couverts"], resultat["non_couverts"]) == (1, 3)
    par_id = {r["id"]: r for r in resultat["risques"]}
    assert set(par_id) == {couvert.pk, seulement_brouillon.pk, seulement_annulee.pk, hors_annee.pk}
    assert par_id[couvert.pk]["couvert"] is True
    assert par_id[couvert.pk]["missions"] == [mission.reference]
    assert par_id[couvert.pk]["processus_code"] == couvert.processus.code
    assert not par_id[seulement_brouillon.pk]["couvert"]
    assert agregats.risques_eleves(2020) == {"couverts": 0, "non_couverts": 0, "risques": []}


def test_file_decisions_rai(
    mission_diffusee: Mission, creer_suivi: Callable[..., SuiviAction], db: None
) -> None:
    entite = DirectionFactory()
    creer_suivi(mission_diffusee, entite, StatutSuivi.VERIFIEE)
    creer_suivi(mission_diffusee, entite, StatutSuivi.ABANDON_PROPOSE)
    suivi = creer_suivi(mission_diffusee, entite, StatutSuivi.EN_COURS)
    DemandeReportFactory(suivi=suivi)
    for palier, statut in (
        (PalierRelance.J_MOINS_15, StatutRelance.ECHEC),
        (PalierRelance.J, StatutRelance.SANS_ADRESSE),
        (PalierRelance.J_PLUS_15, StatutRelance.ENVOYEE),
    ):
        relance = RelanceFactory(suivi=suivi, palier=palier)
        Relance.objects.filter(pk=relance.pk).update(statut=statut)
    # Mission à clôturer : tous ses suivis sont clos (ou elle n'en a aucun).
    prete = faire_mission(StatutMission.RAPPORT_DIFFUSE)
    creer_suivi(prete, entite, StatutSuivi.CLOTUREE)
    creer_suivi(prete, entite, StatutSuivi.ABANDONNEE)
    faire_mission(StatutMission.EN_SUIVI)  # sans action : clôturable
    resultat = agregats.file_decisions_rai()
    assert resultat == {
        "a_cloturer": 1,
        "abandons_proposes": 1,
        "reports_en_attente": 1,
        "missions_a_cloturer": 2,
        "relances_en_echec": 1,
        "relances_sans_adresse": 1,
    }


def test_mes_tests_a_documenter(mission_lancee: Mission) -> None:
    auditeur = make_user(Role.AUDITEUR)
    autre = make_user(Role.AUDITEUR)
    sans_fiche = TestPrevuFactory(mission=mission_lancee, auditeur=auditeur)
    brouillon = TestPrevuFactory(mission=mission_lancee, auditeur=auditeur)
    soumis = TestPrevuFactory(mission=mission_lancee, auditeur=auditeur)
    abandonne = TestPrevuFactory(mission=mission_lancee, auditeur=auditeur)
    TestPrevuFactory(mission=mission_lancee, auditeur=autre)
    for test, statut in ((brouillon, StatutFiche.BROUILLON), (soumis, StatutFiche.SOUMIS)):
        fiche = FicheFactory(test=test)
        type(fiche).objects.filter(pk=fiche.pk).update(statut=statut, conclusion="SATISFAISANT")
    TestPrevu.objects.filter(pk=abandonne.pk).update(
        statut=StatutTest.ABANDONNE, motif_abandon="Sans objet."
    )
    lignes = agregats.mes_tests_a_documenter(auditeur)
    assert {ligne["test_id"] for ligne in lignes} == {sans_fiche.pk, brouillon.pk}
    assert {ligne["test_id"]: ligne["sans_fiche"] for ligne in lignes} == {
        sans_fiche.pk: True,
        brouillon.pk: False,
    }
    EtapeMission.objects.filter(mission=mission_lancee, numero=12).update(
        statut=StatutEtape.TERMINEE
    )
    assert agregats.mes_tests_a_documenter(auditeur) == []


def test_constats_a_repondre_cycle_courant(mission_lancee: Mission, audite_affecte: User) -> None:
    Mission.objects.filter(pk=mission_lancee.pk).update(ordre_mission_emis_le=timezone.now())
    entite = DirectionFactory()
    User.objects.filter(pk=audite_affecte.pk).update(direction_code=entite.code)
    audite_affecte.refresh_from_db()

    def constat(statut: str, cycle: int, **kwargs: Any) -> Constat:
        c = ConstatFactory(mission=mission_lancee, **({"entite": entite} | kwargs))
        Constat.objects.filter(pk=c.pk).update(
            statut=statut, cycle=cycle, soumis_le=timezone.now() if cycle else None
        )
        return c

    a_repondre = constat(StatutConstat.SOUMIS, 1)
    repondu = constat(StatutConstat.VALIDE, 1)
    ReponseFactory(constat=repondu, cycle=1)
    nouveau_cycle = constat(StatutConstat.SOUMIS, 2)
    ReponseFactory(constat=nouveau_cycle, cycle=1)
    constat(StatutConstat.BROUILLON, 0)
    constat(StatutConstat.RENVOYE, 1)
    constat(StatutConstat.SOUMIS, 1, entite=DirectionFactory())  # autre entité
    lignes = agregats.constats_a_repondre(audite_affecte)
    assert {ligne["constat_id"] for ligne in lignes} == {a_repondre.pk, nouveau_cycle.pk}
    EtapeMission.objects.filter(mission=mission_lancee, numero=15).update(
        statut=StatutEtape.VALIDEE
    )
    assert agregats.constats_a_repondre(audite_affecte) == []
