import pytest
from django.core.exceptions import PermissionDenied

from apps.constats.exceptions import ReponseAjoutSeulError
from apps.constats.models import Constat, ReponseAudite
from apps.constats.services.constats import soumettre_constat, valider_constat
from apps.constats.services.reponses import derniere_reponse, repondre, texte_reponse
from apps.core.exceptions import RegleMetierError
from apps.missions.exceptions import EtapeCloseError
from apps.missions.models import Mission, StatutEtape, StatutMission
from apps.signatures.services import verifier
from apps.users.models import Role, User
from tests.constats.factories import ConstatFactory
from tests.factories import make_user
from tests.missions.conftest import affecter, forcer_etapes

pytestmark = pytest.mark.django_db


@pytest.fixture
def rai() -> User:
    return make_user(Role.RAI)


@pytest.fixture
def constat_soumis(mission_en_xiv: Mission, chef: User) -> Constat:
    c = ConstatFactory(mission=mission_en_xiv)
    soumettre_constat(c, by=chef)
    c.refresh_from_db()
    return c


def test_reponse_confirmee_et_verifiable(constat_soumis: Constat, audite_affecte: User) -> None:
    r = repondre(
        constat_soumis,
        position="DESACCORD",
        commentaire="Le contrôle existe : registre tenu à la DCL.",
        by=audite_affecte,
    )
    assert verifier(r.confirmation)
    assert r.confirmation.donnees["empreinte_soumise"] == constat_soumis.empreinte_soumise
    assert r.confirmation.donnees["position"] == "DESACCORD"
    assert r.cycle == 1
    assert derniere_reponse(constat_soumis) == r
    assert "en désaccord" in r.confirmation.texte


def test_desaccord_ne_bloque_pas_la_validation(
    constat_soumis: Constat, audite_affecte: User, rai: User
) -> None:
    repondre(constat_soumis, position="DESACCORD", commentaire="Motif", by=audite_affecte)
    assert valider_constat(constat_soumis, by=rai).statut == "VALIDE"
    # un constat validé reste répondable
    repondre(constat_soumis, position="ACCORD", commentaire="", by=audite_affecte)
    assert derniere_reponse(constat_soumis).position == "ACCORD"  # type: ignore[union-attr]
    assert constat_soumis.reponses.count() == 2


def test_desaccord_sans_motif_refuse_et_rien_ecrit(
    constat_soumis: Constat, audite_affecte: User
) -> None:
    with pytest.raises(RegleMetierError) as e:
        repondre(constat_soumis, position="DESACCORD", commentaire="  ", by=audite_affecte)
    assert e.value.errors["commentaire"] == ["Motivez votre désaccord."]
    assert not ReponseAudite.all_objects.exists()


def test_audite_d_une_autre_mission_ne_repond_pas(constat_soumis: Constat) -> None:
    autre = make_user(Role.AUDITE)
    with pytest.raises(PermissionDenied):
        repondre(constat_soumis, position="ACCORD", commentaire="", by=autre)
    # un auditeur (intervenant) ne répond pas non plus
    with pytest.raises(PermissionDenied):
        repondre(constat_soumis, position="ACCORD", commentaire="", by=make_user(Role.RAI))


def test_audite_affecte_a_une_autre_mission_refuse(
    constat_soumis: Constat,
) -> None:
    from tests.factories import MissionFactory

    autre_mission = MissionFactory()
    user = make_user(Role.AUDITE)
    affecter(autre_mission, user, "AUDITE")
    with pytest.raises(PermissionDenied):
        repondre(constat_soumis, position="ACCORD", commentaire="", by=user)


def test_reponse_sur_brouillon_refusee(mission_en_xiv: Mission, audite_affecte: User) -> None:
    brouillon = ConstatFactory(mission=mission_en_xiv)
    with pytest.raises(RegleMetierError):
        repondre(brouillon, position="ACCORD", commentaire="", by=audite_affecte)


def test_reponse_apres_XV_refusee(constat_soumis: Constat, audite_affecte: User) -> None:
    forcer_etapes(constat_soumis.mission, {15: StatutEtape.TERMINEE})
    with pytest.raises(EtapeCloseError):
        repondre(constat_soumis, position="ACCORD", commentaire="", by=audite_affecte)
    forcer_etapes(constat_soumis.mission, {15: StatutEtape.EN_COURS})
    repondre(constat_soumis, position="ACCORD", commentaire="", by=audite_affecte)


def test_reponse_mission_suspendue_refusee(constat_soumis: Constat, audite_affecte: User) -> None:
    Mission.objects.filter(pk=constat_soumis.mission_id).update(statut=StatutMission.SUSPENDUE)
    with pytest.raises(RegleMetierError):
        repondre(constat_soumis, position="ACCORD", commentaire="", by=audite_affecte)


def test_position_inconnue(constat_soumis: Constat, audite_affecte: User) -> None:
    with pytest.raises(RegleMetierError):
        repondre(constat_soumis, position="PEUT-ETRE", commentaire="", by=audite_affecte)


def test_reponse_ajout_seul(constat_soumis: Constat, audite_affecte: User) -> None:
    r = repondre(constat_soumis, position="ACCORD", commentaire="", by=audite_affecte)
    r.commentaire = "x"
    with pytest.raises(ReponseAjoutSeulError):
        r.save()


def test_texte_reponse(constat_soumis: Constat, audite_affecte: User) -> None:
    texte = texte_reponse(constat_soumis, "ACCORD", by=audite_affecte)
    assert texte.startswith(
        "Je soussigné(e) Awa Ouedraogo, Auditeur interne, déclare être en accord"
    )
    assert f"avec le constat {constat_soumis.reference} « {constat_soumis.titre} »" in texte
    assert constat_soumis.soumis_le.strftime("%d/%m/%Y") in texte  # type: ignore[union-attr]
