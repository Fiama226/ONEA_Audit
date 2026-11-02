import importlib

import pytest

from apps.documents.models import FormatNumerotation
from apps.documents.numerotation import erreurs_modele

migration = importlib.import_module(
    "apps.documents.migrations.0002_normaliser_sequence_numerotation"
)


@pytest.mark.django_db
def test_migration_corrige_les_formats_avec_mise_en_forme() -> None:
    FormatNumerotation.objects.create(
        type_document="QA_ANCIEN",
        modele="{mission}/{code}-{sequence:02d}",
        portee="MISSION",
        abreviation="QA",
    )
    assert erreurs_modele("{mission}/{code}-{sequence:02d}", "MISSION")
    migration.normaliser(__import__("django.apps", fromlist=["apps"]).apps, None)
    fmt = FormatNumerotation.objects.get(type_document="QA_ANCIEN")
    assert fmt.modele == "{mission}/{code}-{sequence}"
    assert erreurs_modele(fmt.modele, fmt.portee) == []


def test_normaliser_modele_laisse_les_modeles_valides() -> None:
    assert (
        migration.normaliser_modele("{mission}/{code}-{sequence}") == "{mission}/{code}-{sequence}"
    )
    assert migration.normaliser_modele("{code}-{sequence!r}") == "{code}-{sequence}"
