# ruff: noqa: F811
import pytest

from apps.communication.droits import (
    TRANSMETTRE,
    actions_provisoire,
    contexte_provisoire,
)
from apps.communication.models import Rapport
from apps.communication.services.provisoire import transmettre_provisoire
from apps.constats.models import Constat
from apps.core.exceptions import RegleMetierError
from apps.missions.models import EtapeMission, Reunion, StatutEtape
from apps.missions.services.etapes import terminer_etape
from apps.users.models import User
from tests.communication.support_provisoire import (  # noqa: F401
    affecter,
    audite_affecte,
    audite_entite_a,
    audite_entite_b,
    auditeur_mission,
    chef,
    constat_a,
    constat_b,
    mission_en_xiv,
    mission_lancee,
    mission_xv,
    mission_xv_vide,
    provisoire_transmis,
    rapport_xv,
)
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db

MSG_REUNION = "La réunion de clôture n'est pas marquée comme tenue."
MSG_TRANSMETTRE = "Transmettez le rapport provisoire aux audités."


def _xv(mission: object) -> EtapeMission:
    return EtapeMission.objects.get(mission=mission, numero=15)


def _manquants(mission: object, chef: User) -> list[str]:
    with pytest.raises(RegleMetierError) as exc:
        terminer_etape(_xv(mission), by=chef)
    return list(exc.value.errors["livrables"])


def test_terminer_XV_exige_reunion_et_transmission(mission_xv, chef: User) -> None:  # type: ignore[no-untyped-def]
    Reunion.objects.filter(mission=mission_xv).update(tenue_le=None)
    assert _manquants(mission_xv, chef) == [MSG_REUNION, MSG_TRANSMETTRE]


def test_terminer_XV_reunion_et_transmission(
    mission_xv,
    rapport_xv: Rapport,
    chef: User,  # type: ignore[no-untyped-def]
) -> None:
    assert _manquants(mission_xv, chef) == [MSG_TRANSMETTRE]
    transmettre_provisoire(rapport_xv, by=chef)
    etape = terminer_etape(_xv(mission_xv), by=chef)
    assert etape.statut == StatutEtape.TERMINEE


def test_sans_constat_valide_seule_la_reunion_est_exigee(mission_xv_vide, chef: User) -> None:  # type: ignore[no-untyped-def]
    assert terminer_etape(_xv(mission_xv_vide), by=chef).statut == StatutEtape.TERMINEE


def test_xv_close_ferme_aussi_les_reponses_aux_constats(
    provisoire_transmis,
    constat_a: Constat,
    audite_entite_a: User,
    chef: User,  # type: ignore[no-untyped-def]
) -> None:
    """Non-régression du lot 6 (D11) : la clôture de XV ferme la réponse au constat."""
    from apps.constats.services.reponses import repondre
    from apps.missions.exceptions import EtapeCloseError

    terminer_etape(_xv(provisoire_transmis.mission), by=chef)
    with pytest.raises(EtapeCloseError):
        repondre(
            constat_a,
            position="ACCORD",
            commentaire="",
            empreinte_soumise=constat_a.empreinte_soumise,
            by=audite_entite_a,
        )


def test_actions_provisoire(
    mission_xv,
    rapport_xv: Rapport,
    chef: User,
    rai: User,
    auditeur_mission: User,  # type: ignore[no-untyped-def]
    audite_entite_a: User,
) -> None:
    for user, attendu in (
        (chef, [TRANSMETTRE]),
        (rai, [TRANSMETTRE]),
        (auditeur_mission, []),
        (audite_entite_a, []),
    ):
        contexte = contexte_provisoire(mission_xv, user)
        assert actions_provisoire(rapport_xv, user, contexte=contexte) == attendu
    forcer_etapes(mission_xv, {15: StatutEtape.TERMINEE})
    contexte = contexte_provisoire(mission_xv, chef)
    assert actions_provisoire(rapport_xv, chef, contexte=contexte) == []
