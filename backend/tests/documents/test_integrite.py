import io
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.documents.models import DocumentVersion
from apps.documents.stockage import ecrire

from .conftest import chemin_fichier

pytestmark = pytest.mark.django_db


def test_verifier_documents_code_de_sortie(version_prete: DocumentVersion) -> None:
    sortie = io.StringIO()
    call_command("verifier_documents", stdout=sortie)
    assert "2 fichier(s) vérifié(s), 0 anomalie(s)" in sortie.getvalue()
    chemin_fichier(version_prete.fichier_docx.name).write_bytes(b"x")
    with pytest.raises(CommandError, match="1 anomalie"):
        call_command("verifier_documents", stdout=io.StringIO())


def test_fichier_manquant_est_une_anomalie(version_prete: DocumentVersion) -> None:
    chemin_fichier(version_prete.fichier_docx.name).unlink()
    with pytest.raises(CommandError):
        call_command("verifier_documents", stdout=io.StringIO())


def test_orphelins_et_manifeste(version_prete: DocumentVersion) -> None:
    ecrire("versions/orphelin/v001.docx", b"seul")
    sortie = io.StringIO()
    call_command("verifier_documents", "--orphelins", "--manifeste", stdout=sortie)
    texte: Any = sortie.getvalue()
    assert "versions/orphelin/v001.docx" in texte
    assert f"{version_prete.fichier_docx.name};{version_prete.empreinte_docx}" in texte
    assert f"{version_prete.fichier_docx.name}\n" not in texte.split("Orphelins")[1]
    assert "1 orphelin(s) : informatif" in texte
    assert chemin_fichier("versions/orphelin/v001.docx").exists()  # jamais supprimé


def test_gabarit_altere_ou_manquant_est_une_anomalie(version_prete: DocumentVersion) -> None:
    chemin = chemin_fichier(version_prete.gabarit.fichier.name)
    chemin.write_bytes(b"autre")
    with pytest.raises(CommandError, match="anomalie"):
        call_command("verifier_documents", stdout=io.StringIO(), stderr=io.StringIO())
    chemin.unlink()
    with pytest.raises(CommandError, match="anomalie"):
        call_command("verifier_documents", stdout=io.StringIO(), stderr=io.StringIO())
