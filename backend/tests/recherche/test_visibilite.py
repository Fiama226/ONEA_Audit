"""Premier filtre (envoyé au moteur) : un filtre par rôle, `None` quand rien n'est lisible."""

from django.utils import timezone

from apps.missions.models import Mission
from apps.recherche.client import echapper_filtre
from apps.recherche.visibilite import ROLES_RECHERCHE, filtre_pour
from apps.users.models import Role, User


def test_roles_de_la_recherche() -> None:
    assert ROLES_RECHERCHE == (Role.RAI, Role.AUDITEUR, Role.AUDITE, Role.DG)


def test_rai_voit_l_audience_equipe(rai: User) -> None:
    assert filtre_pour(rai) == 'audience = "EQUIPE"'


def test_auditeur_limite_a_ses_missions(
    mission_lancee: Mission, auditeur_mission: User, autre_auditeur: User
) -> None:
    filtre = filtre_pour(auditeur_mission)
    assert filtre == f'mission_id IN ["{mission_lancee.pk}"] AND audience = "EQUIPE"'
    assert filtre_pour(autre_auditeur) is None


def test_audite_limite_a_ses_missions_et_a_l_audience_audite(
    mission_lancee: Mission, audite_affecte: User, autre_audite: User
) -> None:
    assert filtre_pour(audite_affecte) is None  # ordre de mission non émis
    Mission.objects.filter(pk=mission_lancee.pk).update(ordre_mission_emis_le=timezone.now())
    assert filtre_pour(audite_affecte) == (
        f'mission_id IN ["{mission_lancee.pk}"] AND audience = "AUDITE"'
    )
    assert filtre_pour(autre_audite) is None


def test_dg_limite_aux_missions_diffusees(
    mission_lancee: Mission, mission_en_suivi: Mission, dg: User
) -> None:
    assert mission_en_suivi.pk == mission_lancee.pk
    assert filtre_pour(dg) == f'mission_id IN ["{mission_en_suivi.pk}"] AND audience = "DG"'


def test_dg_sans_mission_diffusee_et_admin_sans_filtre(
    mission_lancee: Mission, dg: User, admin: User
) -> None:
    assert filtre_pour(dg) is None
    assert filtre_pour(admin) is None


def test_compte_inactif_sans_filtre(rai: User) -> None:
    User.objects.filter(pk=rai.pk).update(is_active=False)
    rai.refresh_from_db()
    assert filtre_pour(rai) is None


def test_valeurs_echappees() -> None:
    assert echapper_filtre('x" OR audience = "DG') == 'x\\" OR audience = \\"DG'
