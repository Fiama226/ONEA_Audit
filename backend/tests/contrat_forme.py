"""Contrat JSON (lot 8) : forme (cles et types) des reponses, comparee a un fichier de reference.

Les valeurs varient d'une execution a l'autre ; seules les cles et les types sont figes.
Regeneration volontaire : `UPDATE_CONTRAT_LOT8=1 pytest <fichier de test>`.
"""

import json
import os
from pathlib import Path
from typing import Any


def forme(valeur: Any) -> Any:
    if isinstance(valeur, dict):
        return {k: forme(v) for k, v in sorted(valeur.items())}
    if isinstance(valeur, list):
        return [forme(valeur[0])] if valeur else []
    if valeur is None:
        return "null"
    return type(valeur).__name__


def comparer(fichier: Path, partie: str, corps: Any, *, brut: bool = False) -> None:
    contrat = corps if brut else forme(corps)
    complet: dict[str, Any] = json.loads(fichier.read_text("utf-8")) if fichier.exists() else {}
    if os.environ.get("UPDATE_CONTRAT_LOT8"):
        complet[partie] = contrat
        fichier.write_text(json.dumps(complet, indent=2, ensure_ascii=False) + "\n", "utf-8")
    assert contrat == complet[partie]
