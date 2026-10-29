from dataclasses import replace

import pytest

from apps.core.exceptions import RegleMetierError
from apps.documents.moteur import registre
from apps.documents.moteur.analyse import analyser_gabarit
from apps.documents.moteur.provisoires import construire_gabarit_provisoire
from apps.documents.moteur.registre import TypeDocument

from .fabrique import CONTRAT_TEST, texte_docx


def _type() -> TypeDocument:
    return TypeDocument(
        code="TEST",
        libelle="Document de test",
        etape=None,
        contrat=CONTRAT_TEST,
        abreviation="TST",
        modele_numero="{mission}/{code}-{sequence:02d}",
        portee_numero="MISSION",
        fournisseur=None,  # type: ignore[arg-type]
    )


def test_gabarit_provisoire_valide_pour_contrat_test() -> None:
    contenu = construire_gabarit_provisoire(_type())
    balises = analyser_gabarit(contenu, CONTRAT_TEST, nom_fichier="p.docx", taille_max_mo=10)
    assert {"mission", "equipe", "notes"} <= balises
    brut = texte_docx(contenu)
    assert "GABARIT PROVISOIRE" in brut
    assert "ONEA — Département Audit Interne" in brut


def test_registre_type_inconnu_422() -> None:
    with pytest.raises(RegleMetierError, match="Type de document inconnu : NOPE."):
        registre.type_document("NOPE")


def test_registre_enregistrement_doublon_et_ordre(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registre, "_TYPES", {})
    b = replace(_type(), code="B", libelle="Zeta", etape=2)
    a = replace(_type(), code="A", libelle="Alpha", etape=2)
    c = replace(_type(), code="C", libelle="Premier", etape=1)
    for t in (b, a, c):
        registre.enregistrer_type(t)
    assert [t.code for t in registre.types_documents()] == ["C", "A", "B"]
    assert registre.type_document("A") is a
    with pytest.raises(ValueError):
        registre.enregistrer_type(a)
