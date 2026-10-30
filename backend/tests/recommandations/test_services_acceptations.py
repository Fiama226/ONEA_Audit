import pytest
from django.core.exceptions import PermissionDenied

from apps.constats.models import Recommandation
from apps.core.exceptions import RegleMetierError
from apps.missions.models import Mission, StatutEtape
from apps.recommandations.models import AcceptationRisque
from apps.recommandations.services.acceptations import (
    MSG_ACTIONS,
    accepter_risque,
    retirer_acceptation,
    texte_acceptation,
)
from apps.recommandations.services.actions import MSG_ACCEPTEE, creer_action
from apps.signatures.models import TypeDocumentSignable
from apps.signatures.services import verifier
from apps.users.models import User
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def test_acceptation_confirmee_et_verifiable(
    recommandations: list[Recommandation], audite_entite_a: User
) -> None:
    reco = recommandations[0]
    acceptation = accepter_risque(
        reco, justification=" Coût trop élevé ", by=audite_entite_a, adresse_ip="10.0.0.1"
    )
    assert acceptation.justification == "Coût trop élevé"
    confirmation = acceptation.confirmation
    assert confirmation.type_document == TypeDocumentSignable.ACCEPTATION_RISQUE
    assert confirmation.texte == texte_acceptation(reco, "Coût trop élevé", audite_entite_a)
    assert verifier(confirmation)


def test_acceptation_exclusive_des_actions(
    recommandations: list[Recommandation],
    audite_entite_a: User,
    audite_entite_b: User,
    chef: User,
) -> None:
    reco = recommandations[0]
    creer_action(reco, libelle="M", by=chef)
    with pytest.raises(RegleMetierError, match="supprimez-les"):
        accepter_risque(reco, justification="x", by=audite_entite_a)
    assert MSG_ACTIONS
    autre = recommandations[2]
    accepter_risque(autre, justification="x", by=audite_entite_b)
    with pytest.raises(RegleMetierError, match=MSG_ACCEPTEE):
        creer_action(autre, libelle="M", by=chef)
    with pytest.raises(RegleMetierError, match="déjà accepté"):
        accepter_risque(autre, justification="y", by=audite_entite_b)


def test_non_responsable_de_l_entite_refuse(
    recommandations: list[Recommandation], audite_entite_b: User, chef: User
) -> None:
    with pytest.raises(PermissionDenied):
        accepter_risque(recommandations[0], justification="x", by=audite_entite_b)
    with pytest.raises(PermissionDenied):
        accepter_risque(recommandations[0], justification="x", by=chef)


def test_justification_obligatoire(
    recommandations: list[Recommandation], audite_entite_a: User
) -> None:
    with pytest.raises(RegleMetierError) as exc:
        accepter_risque(recommandations[0], justification="  ", by=audite_entite_a)
    assert "justification" in exc.value.errors


def test_retrait_par_auteur_ou_rai_puis_nouvelle_acceptation(
    mission_en_communication: Mission,
    recommandations: list[Recommandation],
    audite_entite_a: User,
    audite_entite_b: User,
    chef: User,
) -> None:
    reco = recommandations[0]
    acceptation = accepter_risque(reco, justification="x", by=audite_entite_a)
    with pytest.raises(PermissionDenied):
        retirer_acceptation(acceptation, by=audite_entite_b)
    retirer_acceptation(acceptation, by=audite_entite_a)
    assert not AcceptationRisque.objects.filter(recommandation=reco).exists()
    assert AcceptationRisque.all_objects.filter(pk=acceptation.pk).exists()
    nouvelle = accepter_risque(reco, justification="y", by=audite_entite_a)
    forcer_etapes(mission_en_communication, {16: StatutEtape.TERMINEE})
    with pytest.raises(RegleMetierError):
        retirer_acceptation(nouvelle, by=audite_entite_a)
