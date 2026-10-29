from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.documents.models import GabaritDocument, StatutGabarit
from apps.documents.moteur.registre import TypeDocument
from apps.users.models import User

pytestmark = pytest.mark.django_db


def test_commande_liste_sans_installer(type_test: TypeDocument) -> None:
    out = StringIO()
    call_command("gabarits_provisoires", stdout=out)
    assert "TEST_DOC" in out.getvalue()
    assert GabaritDocument.objects.count() == 0


def test_commande_provisoires_idempotente(type_test: TypeDocument, rai: User) -> None:
    for _ in range(2):
        call_command(
            "gabarits_provisoires", "--installer", "--user", rai.username, stdout=StringIO()
        )
    actifs = GabaritDocument.objects.filter(type_document="TEST_DOC", statut=StatutGabarit.ACTIF)
    assert actifs.count() == 1
    assert actifs.get().provisoire is True
    assert GabaritDocument.objects.count() == 1


def test_commande_utilisateur_requis(type_test: TypeDocument) -> None:
    with pytest.raises(CommandError):
        call_command("gabarits_provisoires", "--installer", stdout=StringIO())
