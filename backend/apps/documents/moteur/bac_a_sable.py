"""Hardened Jinja environment and the actual rendering of a template.

This module is also the entry point of the rendering subprocess (`python -m
apps.documents.moteur.bac_a_sable`, see `rendu.py`): it must stay free of Django imports so that
the child starts fast and cannot reach application state.
"""

import base64
import io
import json
import re
import sys
from typing import Any, Final

from docxtpl import DocxTemplate, Listing
from jinja2 import StrictUndefined
from jinja2.exceptions import SecurityError, TemplateSyntaxError, UndefinedError
from jinja2.sandbox import ImmutableSandboxedEnvironment

from .contrats import Champ, TypeChamp, champ_depuis_dict

MAX_RESULTAT: Final = 1_000_000  # characters/items produced by one operator
MAX_DOCX_OCTETS: Final = 50 * 1024 * 1024
CODE_ERREUR: Final = 3

# Filters whose arguments can allocate huge strings (or leak internals); removed from the
# environment so the static analysis refuses them.
FILTRES_RETIRES: Final = (
    "center",
    "indent",
    "format",
    "wordwrap",
    "urlize",
    "xmlattr",
    "tojson",
    "pprint",
    "random",
    "filesizeformat",
)

# XML 1.0 forbids these characters; Word-pasted text can contain them.
_CARACTERES_INVALIDES: Final = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿\ud800-\udfff]")


class OperationRefusee(SecurityError):
    """An operator would build an oversized value."""


class ErreurRendu(Exception):
    """Rendering failed; `message` is French and displayable, `detail` is for the logs."""

    def __init__(self, message: str, detail: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class EnvironnementBorne(ImmutableSandboxedEnvironment):
    """Immutable sandbox that refuses operators able to allocate huge values."""

    intercepted_binops = frozenset({"*", "**", "+", "%"})

    def call_binop(self, context: Any, operator: str, left: Any, right: Any) -> Any:
        trop = OperationRefusee("Opération refusée : résultat trop volumineux.")
        sequences = (str, bytes, list, tuple)
        if operator == "*":
            for sequence, fois in ((left, right), (right, left)):
                if (
                    isinstance(sequence, sequences)
                    and isinstance(fois, int)
                    and len(sequence) * max(fois, 0) > MAX_RESULTAT
                ):
                    raise trop
            if isinstance(left, int) and isinstance(right, int):
                if left.bit_length() + right.bit_length() > 256:
                    raise trop
        elif operator == "**":
            if isinstance(left, int) and isinstance(right, int):
                if right > 64 or (abs(left) > 1 and right * abs(left).bit_length() > 256):
                    raise trop
        elif operator == "+":
            if (
                isinstance(left, sequences)
                and isinstance(right, sequences)
                and len(left) + len(right) > MAX_RESULTAT
            ):
                raise trop
        elif operator == "%" and isinstance(left, (str, bytes)):
            raise trop
        return super().call_binop(context, operator, left, right)


def environnement_jinja() -> EnvironnementBorne:
    """Jinja environment for untrusted templates: sandboxed, escaping, strict, no globals."""
    env = EnvironnementBorne(autoescape=True, undefined=StrictUndefined)
    env.globals.clear()  # no range/lipsum/cycler/joiner/namespace/dict
    for nom in FILTRES_RETIRES:
        env.filters.pop(nom, None)
    return env


def nettoyer(valeur: Any) -> Any:
    """Strip XML-invalid control characters from every string (same rule everywhere)."""
    if isinstance(valeur, str):
        return _CARACTERES_INVALIDES.sub("", valeur)
    if isinstance(valeur, list):
        return [nettoyer(v) for v in valeur]
    if isinstance(valeur, dict):
        return {k: nettoyer(v) for k, v in valeur.items()}
    return valeur


def _convertir(champ: Champ, valeur: Any) -> Any:
    """Turn `texte_long` values into Listing (line breaks kept); recurse into blocks/lists."""
    if champ.type is TypeChamp.TEXTE_LONG:
        return Listing(valeur)
    if champ.type is TypeChamp.BLOC:
        return _convertir_dict(champ.enfants, valeur)
    if champ.type is TypeChamp.LISTE and champ.enfants:
        return [_convertir_dict(champ.enfants, element) for element in valeur]
    return valeur


def _convertir_dict(champs: tuple[Champ, ...], valeurs: dict[str, Any]) -> dict[str, Any]:
    par_nom = {c.nom: c for c in champs}
    return {nom: _convertir(par_nom[nom], valeur) for nom, valeur in valeurs.items()}


def _message_francais(exc: Exception) -> str:
    if isinstance(exc, OperationRefusee):
        return f"Le rendu du document a échoué : {exc}"
    if isinstance(exc, UndefinedError):
        return "Le rendu du document a échoué : une balise du gabarit n'a pas de valeur."
    if isinstance(exc, SecurityError):
        return "Le rendu du document a échoué : le gabarit utilise une opération interdite."
    if isinstance(exc, TemplateSyntaxError):
        return "Le rendu du document a échoué : erreur de syntaxe dans les balises."
    if isinstance(exc, MemoryError):
        return "Le rendu du document a échoué : mémoire autorisée dépassée."
    return "Le rendu du document a échoué."


def rendre_local(gabarit: bytes, contexte: dict[str, Any], champs: tuple[Champ, ...]) -> bytes:
    """Render in this process (no time or memory limit: use `rendu.rendre_docx`)."""
    brut = nettoyer(contexte)
    donnees = _convertir_dict(champs, brut)
    env = environnement_jinja()
    try:
        modele = DocxTemplate(io.BytesIO(gabarit))
        rendre_proprietes = modele.render_properties

        def proprietes(_contexte: dict[str, Any], _env: Any = None) -> None:
            # Plain values, no autoescape: core properties are stored as text, not XML markup.
            rendre_proprietes(brut, env.overlay(autoescape=False))

        modele.render_properties = proprietes
        modele.render(donnees, jinja_env=env, autoescape=True)
        sortie = io.BytesIO()
        modele.save(sortie)
    except Exception as exc:
        raise ErreurRendu(_message_francais(exc), f"{type(exc).__name__}: {exc}") from exc
    resultat = sortie.getvalue()
    if len(resultat) > MAX_DOCX_OCTETS:
        raise ErreurRendu(
            "Le rendu du document a échoué : le document produit est trop volumineux."
        )
    return resultat


def main() -> int:
    """Subprocess protocol: JSON on stdin, .docx bytes on stdout, French message on stderr."""
    try:
        entree = json.loads(sys.stdin.buffer.read())
        champs = tuple(champ_depuis_dict(c) for c in entree["champs"])
        gabarit = base64.b64decode(entree["gabarit"])
        sys.stdout.buffer.write(rendre_local(gabarit, entree["contexte"], champs))
        sys.stdout.buffer.flush()
        return 0
    except ErreurRendu as exc:
        sys.stderr.write(f"{exc.message}\n{exc.detail}")
    except MemoryError:
        sys.stderr.write("Le rendu du document a échoué : mémoire autorisée dépassée.\n")
    except Exception as exc:
        sys.stderr.write(f"Le rendu du document a échoué.\n{type(exc).__name__}: {exc}")
    return CODE_ERREUR


if __name__ == "__main__":
    sys.exit(main())
