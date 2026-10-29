from typing import Any

import pytest
from django.http import Http404
from django.utils import timezone

from apps.documents.generators.missions import FournisseurPvOuverture
from apps.documents.moteur.contrats import ecarts_contexte
from apps.documents.moteur.registre import type_document
from apps.documents.services.generation import demander_generation
from apps.missions.models import Mission, Reunion, RoleMission, TypeReunion
from apps.users.models import Role, User
from tests.factories import ReunionFactory, make_user
from tests.missions.conftest import affecter

from .missions_support import COMMUN_X, gabarits_provisoires  # noqa: F401

pytestmark = pytest.mark.django_db


def reunion_de(**kwargs: Any) -> Reunion:
    fabrique: Any = ReunionFactory
    reunion: Reunion = fabrique(**kwargs)
    return reunion


def test_pv_raison_si_reunion_non_tenue(mission_lancee: Mission) -> None:
    reunion = reunion_de(mission=mission_lancee)
    assert FournisseurPvOuverture().raison_non_generable(reunion) == (
        "Marquez la réunion d'ouverture comme tenue avant de générer le PV."
    )
    reunion.tenue_le = timezone.now()
    assert FournisseurPvOuverture().raison_non_generable(reunion) is None


def test_pv_participants_et_externes(
    mission_lancee: Mission,
    rai: User,
    gabarits_provisoires: None,  # noqa: F811
    django_capture_on_commit_callbacks: Any,
) -> None:
    kabore = make_user(
        Role.AUDITE,
        last_name="Kaboré",
        first_name="Mme",
        fonction="Directrice",
        direction_code="DCL",
    )
    reunion = reunion_de(
        mission=mission_lancee,
        tenue_le=timezone.now(),
        participants_externes="M. Traoré\n\n  Cabinet X  ",
        compte_rendu="Réunion tenue.",
    )
    reunion.participants.add(kabore)
    f = FournisseurPvOuverture()
    ctx = f.contexte(reunion)
    assert ctx["reunion"]["participants"] == [
        {"nom": "Mme Kaboré", "fonction": "Directrice", "direction": "DCL"}
    ]
    assert ctx["reunion"]["participants_externes"] == ["M. Traoré", "Cabinet X"]
    t = type_document("PV_OUVERTURE")
    assert ecarts_contexte(t.contrat, {**COMMUN_X, **ctx}) == []
    with django_capture_on_commit_callbacks(execute=True):
        v = demander_generation(type_document="PV_OUVERTURE", objet_id=reunion.pk, by=rai)
    v.refresh_from_db()
    assert v.statut == "PRETE" and v.document.numero == f"{mission_lancee.reference}/PVO-01"
    assert f.objets_de_mission(mission_lancee) == [reunion]


def test_droits_fournisseur_pv(mission_lancee: Mission, rai: User) -> None:
    f = FournisseurPvOuverture()
    reunion = reunion_de(mission=mission_lancee)
    chef = make_user(Role.AUDITEUR)
    affecter(mission_lancee, chef, RoleMission.CHEF_MISSION)
    audite = make_user(Role.AUDITE)
    affecter(mission_lancee, audite, RoleMission.AUDITE)
    assert f.peut_generer(chef, reunion) and f.peut_generer(rai, reunion)
    assert not f.peut_generer(audite, reunion)
    assert f.peut_consulter(chef, reunion)
    assert not f.peut_consulter(make_user(Role.AUDITEUR), reunion)


def test_pv_objet_d_un_autre_type(mission_lancee: Mission) -> None:
    lancement = reunion_de(mission=mission_lancee, type=TypeReunion.LANCEMENT)
    with pytest.raises(Http404):
        FournisseurPvOuverture().objet(lancement.pk)
