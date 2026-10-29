"""Hardened Jinja environment and the actual rendering of a template.

This module is also the entry point of the rendering subprocess (`python -W ignore -m
apps.documents.moteur.bac_a_sable --memoire-mo N --cpu-s N`, see `rendu.py`): it must stay free
of Django imports so that the child starts fast and cannot reach application state. The child
applies its own resource limits at start (no `preexec_fn` in the possibly threaded parent).
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
from .controle_ooxml import nettoyer_gabarit, verifier_sortie

MAX_RESULTAT: Final = 1_000_000  # characters/items produced by one operator
MAX_DOCX_OCTETS: Final = 50 * 1024 * 1024
MARQUEUR_ERREUR: Final = "ONEA-ERREUR:"
DETAIL_MAX: Final = 2048
_FOOTNOTES: Final = "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"

# Filters removed from the environment (the static analysis then refuses them): arguments able
# to allocate huge strings, markup-trust (`safe`), or attribute access the analysis cannot see.
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
    "safe",
    "forceescape",
    "attr",
)

# Fixed French messages, one per error code (the child only ever sends a code).
MESSAGES: Final = {
    "trop_volumineux": "Le rendu du document a échoué : opération refusée, résultat trop volumineux.",  # noqa: E501
    "sans_valeur": "Le rendu du document a échoué : une balise du gabarit n'a pas de valeur.",
    "interdit": "Le rendu du document a échoué : le gabarit utilise une opération interdite.",
    "syntaxe": "Le rendu du document a échoué : erreur de syntaxe dans les balises.",
    "memoire": "Le rendu du document a échoué : mémoire autorisée dépassée.",
    "sortie_volumineuse": "Le rendu du document a échoué : le document produit est trop volumineux.",  # noqa: E501
    "sortie_interdite": (
        "Le rendu du document a été refusé : le résultat contient un champ ou un lien externe "
        "interdit."
    ),
    "generique": "Le rendu du document a échoué.",
}

# XML 1.0 forbids these characters; Word-pasted text can contain them.
_CARACTERES_INVALIDES: Final = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿\ud800-\udfff]")


class OperationRefusee(SecurityError):
    """An operator would build an oversized value."""


class ErreurRendu(Exception):
    """Rendering failed; `code` selects the French message, `detail` is for the logs only."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail

    @property
    def message(self) -> str:
        return MESSAGES.get(self.code, MESSAGES["generique"])


class EnvironnementBorne(ImmutableSandboxedEnvironment):
    """Immutable sandbox that refuses operators able to allocate huge values."""

    intercepted_binops = frozenset({"*", "**", "+", "%"})

    def call_binop(self, context: Any, operator: str, left: Any, right: Any) -> Any:
        trop = OperationRefusee("trop_volumineux")
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


def _code_erreur(exc: BaseException) -> str:
    if isinstance(exc, OperationRefusee):
        return "trop_volumineux"
    if isinstance(exc, UndefinedError):
        return "sans_valeur"
    if isinstance(exc, SecurityError):
        return "interdit"
    if isinstance(exc, TemplateSyntaxError):
        return "syntaxe"
    if isinstance(exc, MemoryError):
        return "memoire"
    return "generique"


def _footnotes_une_fois(modele: DocxTemplate) -> Any:
    """Replacement for docxtpl `render_footnotes`, which re-renders (and so re-evaluates the
    user data already written) once per section: render every footnotes part exactly once."""

    def rendre(contexte: dict[str, Any], jinja_env: Any = None) -> None:
        for partie in modele.docx.part.package.iter_parts():
            if partie.content_type == _FOOTNOTES:
                blob: Any = partie.blob
                xml = modele.patch_xml(blob.decode("utf-8") if isinstance(blob, bytes) else blob)
                partie._blob = modele.render_xml_part(xml, partie, contexte, jinja_env).encode(
                    "utf-8"
                )

    return rendre


def rendre_local(gabarit: bytes, contexte: dict[str, Any], champs: tuple[Champ, ...]) -> bytes:
    """Render in this process (no time or memory limit: use `rendu.rendre_docx`)."""
    brut = nettoyer(contexte)
    donnees = _convertir_dict(champs, brut)
    env = environnement_jinja()
    try:
        modele = DocxTemplate(io.BytesIO(nettoyer_gabarit(gabarit)))
        rendre_proprietes = modele.render_properties

        def proprietes(_contexte: dict[str, Any], _env: Any = None) -> None:
            # Plain values, no autoescape: core properties are stored as text, not XML markup.
            rendre_proprietes(brut, env.overlay(autoescape=False))

        modele.render_properties = proprietes
        modele.render_footnotes = _footnotes_une_fois(modele)
        modele.render(donnees, jinja_env=env, autoescape=True)
        sortie = io.BytesIO()
        modele.save(sortie)
    except Exception as exc:
        raise ErreurRendu(_code_erreur(exc), f"{type(exc).__name__}: {exc}") from exc
    resultat = sortie.getvalue()
    if len(resultat) > MAX_DOCX_OCTETS:
        raise ErreurRendu("sortie_volumineuse")
    if verifier_sortie(resultat) is not None:
        raise ErreurRendu("sortie_interdite")
    return resultat


def _limiter_ressources(memoire_mo: int, cpu_s: int) -> None:
    if sys.platform == "win32":
        return
    import resource

    octets = memoire_mo * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (octets, octets))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))


def _argument(nom: str, defaut: int) -> int:
    if nom in sys.argv:
        return int(sys.argv[sys.argv.index(nom) + 1])
    return defaut


def _signaler(code: str, detail: str = "") -> None:
    ligne = detail.replace("\n", " ")[:DETAIL_MAX]
    sys.stderr.write(f"\n{MARQUEUR_ERREUR}{code}:{ligne}\n")


def main() -> int:
    """Subprocess protocol: JSON on stdin, .docx bytes on stdout, error code on stderr."""
    try:
        _limiter_ressources(_argument("--memoire-mo", 1024), _argument("--cpu-s", 65))
        entree = json.loads(sys.stdin.buffer.read())
        champs = tuple(champ_depuis_dict(c) for c in entree["champs"])
        gabarit = base64.b64decode(entree["gabarit"])
        sys.stdout.buffer.write(rendre_local(gabarit, entree["contexte"], champs))
        sys.stdout.buffer.flush()
        return 0
    except ErreurRendu as exc:
        _signaler(exc.code, exc.detail)
    except MemoryError:
        _signaler("memoire")
    except Exception as exc:
        _signaler("generique", f"{type(exc).__name__}: {exc}")
    return 3


if __name__ == "__main__":
    sys.exit(main())
