"""Les modèles de numéro par défaut des types enregistrés doivent passer la validation."""

import importlib

import pytest

from apps.documents.moteur.registre import types_documents
from apps.documents.numerotation import erreurs_modele

pytestmark = pytest.mark.django_db


def test_modele_numero_par_defaut_valide_pour_chaque_type() -> None:
    importlib.import_module("apps.documents.generators")
    types = types_documents()
    assert types
    invalides = {
        t.code: erreurs_modele(t.modele_numero, t.portee_numero)
        for t in types
        if erreurs_modele(t.modele_numero, t.portee_numero)
    }
    assert invalides == {}
