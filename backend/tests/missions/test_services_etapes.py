from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from pytest_django.fixtures import DjangoAssertNumQueries

from apps.core.exceptions import RegleMetierError
from apps.missions.exceptions import MissionFigeeError
from apps.missions.models import (
    DeclarationIndependance,
    EtapeMission,
    EvenementEtape,
    Mission,
    RoleMission,
    StatutDeclaration,
    StatutEtape,
    StatutMission,
    TypeEvenementEtape,
    TypeMission,
)
from apps.missions.services.etapes import (
    ActionEtape,
    actions_possibles,
    avancer_phase,
    contexte_actions,
    demarrer_etape,
    marquer_non_applicable,
    planifier_etape,
    renvoyer_etape,
    retablir_etape,
    rouvrir_etape,
    terminer_etape,
    valider_etape,
)
from apps.users.models import Role, User
from tests.factories import EntretienFactory, ReunionFactory, make_user
from tests.missions.conftest import affecter, forcer_etapes

pytestmark = pytest.mark.django_db

A = ActionEtape


def etape_n(mission: Mission, numero: int) -> EtapeMission:
    return mission.etapes.get(numero=numero)


def statut_mission(mission: Mission) -> str:
    return str(Mission.objects.get(pk=mission.pk).statut)


def en_phase(mission: Mission, statut: str) -> None:
    Mission.objects.filter(pk=mission.pk).update(statut=statut)


def nom(user: User) -> str:
    return user.get_full_name() or user.username


@pytest.fixture
def superviseur(mission_lancee: Mission) -> User:
    user = make_user(Role.AUDITEUR)
    affecter(mission_lancee, user, RoleMission.SUPERVISEUR)
    return user


def test_demarrer_II_exige_les_declarations(mission_lancee: Mission, rai: User) -> None:
    forcer_etapes(mission_lancee, {1: StatutEtape.TERMINEE})
    en_attente = make_user(Role.AUDITEUR)
    affecter(mission_lancee, en_attente, RoleMission.AUDITEUR, confirmee=False)
    with pytest.raises(RegleMetierError) as exc:
        demarrer_etape(etape_n(mission_lancee, 2), by=rai)
    assert exc.value.errors["declarations"] == [
        f"Déclarations d'indépendance en attente : {nom(en_attente)}."
    ]
    DeclarationIndependance.objects.update(statut=StatutDeclaration.CONFIRMEE)
    etape = demarrer_etape(etape_n(mission_lancee, 2), by=rai)
    assert etape.statut == StatutEtape.EN_COURS
    assert etape.date_debut_reelle == timezone.localdate()


def test_demarrer_etape_d_une_phase_future_refuse(mission_lancee: Mission, rai: User) -> None:
    with pytest.raises(RegleMetierError) as exc:
        demarrer_etape(etape_n(mission_lancee, 12), by=rai)
    assert exc.value.message == "L'étape XII appartient à une phase qui n'a pas commencé."
    assert etape_n(mission_lancee, 12).statut == StatutEtape.A_FAIRE


def test_demarrer_refuse_si_mission_figee(mission_lancee: Mission, rai: User) -> None:
    en_phase(mission_lancee, StatutMission.SUSPENDUE)
    with pytest.raises(MissionFigeeError):
        demarrer_etape(etape_n(mission_lancee, 2), by=rai)


def test_demarrer_exige_le_role_et_la_declaration(
    mission_lancee: Mission, auditeur_mission: User
) -> None:
    forcer_etapes(mission_lancee, {1: StatutEtape.TERMINEE})
    sans_declaration = make_user(Role.AUDITEUR)
    affecter(mission_lancee, sans_declaration, RoleMission.AUDITEUR, confirmee=False)
    with pytest.raises(PermissionDenied):
        demarrer_etape(etape_n(mission_lancee, 3), by=sans_declaration)
    with pytest.raises(PermissionDenied):
        demarrer_etape(etape_n(mission_lancee, 3), by=make_user(Role.AUDITEUR))
    DeclarationIndependance.objects.update(statut=StatutDeclaration.CONFIRMEE)
    demarrer_etape(etape_n(mission_lancee, 2), by=auditeur_mission)


def test_terminer_II_livrables_manquants(mission_lancee: Mission, chef: User) -> None:
    en_attente = make_user(Role.AUDITEUR)
    affecter(mission_lancee, en_attente, RoleMission.AUDITEUR, confirmee=False)
    forcer_etapes(mission_lancee, {1: StatutEtape.TERMINEE, 2: StatutEtape.EN_COURS})
    with pytest.raises(RegleMetierError) as exc:
        terminer_etape(etape_n(mission_lancee, 2), by=chef)
    assert exc.value.message == "Livrables manquants."
    assert exc.value.errors["livrables"] == [
        "La réunion d'ouverture n'est pas marquée comme tenue.",
        "Aucun entretien n'est planifié.",
        f"Déclarations d'indépendance en attente : {nom(en_attente)}.",
    ]
    assert etape_n(mission_lancee, 2).statut == StatutEtape.EN_COURS


def test_terminer_II_complete(mission_lancee: Mission, chef: User) -> None:
    forcer_etapes(mission_lancee, {1: StatutEtape.TERMINEE, 2: StatutEtape.EN_COURS})
    ReunionFactory(mission=mission_lancee, tenue_le=timezone.now())
    EntretienFactory(mission=mission_lancee)
    etape = terminer_etape(etape_n(mission_lancee, 2), by=chef)
    assert etape.statut == StatutEtape.TERMINEE
    assert etape.terminee_par == chef
    assert etape.date_fin_reelle == timezone.localdate()
    assert statut_mission(mission_lancee) == StatutMission.EN_PLANIFICATION


def test_terminer_XV_renvoie_au_lot_7(mission_lancee: Mission, chef: User) -> None:
    forcer_etapes(mission_lancee, {15: StatutEtape.EN_COURS})
    with pytest.raises(RegleMetierError) as exc:
        terminer_etape(etape_n(mission_lancee, 15), by=chef)
    assert exc.value.errors["livrables"] == [
        "Les livrables de l'étape XV sont gérés à partir du lot 7."
    ]


def test_terminer_I_refuse(mission_lancee: Mission, chef: User) -> None:
    with pytest.raises(RegleMetierError) as exc:
        terminer_etape(etape_n(mission_lancee, 1), by=chef)
    assert exc.value.message == "L'étape I se termine par l'émission de l'ordre de mission."
    assert actions_possibles(etape_n(mission_lancee, 1), chef) == [A.PLANIFIER]


def test_terminer_exige_le_chef(mission_lancee: Mission, rai: User, auditeur_mission: User) -> None:
    forcer_etapes(mission_lancee, {1: StatutEtape.TERMINEE, 2: StatutEtape.EN_COURS})
    for user in (rai, auditeur_mission):
        with pytest.raises(PermissionDenied):
            terminer_etape(etape_n(mission_lancee, 2), by=user)


def test_valider_X_fait_passer_en_accomplissement(mission_lancee: Mission, rai: User) -> None:
    forcer_etapes(mission_lancee, {n: StatutEtape.TERMINEE for n in range(1, 11)})
    etape = valider_etape(etape_n(mission_lancee, 10), by=rai)
    assert etape.statut == StatutEtape.VALIDEE
    assert etape.validee_par == rai
    assert etape.validee_le is not None
    assert statut_mission(mission_lancee) == StatutMission.EN_ACCOMPLISSEMENT


def test_phase_ne_change_pas_tant_qu_une_etape_est_ouverte(
    mission_lancee: Mission, rai: User
) -> None:
    forcer_etapes(
        mission_lancee,
        {n: StatutEtape.TERMINEE for n in range(1, 11)}
        | {7: StatutEtape.NON_APPLICABLE, 8: StatutEtape.EN_COURS},
    )
    valider_etape(etape_n(mission_lancee, 10), by=rai)
    assert statut_mission(mission_lancee) == StatutMission.EN_PLANIFICATION
    assert avancer_phase(mission_lancee, by=rai) is False
    forcer_etapes(mission_lancee, {8: StatutEtape.TERMINEE})
    assert avancer_phase(mission_lancee, by=rai) is True
    assert statut_mission(mission_lancee) == StatutMission.EN_ACCOMPLISSEMENT


def test_xiii_valide_en_dernier_passe_en_communication(mission_lancee: Mission, rai: User) -> None:
    en_phase(mission_lancee, StatutMission.EN_ACCOMPLISSEMENT)
    forcer_etapes(mission_lancee, {n: StatutEtape.TERMINEE for n in range(1, 15)})
    valider_etape(etape_n(mission_lancee, 13), by=rai)
    assert statut_mission(mission_lancee) == StatutMission.EN_COMMUNICATION


def test_xiv_termine_en_dernier_passe_en_communication(mission_lancee: Mission, rai: User) -> None:
    en_phase(mission_lancee, StatutMission.EN_ACCOMPLISSEMENT)
    forcer_etapes(
        mission_lancee,
        {n: "TERMINEE" for n in range(1, 13)} | {13: "VALIDEE", 14: "EN_COURS"},
    )
    assert avancer_phase(mission_lancee, by=rai) is False
    forcer_etapes(mission_lancee, {14: StatutEtape.TERMINEE})
    assert avancer_phase(mission_lancee, by=rai) is True
    assert statut_mission(mission_lancee) == StatutMission.EN_COMMUNICATION


def test_rouvrir_IV_met_VI_a_revalider_et_bloque_la_phase(
    mission_lancee: Mission, rai: User
) -> None:
    forcer_etapes(
        mission_lancee,
        {n: StatutEtape.TERMINEE for n in range(1, 11)} | {6: "VALIDEE", 10: "TERMINEE"},
    )
    rouvrir_etape(etape_n(mission_lancee, 4), motif="Risque oublié", by=rai)
    assert etape_n(mission_lancee, 4).statut == StatutEtape.EN_COURS
    assert etape_n(mission_lancee, 4).date_fin_reelle is None
    assert etape_n(mission_lancee, 6).statut == StatutEtape.A_REVALIDER
    evenement = EvenementEtape.objects.get(
        etape__mission=mission_lancee, etape__numero=6, type=TypeEvenementEtape.A_REVALIDER
    )
    assert evenement.par == rai
    valider_etape(etape_n(mission_lancee, 10), by=rai)
    assert statut_mission(mission_lancee) == StatutMission.EN_PLANIFICATION


def test_valideur_auteur_refuse(mission_lancee: Mission, rai: User) -> None:
    forcer_etapes(mission_lancee, {10: StatutEtape.TERMINEE})
    EtapeMission.objects.filter(mission=mission_lancee, numero=10).update(terminee_par=rai)
    with pytest.raises(RegleMetierError) as exc:
        valider_etape(etape_n(mission_lancee, 10), by=rai)
    assert exc.value.message == "Le valideur ne peut pas être l'auteur de l'étape."
    with pytest.raises(RegleMetierError):
        renvoyer_etape(etape_n(mission_lancee, 10), motif="Non", by=rai)
    assert A.VALIDER not in actions_possibles(etape_n(mission_lancee, 10), rai)


def test_valider_une_etape_non_jalon_refuse(mission_lancee: Mission, rai: User) -> None:
    forcer_etapes(mission_lancee, {5: StatutEtape.TERMINEE})
    with pytest.raises(RegleMetierError) as exc:
        valider_etape(etape_n(mission_lancee, 5), by=rai)
    assert exc.value.message == "Seuls les jalons VI, X, XIII et XVIII sont validés."


def test_superviseur_valide_VI_pas_XVIII(mission_lancee: Mission, superviseur: User) -> None:
    forcer_etapes(mission_lancee, {6: StatutEtape.TERMINEE, 18: StatutEtape.TERMINEE})
    assert A.VALIDER in actions_possibles(etape_n(mission_lancee, 6), superviseur)
    assert valider_etape(etape_n(mission_lancee, 6), by=superviseur).statut == StatutEtape.VALIDEE
    en_phase(mission_lancee, StatutMission.EN_COMMUNICATION)
    assert A.VALIDER not in actions_possibles(etape_n(mission_lancee, 18), superviseur)
    with pytest.raises(PermissionDenied):
        valider_etape(etape_n(mission_lancee, 18), by=superviseur)


def test_non_applicable_assurance_ou_jalon_refuse(mission_lancee: Mission, chef: User) -> None:
    with pytest.raises(RegleMetierError) as exc:
        marquer_non_applicable(etape_n(mission_lancee, 5), motif="Hors périmètre", by=chef)
    assert (
        exc.value.message
        == "Seules les missions de conseil peuvent avoir des étapes non applicables."
    )
    Mission.objects.filter(pk=mission_lancee.pk).update(type=TypeMission.CONSEIL)
    with pytest.raises(RegleMetierError) as exc:
        marquer_non_applicable(etape_n(mission_lancee, 6), motif="Hors périmètre", by=chef)
    assert exc.value.message == "Un jalon ne peut pas être marqué non applicable."
    with pytest.raises(RegleMetierError) as exc:
        marquer_non_applicable(etape_n(mission_lancee, 5), motif=" ", by=chef)
    assert exc.value.errors["motif"] == ["Le motif est obligatoire."]


def test_retablir(mission_lancee: Mission, chef: User) -> None:
    Mission.objects.filter(pk=mission_lancee.pk).update(type=TypeMission.CONSEIL)
    etape = marquer_non_applicable(etape_n(mission_lancee, 5), motif="Hors périmètre", by=chef)
    assert etape.statut == StatutEtape.NON_APPLICABLE
    assert etape.motif_non_applicable == "Hors périmètre"
    etape = retablir_etape(etape_n(mission_lancee, 5), by=chef)
    assert etape.statut == StatutEtape.A_FAIRE
    types = list(
        EvenementEtape.objects.filter(etape__mission=mission_lancee, etape__numero=5).values_list(
            "type", flat=True
        )
    )
    assert types == [TypeEvenementEtape.NON_APPLICABLE, TypeEvenementEtape.RETABLIE]


def test_evenement_par_transition_avec_motif(mission_lancee: Mission, rai: User) -> None:
    forcer_etapes(mission_lancee, {6: StatutEtape.TERMINEE})
    renvoyer_etape(etape_n(mission_lancee, 6), motif="Référentiel incomplet", by=rai)
    assert etape_n(mission_lancee, 6).statut == StatutEtape.RENVOYEE
    evenement = EvenementEtape.objects.get(etape__mission=mission_lancee, etape__numero=6)
    assert (evenement.type, evenement.motif, evenement.par) == (
        TypeEvenementEtape.RENVOYEE,
        "Référentiel incomplet",
        rai,
    )
    assert (evenement.statut_avant, evenement.statut_apres) == ("TERMINEE", "RENVOYEE")
    with pytest.raises(RegleMetierError) as exc:
        rouvrir_etape(etape_n(mission_lancee, 4), motif="", by=rai)
    assert exc.value.errors["motif"] == ["Le motif est obligatoire."]
    with pytest.raises(RegleMetierError) as exc:
        renvoyer_etape(etape_n(mission_lancee, 6), motif="", by=rai)
    assert exc.value.errors["motif"] == ["Le motif est obligatoire."]


def test_planifier_etape(mission_lancee: Mission, chef: User, auditeur_mission: User) -> None:
    etape = planifier_etape(
        etape_n(mission_lancee, 3),
        by=chef,
        date_debut_prevue=date(2026, 3, 1),
        date_fin_prevue=date(2026, 3, 10),
        charge_prevue_jours=Decimal("4.5"),
    )
    assert etape.charge_prevue_jours == Decimal("4.5")
    with pytest.raises(RegleMetierError) as exc:
        planifier_etape(
            etape_n(mission_lancee, 3),
            by=chef,
            date_debut_prevue=date(2026, 3, 10),
            date_fin_prevue=date(2026, 3, 1),
        )
    assert "date_fin_prevue" in exc.value.errors
    with pytest.raises(RegleMetierError) as exc:
        planifier_etape(etape_n(mission_lancee, 3), by=chef, charge_prevue_jours=Decimal("-1"))
    assert "charge_prevue_jours" in exc.value.errors
    with pytest.raises(PermissionDenied):
        planifier_etape(etape_n(mission_lancee, 3), by=auditeur_mission, charge_prevue_jours=1)


CAS_ACTIONS = [
    # (utilisateur, numéro, statut, type de mission, actions attendues)
    ("rai", 3, "A_FAIRE", "ASSURANCE", {A.DEMARRER, A.PLANIFIER}),
    ("chef", 3, "A_FAIRE", "ASSURANCE", {A.DEMARRER, A.PLANIFIER}),
    ("chef", 3, "A_FAIRE", "CONSEIL", {A.DEMARRER, A.PLANIFIER, A.NON_APPLICABLE}),
    ("auditeur", 3, "A_FAIRE", "ASSURANCE", {A.DEMARRER}),
    ("chef", 12, "A_FAIRE", "ASSURANCE", {A.PLANIFIER}),
    ("chef", 3, "EN_COURS", "ASSURANCE", {A.TERMINER, A.PLANIFIER}),
    ("rai", 3, "EN_COURS", "ASSURANCE", {A.PLANIFIER}),
    ("auditeur", 3, "EN_COURS", "ASSURANCE", set()),
    ("chef", 1, "EN_COURS", "ASSURANCE", {A.PLANIFIER}),
    ("rai", 6, "TERMINEE", "ASSURANCE", {A.VALIDER, A.RENVOYER, A.ROUVRIR, A.PLANIFIER}),
    ("superviseur", 6, "TERMINEE", "ASSURANCE", {A.VALIDER, A.RENVOYER, A.ROUVRIR}),
    ("chef", 6, "TERMINEE", "ASSURANCE", {A.PLANIFIER}),
    ("rai", 6, "A_REVALIDER", "ASSURANCE", {A.VALIDER, A.ROUVRIR, A.PLANIFIER}),
    ("rai", 5, "VALIDEE", "ASSURANCE", {A.ROUVRIR, A.PLANIFIER}),
    ("rai", 5, "TERMINEE", "ASSURANCE", {A.ROUVRIR, A.PLANIFIER}),
    ("rai", 5, "NON_APPLICABLE", "CONSEIL", {A.PLANIFIER}),
    ("chef", 5, "NON_APPLICABLE", "CONSEIL", {A.RETABLIR, A.PLANIFIER}),
    ("chef", 6, "EN_COURS", "CONSEIL", {A.TERMINER, A.PLANIFIER}),
    ("chef", 4, "RENVOYEE", "ASSURANCE", {A.TERMINER, A.PLANIFIER}),
]


@pytest.mark.parametrize(("qui", "numero", "statut", "type_mission", "attendues"), CAS_ACTIONS)
def test_actions_possibles_par_role_et_statut(
    mission_lancee: Mission,
    rai: User,
    chef: User,
    auditeur_mission: User,
    superviseur: User,
    qui: str,
    numero: int,
    statut: str,
    type_mission: str,
    attendues: set[str],
) -> None:
    utilisateurs = {
        "rai": rai,
        "chef": chef,
        "auditeur": auditeur_mission,
        "superviseur": superviseur,
    }
    Mission.objects.filter(pk=mission_lancee.pk).update(type=type_mission)
    forcer_etapes(mission_lancee, {numero: statut})
    resultat = actions_possibles(etape_n(mission_lancee, numero), utilisateurs[qui])
    assert set(resultat) == attendues


def test_actions_possibles_vide_si_mission_figee_ou_hors_phase(
    mission_lancee: Mission, rai: User
) -> None:
    en_phase(mission_lancee, StatutMission.PLANIFIEE)
    assert actions_possibles(etape_n(mission_lancee, 3), rai) == []
    en_phase(mission_lancee, StatutMission.SUSPENDUE)
    assert actions_possibles(etape_n(mission_lancee, 3), rai) == []


def test_actions_possibles_sans_declaration_confirmee(mission_lancee: Mission) -> None:
    sans = make_user(Role.AUDITEUR)
    affecter(mission_lancee, sans, RoleMission.CHEF_MISSION, confirmee=False)
    assert actions_possibles(etape_n(mission_lancee, 3), sans) == []


def test_actions_possibles_liste_de_18_etapes_en_peu_de_requetes(
    mission_lancee: Mission,
    chef: User,
    django_assert_max_num_queries: DjangoAssertNumQueries,
) -> None:
    mission = Mission.objects.get(pk=mission_lancee.pk)
    with django_assert_max_num_queries(4):
        contexte = contexte_actions(mission, chef)
        etapes = list(EtapeMission.objects.filter(mission=mission))
        resultats = {e.numero: actions_possibles(e, chef, contexte=contexte) for e in etapes}
    assert len(resultats) == 18
    assert A.PLANIFIER in resultats[3]
    assert A.DEMARRER in resultats[3]


def test_phase_bloquee_si_une_etape_precedente_est_rouverte(
    mission_lancee: Mission, rai: User
) -> None:
    en_phase(mission_lancee, StatutMission.EN_ACCOMPLISSEMENT)
    forcer_etapes(
        mission_lancee,
        {n: StatutEtape.TERMINEE for n in range(1, 15)} | {10: StatutEtape.EN_COURS},
    )
    valider_etape(etape_n(mission_lancee, 13), by=rai)
    assert statut_mission(mission_lancee) == StatutMission.EN_ACCOMPLISSEMENT
    forcer_etapes(mission_lancee, {10: StatutEtape.TERMINEE})
    assert avancer_phase(mission_lancee, by=rai) is True


def test_droit_verifie_avant_motif_et_etat(
    mission_lancee: Mission, auditeur_mission: User, chef: User
) -> None:
    forcer_etapes(mission_lancee, {6: StatutEtape.TERMINEE})
    with pytest.raises(PermissionDenied):
        rouvrir_etape(etape_n(mission_lancee, 6), motif="", by=auditeur_mission)
    with pytest.raises(PermissionDenied):
        renvoyer_etape(etape_n(mission_lancee, 6), motif="", by=chef)
    with pytest.raises(PermissionDenied):
        marquer_non_applicable(etape_n(mission_lancee, 5), motif="", by=auditeur_mission)
    with pytest.raises(PermissionDenied):
        valider_etape(etape_n(mission_lancee, 5), by=auditeur_mission)


def test_renvoyer_efface_la_date_de_fin_reelle(mission_lancee: Mission, rai: User) -> None:
    EtapeMission.objects.filter(mission=mission_lancee, numero=6).update(
        statut=StatutEtape.TERMINEE, date_fin_reelle=date(2026, 3, 13)
    )
    etape = renvoyer_etape(etape_n(mission_lancee, 6), motif="À reprendre", by=rai)
    assert etape.date_fin_reelle is None
