from datetime import date
from typing import Any

import pytest
from auditlog.models import LogEntry
from django.utils import timezone

from apps.core.exceptions import RegleMetierError
from apps.missions.exceptions import EtapeCloseError, MissionFigeeError
from apps.missions.models import (
    EtapeMission,
    EvenementEtape,
    Mission,
    StatutEtape,
    StatutMission,
    TypeEvenementEtape,
)
from apps.missions.services.declarations import arbitrer_conflit, confirmer_declaration
from apps.missions.services.equipe import affecter, desaffecter, remplacer_chef
from apps.missions.services.missions import (
    annuler_mission,
    creer_mission,
    emettre_ordre_mission,
    lancer_mission,
    modifier_mission,
    planifier_mission,
    reprendre_mission,
    supprimer_mission,
    suspendre_mission,
)
from apps.referentiel.models import CartographieVersion
from apps.signatures.models import TypeDocumentSignable
from apps.signatures.services import verifier
from apps.users.models import Role, User
from tests.factories import (
    CartographieVersionFactory,
    DirectionFactory,
    MissionFactory,
    ProcessusFactory,
    make_user,
)

MSG_CHEF = "Désignez un chef de mission avant de lancer la mission."


@pytest.fixture
def cartographie_validee(db: None) -> CartographieVersion:
    return MissionFactory().cartographie


def brouillon_complet(rai: User, **champs: Any) -> Mission:
    base: dict[str, Any] = {
        "date_debut_prevue": date(2026, 3, 1),
        "date_fin_prevue": date(2026, 5, 1),
    }
    return creer_mission(
        titre="Audit de la facturation",
        type="ASSURANCE",
        by=rai,
        processus=[ProcessusFactory()],
        entites=[DirectionFactory()],
        **(base | champs),
    )


def test_creation_cree_18_etapes_a_faire(rai: User, cartographie_validee: CartographieVersion):
    mission = brouillon_complet(rai)
    assert mission.statut == StatutMission.BROUILLON
    assert mission.reference == ""
    assert mission.cartographie == cartographie_validee
    etapes = list(mission.etapes.order_by("numero"))
    assert [e.numero for e in etapes] == list(range(1, 19))
    assert {e.statut for e in etapes} == {StatutEtape.A_FAIRE}
    assert mission.processus.count() == 1
    assert mission.entites.count() == 1
    assert mission.created_by == rai


def test_creation_sans_cartographie_validee_422(db: None, rai: User):
    CartographieVersionFactory()  # brouillon seulement
    with pytest.raises(RegleMetierError) as e:
        creer_mission(titre="Audit", type="ASSURANCE", by=rai)
    assert e.value.errors["cartographie"] == [
        "Aucune cartographie des risques validée : validez une cartographie "
        "avant de créer une mission."
    ]
    assert not Mission.objects.exists()


def test_creation_champs_invalides_par_champ(rai: User, cartographie_validee: CartographieVersion):
    with pytest.raises(RegleMetierError) as e:
        creer_mission(titre="", type="INCONNU", by=rai)
    assert {"titre", "type"} <= set(e.value.errors)


def test_creation_dates_incoherentes(rai: User, cartographie_validee: CartographieVersion):
    with pytest.raises(RegleMetierError) as e:
        creer_mission(
            titre="A",
            type="ASSURANCE",
            by=rai,
            date_debut_prevue=date(2026, 5, 1),
            date_fin_prevue=date(2026, 3, 1),
        )
    assert "date_fin_prevue" in e.value.errors


def test_cartographie_inchangee_si_plus_recente_validee(
    rai: User, cartographie_validee: CartographieVersion
):
    mission = brouillon_complet(rai)
    plus_recente = CartographieVersionFactory(annee=cartographie_validee.annee + 1)
    CartographieVersion._base_manager.filter(pk=plus_recente.pk).update(  # noqa: SLF001
        statut="VALIDEE", validee_le=timezone.now(), validee_par=rai
    )
    mission = modifier_mission(mission, by=rai, budget_jours=5)
    assert mission.cartographie == cartographie_validee


def test_modifier_mission_champs_et_m2m(rai: User, cartographie_validee: CartographieVersion):
    mission = brouillon_complet(rai)
    nouveau = ProcessusFactory()
    mission = modifier_mission(mission, by=rai, objectifs="Évaluer", processus=[nouveau])
    mission.refresh_from_db()
    assert mission.objectifs == "Évaluer"
    assert list(mission.processus.all()) == [nouveau]
    with pytest.raises(ValueError, match="reference"):
        modifier_mission(mission, by=rai, reference="DAI/2026/M99")


def test_supprimer_brouillon_logiquement(rai: User, cartographie_validee: CartographieVersion):
    mission = brouillon_complet(rai)
    pk = mission.pk
    supprimer_mission(mission, by=rai)
    assert not Mission.objects.filter(pk=pk).exists()
    assert Mission.all_objects.get(pk=pk).deleted_at is not None
    assert not EtapeMission.objects.filter(mission_id=pk).exists()
    assert EtapeMission.all_objects.filter(mission_id=pk).count() == 18


def test_supprimer_hors_brouillon_refuse(rai: User, cartographie_validee: CartographieVersion):
    mission = planifier_mission(brouillon_complet(rai), by=rai)
    with pytest.raises(RegleMetierError) as e:
        supprimer_mission(mission, by=rai)
    assert "Seule une mission en brouillon peut être supprimée ; annulez-la." in e.value.message


def test_planifier_champs_manquants_par_champ(rai: User, cartographie_validee: CartographieVersion):
    mission = creer_mission(titre="Audit", type="ASSURANCE", by=rai)
    with pytest.raises(RegleMetierError) as e:
        planifier_mission(mission, by=rai)
    msg = ["Ce champ est obligatoire pour planifier la mission."]
    assert e.value.errors == {
        "processus": msg,
        "entites": msg,
        "date_debut_prevue": msg,
        "date_fin_prevue": msg,
    }
    assert Mission.objects.get(pk=mission.pk).statut == StatutMission.BROUILLON


def test_planifier_attribue_la_reference(rai: User, cartographie_validee: CartographieVersion):
    mission = planifier_mission(brouillon_complet(rai), by=rai)
    assert (mission.statut, mission.reference) == (StatutMission.PLANIFIEE, "DAI/2026/M01")
    assert (mission.annee, mission.numero) == (2026, 1)
    suivante = planifier_mission(brouillon_complet(rai), by=rai)
    assert suivante.reference == "DAI/2026/M02"


def test_planifier_deux_fois_refuse(rai: User, cartographie_validee: CartographieVersion):
    mission = planifier_mission(brouillon_complet(rai), by=rai)
    with pytest.raises(RegleMetierError):
        planifier_mission(mission, by=rai)


def test_numero_jamais_reattribue(rai: User, cartographie_validee: CartographieVersion):
    supprimer_mission(brouillon_complet(rai), by=rai)  # un brouillon n'a pas de référence
    m1 = planifier_mission(brouillon_complet(rai), by=rai)
    assert m1.reference == "DAI/2026/M01"
    annuler_mission(m1, motif="Abandon du projet", by=rai)
    m2 = planifier_mission(brouillon_complet(rai), by=rai)
    assert m2.reference == "DAI/2026/M02"
    autre = brouillon_complet(
        rai, date_debut_prevue=date(2027, 1, 5), date_fin_prevue=date(2027, 2, 5)
    )
    assert planifier_mission(autre, by=rai).reference == "DAI/2027/M01"


def test_reference_a_trois_chiffres(rai: User, cartographie_validee: CartographieVersion):
    MissionFactory(reference="DAI/2026/M99", annee=2026, numero=99, statut="PLANIFIEE")
    mission = planifier_mission(brouillon_complet(rai), by=rai)
    assert mission.reference == "DAI/2026/M100"


def test_lancer_sans_chef_refuse(rai: User, cartographie_validee: CartographieVersion):
    mission = planifier_mission(brouillon_complet(rai), by=rai)
    with pytest.raises(RegleMetierError) as e:
        lancer_mission(mission, by=rai)
    assert e.value.message == MSG_CHEF
    assert Mission.objects.get(pk=mission.pk).statut == StatutMission.PLANIFIEE


def test_lancer_demarre_l_etape_I(rai: User, cartographie_validee: CartographieVersion):
    mission = planifier_mission(brouillon_complet(rai), by=rai)
    affecter(mission, utilisateur=make_user(Role.AUDITEUR), role_mission="CHEF_MISSION", by=rai)
    mission = lancer_mission(mission, by=rai)
    assert mission.statut == StatutMission.EN_PLANIFICATION
    etape = mission.etapes.get(numero=1)
    assert etape.statut == StatutEtape.EN_COURS
    assert etape.date_debut_reelle is not None
    evt = EvenementEtape.objects.get(etape=etape)
    assert (evt.type, evt.par) == (TypeEvenementEtape.DEMARREE, rai)


def test_lancer_exige_planifiee(rai: User, cartographie_validee: CartographieVersion):
    with pytest.raises(RegleMetierError):
        lancer_mission(brouillon_complet(rai), by=rai)


@pytest.fixture
def mission_a_ordre(rai: User, cartographie_validee: CartographieVersion) -> Mission:
    mission = planifier_mission(
        brouillon_complet(
            rai,
            objectifs="Évaluer le dispositif de facturation",
            perimetre="Agences de Ouagadougou",
            exclusions="Recouvrement",
            clients="DG",
            livrables_attendus="Rapport d'audit",
        ),
        by=rai,
    )
    chef = make_user(Role.AUDITEUR, first_name="Issa", last_name="Zongo")
    affecter(mission, utilisateur=chef, role_mission="CHEF_MISSION", by=rai)
    return lancer_mission(mission, by=rai)


def test_emettre_ordre_refuse_sans_objectifs_ni_perimetre(
    rai: User, cartographie_validee: CartographieVersion
):
    mission = planifier_mission(brouillon_complet(rai), by=rai)
    affecter(mission, utilisateur=make_user(Role.AUDITEUR), role_mission="CHEF_MISSION", by=rai)
    mission = lancer_mission(mission, by=rai)
    with pytest.raises(RegleMetierError) as e:
        emettre_ordre_mission(mission, by=rai)
    assert set(e.value.errors) == {"objectifs", "perimetre"}


def test_emettre_ordre_termine_I_et_gele_les_champs(rai: User, mission_a_ordre: Mission):
    confirmation = emettre_ordre_mission(mission_a_ordre, by=rai, adresse_ip="10.0.0.1")
    mission = Mission.objects.get(pk=mission_a_ordre.pk)
    etape = mission.etapes.get(numero=1)
    assert etape.statut == StatutEtape.TERMINEE
    assert etape.terminee_par == rai
    assert etape.date_fin_reelle is not None
    assert mission.ordre_mission_emis_le is not None
    assert confirmation.type_document == TypeDocumentSignable.ORDRE_MISSION
    assert confirmation.signataire == rai
    assert confirmation.adresse_ip == "10.0.0.1"
    assert EvenementEtape.objects.filter(etape=etape, type=TypeEvenementEtape.TERMINEE).exists()
    with pytest.raises(EtapeCloseError):
        modifier_mission(mission, by=rai, objectifs="Autres objectifs")
    assert modifier_mission(mission, by=rai, budget_jours=12).budget_jours == 12


def test_emettre_ordre_snapshot_verifiable(rai: User, mission_a_ordre: Mission):
    c = emettre_ordre_mission(mission_a_ordre, by=rai)
    assert verifier(c)
    donnees = c.donnees
    assert donnees["reference"] == "DAI/2026/M01"
    assert donnees["objectifs"] == "Évaluer le dispositif de facturation"
    assert donnees["equipe"] == [{"nom": "Issa Zongo", "role_mission": "CHEF_MISSION"}]
    assert len(donnees["processus"]) == 1
    assert len(donnees["entites"]) == 1
    assert donnees["date_debut_prevue"] == "2026-03-01"
    assert "Responsable de l'Audit Interne, émets l'ordre de mission DAI/2026/M01" in c.texte
    assert "« Audit de la facturation »" in c.texte


def test_emettre_ordre_deux_fois_refuse(rai: User, mission_a_ordre: Mission):
    emettre_ordre_mission(mission_a_ordre, by=rai)
    with pytest.raises(RegleMetierError):
        emettre_ordre_mission(mission_a_ordre, by=rai)


def test_d17_m2m_gele_apres_emission(rai: User, mission_a_ordre: Mission):
    emettre_ordre_mission(mission_a_ordre, by=rai)
    mission = Mission.objects.get(pk=mission_a_ordre.pk)
    with pytest.raises(EtapeCloseError):
        modifier_mission(mission, by=rai, processus=[ProcessusFactory()])
    with pytest.raises(EtapeCloseError):
        modifier_mission(mission, by=rai, entites=[DirectionFactory()])
    # Les mêmes ensembles ne sont pas une modification.
    modifier_mission(
        mission,
        by=rai,
        processus=list(mission.processus.all()),
        entites=list(mission.entites.all()),
    )


@pytest.mark.parametrize(
    "statut", [StatutMission.EN_ACCOMPLISSEMENT, StatutMission.EN_COMMUNICATION]
)
def test_nouvelle_emission_apres_reouverture_de_I(rai: User, mission_a_ordre: Mission, statut: str):
    premiere = emettre_ordre_mission(mission_a_ordre, by=rai)
    Mission.objects.filter(pk=mission_a_ordre.pk).update(statut=statut)
    EtapeMission.objects.filter(mission=mission_a_ordre, numero=1).update(
        statut=StatutEtape.EN_COURS
    )
    seconde = emettre_ordre_mission(mission_a_ordre, by=rai)
    assert seconde.pk != premiere.pk and verifier(premiere) and verifier(seconde)
    assert mission_a_ordre.etapes.get(numero=1).statut == StatutEtape.TERMINEE
    mission = Mission.objects.get(pk=mission_a_ordre.pk)
    with pytest.raises(EtapeCloseError):
        modifier_mission(mission, by=rai, objectifs="Autres objectifs")


def test_emission_refusee_hors_phases(rai: User, mission_a_ordre: Mission):
    Mission.objects.filter(pk=mission_a_ordre.pk).update(statut=StatutMission.RAPPORT_DIFFUSE)
    with pytest.raises(RegleMetierError):
        emettre_ordre_mission(mission_a_ordre, by=rai)


def test_ordre_equipe_sans_audites(rai: User, mission_a_ordre: Mission):
    affecter(mission_a_ordre, utilisateur=make_user(Role.AUDITE), role_mission="AUDITE", by=rai)
    c = emettre_ordre_mission(mission_a_ordre, by=rai)
    assert [m["role_mission"] for m in c.donnees["equipe"]] == ["CHEF_MISSION"]


def test_message_mission_en_brouillon(rai: User, cartographie_validee: CartographieVersion):
    with pytest.raises(RegleMetierError) as e:
        lancer_mission(brouillon_complet(rai), by=rai)
    assert e.value.message == "Impossible de lancer la mission : la mission est en brouillon."


def test_factory_trait_ajoute_processus_et_entites(db: None):
    mission = MissionFactory(avec_processus_et_entites=True)
    assert mission.processus.count() == 1 and mission.entites.count() == 1
    assert MissionFactory().processus.count() == 0


def test_gel_mission_suspendue_toutes_ecritures(rai: User, mission_a_ordre: Mission):
    mission = mission_a_ordre
    nouvel_auditeur = make_user(Role.AUDITEUR)
    affectation = mission.affectations.get(role_mission="CHEF_MISSION")
    declaration = affectation.declaration
    suspendre_mission(mission, motif="Arrêt demandé par la DG", by=rai)
    ecritures = [
        lambda: modifier_mission(mission, by=rai, budget_jours=3),
        lambda: planifier_mission(mission, by=rai),
        lambda: lancer_mission(mission, by=rai),
        lambda: emettre_ordre_mission(mission, by=rai),
        lambda: suspendre_mission(mission, motif="Encore", by=rai),
        lambda: supprimer_mission(mission, by=rai),
        lambda: affecter(mission, utilisateur=nouvel_auditeur, role_mission="AUDITEUR", by=rai),
        lambda: desaffecter(affectation, by=rai),
        lambda: remplacer_chef(mission, utilisateur=nouvel_auditeur, by=rai),
        lambda: confirmer_declaration(declaration, by=affectation.utilisateur),
        lambda: arbitrer_conflit(declaration, justification="x", by=rai),
    ]
    for appel in ecritures:
        with pytest.raises(MissionFigeeError):
            appel()
    reprendre_mission(mission, by=rai)
    relue = Mission.objects.get(pk=mission.pk)
    assert relue.statut == StatutMission.EN_PLANIFICATION
    assert relue.statut_avant_suspension == ""


def test_suspendre_reprendre_annuler_regles(rai: User, cartographie_validee: CartographieVersion):
    brouillon = brouillon_complet(rai)
    with pytest.raises(RegleMetierError):
        suspendre_mission(brouillon, motif="x", by=rai)
    with pytest.raises(RegleMetierError):
        annuler_mission(brouillon, motif="x", by=rai)
    mission = planifier_mission(brouillon, by=rai)
    with pytest.raises(RegleMetierError) as e:
        suspendre_mission(mission, motif="  ", by=rai)
    assert "motif" in e.value.errors
    with pytest.raises(RegleMetierError):
        reprendre_mission(mission, by=rai)
    suspendre_mission(mission, motif="Budget gelé", by=rai)
    mission = Mission.objects.get(pk=mission.pk)
    assert (mission.statut, mission.statut_avant_suspension, mission.motif_suspension) == (
        StatutMission.SUSPENDUE,
        StatutMission.PLANIFIEE,
        "Budget gelé",
    )
    # Une mission suspendue peut être annulée (D2) ; une mission annulée est définitive.
    with pytest.raises(RegleMetierError) as e:
        annuler_mission(mission, motif="", by=rai)
    assert "motif" in e.value.errors
    annuler_mission(mission, motif="Plus d'objet", by=rai)
    mission = Mission.objects.get(pk=mission.pk)
    assert (mission.statut, mission.motif_annulation) == (StatutMission.ANNULEE, "Plus d'objet")
    with pytest.raises(MissionFigeeError):
        modifier_mission(mission, by=rai, budget_jours=1)
    with pytest.raises(RegleMetierError):
        reprendre_mission(mission, by=rai)
    with pytest.raises(RegleMetierError):
        annuler_mission(mission, motif="encore", by=rai)


def test_transitions_historisees_avec_motif(rai: User, cartographie_validee: CartographieVersion):
    mission = planifier_mission(brouillon_complet(rai), by=rai)
    suspendre_mission(mission, motif="Arrêt demandé par la DG", by=rai)
    reprendre_mission(mission, by=rai)
    annuler_mission(mission, motif="Abandon", by=rai)
    entrees = LogEntry.objects.get_for_object(Mission.objects.get(pk=mission.pk))
    changements = [e.changes_dict for e in entrees]
    assert any(
        c.get("motif_suspension", [None, None])[1] == "Arrêt demandé par la DG" for c in changements
    )
    assert any(c.get("motif_annulation", [None, None])[1] == "Abandon" for c in changements)
    assert any(c.get("statut", [None, None])[1] == StatutMission.SUSPENDUE for c in changements)
    assert rai in {e.actor for e in entrees}
