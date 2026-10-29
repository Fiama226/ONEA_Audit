import pytest

from apps.documents.moteur.analyse import analyser_gabarit
from apps.documents.moteur.provisoires import construire_gabarit_provisoire
from apps.documents.moteur.registre import type_document


@pytest.mark.parametrize(
    ("code", "abreviation", "etape"), [("ORDRE_MISSION", "OM", 1), ("PV_OUVERTURE", "PVO", 2)]
)
def test_contrats_valides_par_gabarit_provisoire(code: str, abreviation: str, etape: int) -> None:
    t = type_document(code)
    assert (t.abreviation, t.etape) == (abreviation, etape)
    contenu = construire_gabarit_provisoire(t)
    analyser_gabarit(contenu, t.contrat, nom_fichier="p.docx", taille_max_mo=10)
