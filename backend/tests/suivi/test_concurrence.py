import threading

import pytest
from django.db import connection, transaction

from apps.core.exceptions import RegleMetierError
from apps.suivi.models import StatutSuivi, SuiviAction
from apps.suivi.services import workflow
from apps.users.models import User
from tests.suivi.factories import PreuveFactory

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def mission_validee(request: pytest.FixtureRequest) -> object:
    # Numéros de constat réservés en transaction : le jeu d'essai en ouvre une.
    with transaction.atomic():
        return request.getfixturevalue("mission_en_suivi")


def test_transitions_concurrentes(
    mission_validee: object, responsable: User, auditeur_mission: User
) -> None:
    s = SuiviAction.objects.first()
    PreuveFactory(suivi=s)
    workflow.declarer_realisee(s, commentaire="Fait.", by=responsable)
    barriere = threading.Barrier(2)
    resultats: dict[str, object] = {}

    def lancer(nom: str, operation: object) -> None:
        try:
            barriere.wait(timeout=10)
            operation()  # type: ignore[operator]
            resultats[nom] = "ok"
        except Exception as e:  # noqa: BLE001
            resultats[nom] = e
        finally:
            connection.close()

    threads = [
        threading.Thread(
            target=lancer, args=("verifier", lambda: workflow.verifier(s, by=auditeur_mission))
        ),
        threading.Thread(
            target=lancer,
            args=("rejeter", lambda: workflow.rejeter(s, motif="Non.", by=auditeur_mission)),
        ),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    reussies = [n for n, r in resultats.items() if r == "ok"]
    assert len(resultats) == 2
    assert len(reussies) == 1, resultats
    perdante = next(r for n, r in resultats.items() if n not in reussies)
    assert isinstance(perdante, RegleMetierError)
    s.refresh_from_db()
    assert s.statut in (StatutSuivi.VERIFIEE, StatutSuivi.EN_COURS)
    assert s.evenements.count() == 2  # déclaration + une seule décision
