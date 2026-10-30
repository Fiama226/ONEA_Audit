# ruff: noqa: F811
from django.utils import timezone

from apps.communication.droits import (
    ACCUSER_RECEPTION,
    CORRIGER,
    DIFFUSER,
    RENVOYER,
    VALIDER,
    actions_rapport,
    contexte_rapport,
    rapports_diffuses_visibles,
)
from apps.communication.models import Rapport
from apps.communication.services.correction import emettre_rapport_corrige
from apps.missions.models import Mission, RoleMission
from apps.users.models import Role, User
from tests.communication.factories import RapportFactory
from tests.communication.support_t8 import (  # noqa: F401
    admin,
    dg,
    rapport_diffuse,
    rapport_soumis_reel,
    rapport_valide,
)
from tests.factories import MissionFactory, make_user
from tests.missions.conftest import affecter


def _actions(rapport: Rapport, user: User) -> list[str]:
    rapport = Rapport.all_objects.get(pk=rapport.pk)
    mission = Mission.objects.get(pk=rapport.mission_id)
    return actions_rapport(rapport, user, contexte=contexte_rapport(mission, user))


def test_rai_valide_et_renvoie_le_rapport_soumis(
    rapport_soumis_reel: Rapport, rai: User, chef: User, admin: User, dg: User
) -> None:
    assert _actions(rapport_soumis_reel, rai) == [VALIDER, RENVOYER]
    for autre in (chef, admin, dg):
        assert _actions(rapport_soumis_reel, autre) == []


def test_superviseur_n_a_aucune_action_de_validation(rapport_soumis_reel: Rapport) -> None:
    superviseur = make_user(Role.AUDITEUR)
    affecter(rapport_soumis_reel.mission, superviseur, RoleMission.SUPERVISEUR)
    assert _actions(rapport_soumis_reel, superviseur) == []


def test_l_auteur_de_la_soumission_ne_peut_pas_valider(rapport_soumis_reel: Rapport) -> None:
    rai = make_user(Role.RAI)
    Rapport.objects.filter(pk=rapport_soumis_reel.pk)  # lecture seule : l'écriture est gelée
    rapport = Rapport.all_objects.get(pk=rapport_soumis_reel.pk)
    rapport.soumis_par = rai  # instance non sauvegardée : suffit au calcul pur
    mission = Mission.objects.get(pk=rapport.mission_id)
    actions = actions_rapport(rapport, rai, contexte=contexte_rapport(mission, rai))
    assert actions == [RENVOYER]


def test_diffuser_apres_validation(rapport_valide: Rapport, rai: User, chef: User) -> None:
    assert _actions(rapport_valide, rai) == [DIFFUSER]
    assert _actions(rapport_valide, chef) == []


def test_apres_diffusion_corriger_et_accuser(
    rapport_diffuse: Rapport, rai: User, chef: User, dg: User, admin: User
) -> None:
    assert _actions(rapport_diffuse, rai) == [CORRIGER]
    assert _actions(rapport_diffuse, dg) == [ACCUSER_RECEPTION]
    assert _actions(rapport_diffuse, chef) == [ACCUSER_RECEPTION]
    assert _actions(rapport_diffuse, admin) == []


def test_accuse_donne_ne_se_propose_plus(rapport_diffuse: Rapport, dg: User) -> None:
    from apps.communication.services.diffusion import accuser_reception

    accuser_reception(rapport_diffuse, by=dg)
    assert _actions(rapport_diffuse, dg) == []


def test_rapport_remplace_sans_action(rapport_diffuse: Rapport, rai: User, dg: User) -> None:
    emettre_rapport_corrige(rapport_diffuse, motif="Erreur.", by=rai)
    assert _actions(rapport_diffuse, rai) == []
    assert _actions(rapport_diffuse, dg) == []


def test_rapports_diffuses_visibles_par_role(
    rapport_diffuse: Rapport,
    rai: User,
    dg: User,
    admin: User,
    chef: User,
    auditeur_mission: User,
    audite_affecte: User,
) -> None:
    Mission.objects.filter(pk=rapport_diffuse.mission_id).update(
        ordre_mission_emis_le=timezone.now()
    )
    autre = RapportFactory(mission=MissionFactory(), statut="BROUILLON")
    visibles = {r.pk for r in rapports_diffuses_visibles(dg)}
    assert visibles == {rapport_diffuse.pk} and autre.pk not in visibles
    assert {r.pk for r in rapports_diffuses_visibles(rai)} == {rapport_diffuse.pk}
    for membre in (chef, auditeur_mission, audite_affecte):
        assert {r.pk for r in rapports_diffuses_visibles(membre)} == {rapport_diffuse.pk}
    assert not rapports_diffuses_visibles(admin).exists()
    assert not rapports_diffuses_visibles(make_user(Role.AUDITEUR)).exists()
    assert not rapports_diffuses_visibles(make_user(Role.AUDITE)).exists()


def test_le_rapport_corrige_non_diffuse_n_est_pas_visible(
    rapport_diffuse: Rapport, rai: User, dg: User
) -> None:
    corrige = emettre_rapport_corrige(rapport_diffuse, motif="Erreur.", by=rai)
    visibles = {r.pk for r in rapports_diffuses_visibles(dg)}
    assert corrige.pk not in visibles and rapport_diffuse.pk in visibles
