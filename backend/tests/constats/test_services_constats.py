import pytest
from django.core.exceptions import PermissionDenied

from apps.constats.models import (
    CauseConstat,
    Constat,
    EvenementConstat,
    Recommandation,
    StatutConstat,
)
from apps.constats.services.constats import (
    creer_constat,
    modifier_constat,
    renvoyer_constat,
    rouvrir_constat,
    soumettre_constat,
    supprimer_constat,
    valider_constat,
)
from apps.core.exceptions import RegleMetierError
from apps.missions.exceptions import EtapeCloseError, MissionFigeeError
from apps.missions.models import Mission, StatutEtape, StatutMission
from apps.signatures.services import empreinte, normaliser
from apps.users.models import Role, User
from tests.constats.factories import fiche_anomalie
from tests.factories import DirectionFactory, MissionFactory, ProcessusFactory, make_user
from tests.missions.conftest import affecter, forcer_etapes

pytestmark = pytest.mark.django_db

MSG_XIV = "Commencez l'étape XIV pour rédiger les constats."


@pytest.fixture
def rai() -> User:
    return make_user(Role.RAI)


@pytest.fixture
def superviseur(mission_en_xiv: Mission) -> User:
    user = make_user(Role.AUDITEUR)
    affecter(mission_en_xiv, user, "SUPERVISEUR")
    return user


@pytest.fixture
def champs(mission_en_xiv: Mission) -> dict[str, object]:
    entite, processus = DirectionFactory(), ProcessusFactory()
    forcer_etapes(mission_en_xiv, {1: StatutEtape.EN_COURS})
    mission_en_xiv.entites.add(entite)
    mission_en_xiv.processus.add(processus)
    forcer_etapes(mission_en_xiv, {1: StatutEtape.VALIDEE})
    return {"entite": entite, "processus": processus}


def _complet(mission: Mission, chef: User, champs: dict[str, object]) -> Constat:
    return creer_constat(
        mission,
        titre="Rapprochements absents",
        by=chef,
        fiches=[fiche_anomalie(mission)],
        causes=[{"categorie": "METHODES", "description": "Pas de procédure."}],
        recommandations=[{"libelle": "Formaliser.", "priorite": "HAUTE"}],
        fait_constate="Fait",
        referentiel="Critère",
        consequence="Risque",
        probabilite=3,
        impact=5,
        **champs,
    )


def test_creation_complete(mission_en_xiv: Mission, chef: User, champs: dict[str, object]) -> None:
    c = _complet(mission_en_xiv, chef, champs)
    assert c.reference == "C-01"
    assert c.score == 15
    assert c.niveau == "ELEVE"
    assert c.causes.count() == 1
    assert c.recommandations.get().priorite == "HAUTE"
    assert _complet(mission_en_xiv, chef, champs).reference == "C-02"


def test_references_croisees_refusees(
    mission_en_xiv: Mission, chef: User, champs: dict[str, object]
) -> None:
    autre = MissionFactory()
    fiche_autre = fiche_anomalie(autre)
    with pytest.raises(RegleMetierError) as e:
        creer_constat(mission_en_xiv, titre="T", by=chef, fiches=[fiche_autre], **champs)
    assert e.value.message == f"La fiche {fiche_autre.pk} n'appartient pas à la mission."
    with pytest.raises(RegleMetierError) as e:
        creer_constat(
            mission_en_xiv,
            titre="T",
            by=chef,
            entite=DirectionFactory(),
            processus=champs["processus"],
        )
    assert e.value.message == "L'entité doit être une entité de la mission."
    with pytest.raises(RegleMetierError) as e:
        creer_constat(
            mission_en_xiv,
            titre="T",
            by=chef,
            entite=champs["entite"],
            processus=ProcessusFactory(),
        )
    assert e.value.message == "Le processus doit être un processus de la mission."


def test_creation_atomique_ne_consomme_pas_de_numero(
    mission_en_xiv: Mission, chef: User, champs: dict[str, object]
) -> None:
    with pytest.raises(RegleMetierError):
        creer_constat(
            mission_en_xiv,
            titre="T",
            by=chef,
            causes=[{"categorie": "INCONNUE", "description": "x"}],
            **champs,
        )
    assert not Constat.all_objects.filter(mission=mission_en_xiv).exists()
    assert not CauseConstat.all_objects.filter(mission=mission_en_xiv).exists()
    assert creer_constat(mission_en_xiv, titre="T", by=chef, **champs).reference == "C-01"


def test_numero_jamais_reattribue(
    mission_en_xiv: Mission, chef: User, champs: dict[str, object]
) -> None:
    c = creer_constat(mission_en_xiv, titre="T", by=chef, **champs)
    supprimer_constat(c, by=chef)
    assert creer_constat(mission_en_xiv, titre="T", by=chef, **champs).reference == "C-02"


def test_soumettre_exigences_par_champ(
    mission_en_xiv: Mission, chef: User, champs: dict[str, object]
) -> None:
    c = creer_constat(mission_en_xiv, titre="T", by=chef, **champs)
    with pytest.raises(RegleMetierError) as e:
        soumettre_constat(c, by=chef)
    assert set(e.value.errors) == {
        "fait_constate",
        "referentiel",
        "consequence",
        "probabilite",
        "impact",
        "causes",
        "recommandations",
        "fiches",
    }
    c.refresh_from_db()
    assert c.statut == StatutConstat.BROUILLON


def test_soumission_fige_la_version(
    mission_en_xiv: Mission, chef: User, champs: dict[str, object]
) -> None:
    c = _complet(mission_en_xiv, chef, champs)
    soumettre_constat(c, by=chef)
    c.refresh_from_db()
    assert (c.statut, c.cycle, c.soumis_par) == (StatutConstat.SOUMIS, 1, chef)
    assert len(c.empreinte_soumise) == 64
    # recalculée depuis la version relue en base : l'empreinte stockée reste vérifiable
    relu = Constat.objects.get(pk=c.pk)
    assert relu.empreinte_soumise == empreinte(
        f"{relu.reference} {relu.titre}", normaliser(relu.version_soumise)
    )
    assert c.version_soumise["causes"][0]["categorie"] == "METHODES"
    assert EvenementConstat.objects.filter(constat=c, type="SOUMIS").count() == 1


def test_soumettre_reserve_au_chef_ou_rai(
    mission_en_xiv: Mission, chef: User, auditeur_mission: User, champs: dict[str, object]
) -> None:
    c = _complet(mission_en_xiv, chef, champs)
    with pytest.raises(PermissionDenied):
        soumettre_constat(c, by=auditeur_mission)


def test_valideur_auteur_ou_soumetteur_refuse(
    mission_en_xiv: Mission, chef: User, rai: User, champs: dict[str, object]
) -> None:
    c = _complet(mission_en_xiv, rai, champs)
    soumettre_constat(c, by=chef)
    with pytest.raises(PermissionDenied):
        valider_constat(c, by=rai)  # auteur
    sup = make_user(Role.AUDITEUR)
    affecter(mission_en_xiv, sup, "SUPERVISEUR")
    c2 = _complet(mission_en_xiv, chef, champs)
    soumettre_constat(c2, by=rai)
    with pytest.raises(PermissionDenied):
        valider_constat(c2, by=rai)  # soumetteur
    assert valider_constat(c2, by=sup).statut == StatutConstat.VALIDE


def test_cycle_complet_renvoi_resoumission_reouverture(
    mission_en_xiv: Mission, chef: User, rai: User, champs: dict[str, object]
) -> None:
    c = _complet(mission_en_xiv, chef, champs)
    soumettre_constat(c, by=chef)
    with pytest.raises(RegleMetierError):
        renvoyer_constat(c, motif=" ", by=rai)
    renvoyer_constat(c, motif="À préciser", by=rai)
    c.refresh_from_db()
    assert c.statut == StatutConstat.RENVOYE
    soumettre_constat(c, by=chef)
    c.refresh_from_db()
    assert c.cycle == 2
    valider_constat(c, by=rai)
    c.refresh_from_db()
    assert c.statut == StatutConstat.VALIDE
    with pytest.raises(RegleMetierError):
        modifier_constat(c, by=chef, titre="x")
    rouvrir_constat(c, motif="Erreur", by=rai)
    c.refresh_from_db()
    assert c.statut == StatutConstat.BROUILLON
    assert EvenementConstat.objects.filter(constat=c).count() == 5


def test_resoumission_incremente_le_cycle_et_garde_les_reponses(
    mission_en_xiv: Mission, chef: User, rai: User, audite_affecte: User, champs: dict[str, object]
) -> None:
    from apps.constats.services.reponses import repondre

    c = _complet(mission_en_xiv, chef, champs)
    soumettre_constat(c, by=chef)
    c.refresh_from_db()
    audite_affecte.direction_code = champs["entite"].code  # type: ignore[attr-defined]
    audite_affecte.save(update_fields=["direction_code"])
    repondre(
        c,
        position="ACCORD",
        commentaire="",
        by=audite_affecte,
        empreinte_soumise=c.empreinte_soumise,
    )
    renvoyer_constat(c, motif="Revoir", by=rai)
    soumettre_constat(c, by=chef)
    c.refresh_from_db()
    assert c.cycle == 2
    assert c.reponses.count() == 1


def test_remplacement_des_causes_et_recommandations(
    mission_en_xiv: Mission, chef: User, champs: dict[str, object]
) -> None:
    c = _complet(mission_en_xiv, chef, champs)
    cause = c.causes.get()
    modifier_constat(
        c,
        by=chef,
        causes=[
            {"id": str(cause.pk), "categorie": "MATERIEL", "description": "Outil absent."},
            {"categorie": "MILIEU", "description": "Locaux."},
        ],
        recommandations=[{"libelle": "Autre.", "priorite": "FAIBLE"}],
    )
    assert sorted(c.causes.values_list("categorie", flat=True)) == ["MATERIEL", "MILIEU"]
    assert c.causes.get(pk=cause.pk).description == "Outil absent."
    assert [r.libelle for r in c.recommandations.all()] == ["Autre."]
    assert Recommandation.all_objects.filter(constat=c).count() == 2  # l'ancienne est supprimée
    with pytest.raises(RegleMetierError):
        modifier_constat(
            c,
            by=chef,
            causes=[
                {
                    "id": "00000000-0000-0000-0000-000000000000",
                    "categorie": "MATERIEL",
                    "description": "x",
                }
            ],
        )


def test_supprimer_seulement_brouillon_ou_renvoye(
    mission_en_xiv: Mission, chef: User, rai: User, champs: dict[str, object]
) -> None:
    c = _complet(mission_en_xiv, chef, champs)
    soumettre_constat(c, by=chef)
    with pytest.raises(RegleMetierError):
        supprimer_constat(c, by=chef)


def test_ecritures_refusees_xiv_fermee_ou_non_commencee(
    mission_en_xiv: Mission, chef: User, champs: dict[str, object]
) -> None:
    c = _complet(mission_en_xiv, chef, champs)
    forcer_etapes(mission_en_xiv, {14: StatutEtape.TERMINEE})
    for appel in (
        lambda: creer_constat(mission_en_xiv, titre="T", by=chef, **champs),
        lambda: modifier_constat(c, by=chef, titre="x"),
        lambda: soumettre_constat(c, by=chef),
        lambda: supprimer_constat(c, by=chef),
    ):
        with pytest.raises(EtapeCloseError):
            appel()
    forcer_etapes(mission_en_xiv, {14: StatutEtape.A_FAIRE})
    with pytest.raises(RegleMetierError) as e:
        modifier_constat(c, by=chef, titre="x")
    assert e.value.message == MSG_XIV
    forcer_etapes(mission_en_xiv, {14: StatutEtape.RENVOYEE})
    modifier_constat(c, by=chef, titre="ok")


def test_gel_suspendue_toutes_ecritures_lot6_constats(
    mission_en_xiv: Mission, chef: User, rai: User, champs: dict[str, object]
) -> None:
    brouillon = _complet(mission_en_xiv, chef, champs)
    soumis = _complet(mission_en_xiv, chef, champs)
    soumettre_constat(soumis, by=chef)
    valide = _complet(mission_en_xiv, chef, champs)
    soumettre_constat(valide, by=chef)
    valider_constat(valide, by=rai)
    Mission.objects.filter(pk=mission_en_xiv.pk).update(statut=StatutMission.SUSPENDUE)
    for appel in (
        lambda: creer_constat(mission_en_xiv, titre="T", by=chef, **champs),
        lambda: modifier_constat(brouillon, by=chef, titre="x"),
        lambda: soumettre_constat(brouillon, by=chef),
        lambda: supprimer_constat(brouillon, by=chef),
        lambda: valider_constat(soumis, by=rai),
        lambda: renvoyer_constat(soumis, motif="m", by=rai),
        lambda: rouvrir_constat(valide, motif="m", by=rai),
    ):
        with pytest.raises(MissionFigeeError):
            appel()
    assert Constat.objects.get(pk=soumis.pk).statut == StatutConstat.SOUMIS
    assert Constat.objects.get(pk=valide.pk).statut == StatutConstat.VALIDE


def test_droits_contribuer(
    mission_en_xiv: Mission, audite_affecte: User, champs: dict[str, object]
) -> None:
    with pytest.raises(PermissionDenied):
        creer_constat(mission_en_xiv, titre="T", by=audite_affecte, **champs)
