from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.documents.management.commands.contrats_documents import Command
from apps.documents.moteur.documentation import documenter

from .fabrique import CONTRAT_TEST


def test_documenter_contient_tableau_et_exemples() -> None:
    md = documenter(CONTRAT_TEST)
    assert "| Balise | Type | Description |" in md
    assert "`mission.titre`" in md
    assert "{{ mission.reference }}" in md
    assert "{%tr for l in equipe %}" in md
    assert "`equipe[].nom`" in md


def test_documentation_contrats_a_jour() -> None:
    # Verifies the committed files under docs/documents/contrats/.
    call_command(Command(), "--verifier")


def test_ecrire_puis_verifier_et_detecter_ecart(tmp_path: Path) -> None:
    call_command(Command(), "--ecrire", dossier=str(tmp_path))
    call_command(Command(), "--verifier", dossier=str(tmp_path))
    (tmp_path / "COMMUN.md").write_text("modifié", encoding="utf-8")
    with pytest.raises(CommandError):
        call_command(Command(), "--verifier", dossier=str(tmp_path))
