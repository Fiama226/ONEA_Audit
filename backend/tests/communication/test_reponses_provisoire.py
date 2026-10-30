# ruff: noqa: F811
from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied

from apps.communication.droits import constats_a_repondre
from apps.communication.models import RapportProvisoire, ReponseRapport
from apps.communication.services.provisoire import (
    etat_reponses,
    repondre_provisoire,
    reponses_visibles,
)
from apps.constats.models import Constat
from apps.core.exceptions import RegleMetierError
from apps.missions.models import StatutEtape
from apps.signatures.services import verifier
from apps.users.models import User
from tests.communication.support_provisoire import (  # noqa: F401
    affecter,
    audite_affecte,
    audite_entite_a,
    audite_entite_b,
    auditeur_mission,
    aujourd_hui_le,
    chef,
    constat_a,
    constat_b,
    constat_hors_provisoire,
    mission_en_xiv,
    mission_lancee,
    mission_xv,
    provisoire_transmis,
    rapport_xv,
)
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def test_reponse_responsable_entite_confirmee(
    provisoire_transmis: RapportProvisoire,
    constat_a: Constat,
    audite_entite_a: User,
    audite_entite_b: User,
) -> None:
    r = repondre_provisoire(
        provisoire_transmis,
        constat=constat_a,
        commentaire="Mesure déjà engagée par la DCL.",
        by=audite_entite_a,
    )
    assert verifier(r.confirmation) and not r.hors_delai
    assert "du rapport provisoire de la mission" in r.confirmation.texte
    with pytest.raises(PermissionDenied):
        repondre_provisoire(
            provisoire_transmis, constat=constat_a, commentaire="x", by=audite_entite_b
        )


def test_reponse_hors_delai_acceptee_et_marquee(
    provisoire_transmis: RapportProvisoire,
    constat_a: Constat,
    audite_entite_a: User,
    aujourd_hui_le,  # noqa: F811
) -> None:
    aujourd_hui_le(provisoire_transmis.date_limite_reponses + timedelta(days=1))
    assert repondre_provisoire(
        provisoire_transmis, constat=constat_a, commentaire="Retard", by=audite_entite_a
    ).hors_delai


def test_reponse_le_jour_limite_dans_les_delais(
    provisoire_transmis: RapportProvisoire,
    constat_a: Constat,
    audite_entite_a: User,
    aujourd_hui_le,  # noqa: F811
) -> None:
    aujourd_hui_le(provisoire_transmis.date_limite_reponses)
    assert not repondre_provisoire(
        provisoire_transmis, constat=constat_a, commentaire="Ok", by=audite_entite_a
    ).hors_delai


def test_reponse_apres_XVI_refusee(
    provisoire_transmis: RapportProvisoire, constat_a: Constat, audite_entite_a: User
) -> None:
    forcer_etapes(provisoire_transmis.mission, {16: StatutEtape.TERMINEE})
    with pytest.raises(RegleMetierError) as exc:
        repondre_provisoire(
            provisoire_transmis, constat=constat_a, commentaire="Tard", by=audite_entite_a
        )
    assert exc.value.message == "La période de réponse au rapport provisoire est close."


def test_reponse_constat_hors_provisoire(
    provisoire_transmis: RapportProvisoire, constat_hors_provisoire: Constat, audite_entite_a: User
) -> None:
    autre = constat_hors_provisoire
    with pytest.raises(RegleMetierError) as exc:
        repondre_provisoire(provisoire_transmis, constat=autre, commentaire="x", by=audite_entite_a)
    assert exc.value.message == "Ce constat ne figure pas dans le rapport provisoire."


def test_reponse_commentaire_obligatoire(
    provisoire_transmis: RapportProvisoire, constat_a: Constat, audite_entite_a: User
) -> None:
    with pytest.raises(RegleMetierError) as exc:
        repondre_provisoire(
            provisoire_transmis, constat=constat_a, commentaire="  ", by=audite_entite_a
        )
    assert exc.value.message == "Saisissez la réponse de votre direction."


def test_reponse_refusee_hors_audite(
    provisoire_transmis: RapportProvisoire, constat_a: Constat, chef: User, rai: User
) -> None:
    for user in (chef, rai):
        with pytest.raises(PermissionDenied):
            repondre_provisoire(provisoire_transmis, constat=constat_a, commentaire="x", by=user)


def test_reponses_en_ajout_seul_la_derniere_fait_foi(
    provisoire_transmis: RapportProvisoire, constat_a: Constat, audite_entite_a: User
) -> None:
    repondre_provisoire(provisoire_transmis, constat=constat_a, commentaire="1", by=audite_entite_a)
    repondre_provisoire(provisoire_transmis, constat=constat_a, commentaire="2", by=audite_entite_a)
    assert ReponseRapport.objects.filter(provisoire=provisoire_transmis).count() == 2
    etat = {e.reference: e for e in etat_reponses(provisoire_transmis)}[constat_a.reference]
    assert etat.recue_le is not None


def test_reponses_visibles_audite_les_siennes(
    provisoire_transmis: RapportProvisoire,
    constat_a: Constat,
    constat_b: Constat,
    audite_entite_a: User,
    audite_entite_b: User,
    chef: User,
    rai: User,
) -> None:
    ra = repondre_provisoire(
        provisoire_transmis, constat=constat_a, commentaire="A", by=audite_entite_a
    )
    rb = repondre_provisoire(
        provisoire_transmis, constat=constat_b, commentaire="B", by=audite_entite_b
    )
    assert list(reponses_visibles(audite_entite_a, provisoire_transmis)) == [ra]
    assert list(reponses_visibles(audite_entite_b, provisoire_transmis)) == [rb]
    for interne in (chef, rai):
        assert set(reponses_visibles(interne, provisoire_transmis)) == {ra, rb}


def test_reponses_visibles_dg_admin_aucune(provisoire_transmis: RapportProvisoire) -> None:
    from apps.users.models import Role
    from tests.factories import make_user

    for role in (Role.DG, Role.ADMIN):
        assert not reponses_visibles(make_user(role), provisoire_transmis).exists()


def test_etat_reponses_attendue_recue_hors_delai(
    provisoire_transmis: RapportProvisoire,
    constat_a: Constat,
    constat_b: Constat,
    audite_entite_a: User,
    aujourd_hui_le,  # noqa: F811
) -> None:
    aujourd_hui_le(provisoire_transmis.date_limite_reponses + timedelta(days=2))
    repondre_provisoire(provisoire_transmis, constat=constat_a, commentaire="A", by=audite_entite_a)
    etats = {e.reference: e for e in etat_reponses(provisoire_transmis)}
    assert set(etats) == {constat_a.reference, constat_b.reference}
    assert etats[constat_a.reference].recue_le is not None and etats[constat_a.reference].hors_delai
    assert etats[constat_b.reference].recue_le is None
    assert etats[constat_b.reference].attendue_de == constat_b.entite.libelle


def test_constats_a_repondre(
    provisoire_transmis: RapportProvisoire,
    constat_a: Constat,
    audite_entite_a: User,
    chef: User,
) -> None:
    assert constats_a_repondre(audite_entite_a, provisoire_transmis) == [constat_a.pk]
    assert constats_a_repondre(chef, provisoire_transmis) == []
