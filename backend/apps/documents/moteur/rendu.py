"""Sandboxed rendering of Word templates with docxtpl."""

import io
from typing import Any

from docxtpl import DocxTemplate, Listing
from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from .contrats import CHAMPS_COMMUNS, Champ, Contrat, TypeChamp, ecarts_contexte
from .exceptions import RenduError


def environnement_jinja() -> SandboxedEnvironment:
    """Jinja environment for untrusted templates: sandboxed, escaping, strict on typos."""
    return SandboxedEnvironment(autoescape=True, undefined=StrictUndefined)


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


def rendre_docx(gabarit: bytes, contexte: dict[str, Any], contrat: Contrat) -> bytes:
    """Render `gabarit` with `contexte`, which must conform to `contrat`."""
    ecarts = ecarts_contexte(contrat, contexte)
    if ecarts:
        raise RenduError(
            "Les données du document ne respectent pas le contrat : " + " ".join(ecarts)
        )
    donnees = _convertir_dict(CHAMPS_COMMUNS + contrat.champs, contexte)
    try:
        modele = DocxTemplate(io.BytesIO(gabarit))
        modele.render(donnees, jinja_env=environnement_jinja(), autoescape=True)
        sortie = io.BytesIO()
        modele.save(sortie)
    except Exception as exc:
        raise RenduError(f"Le rendu du document a échoué : {exc}") from exc
    return sortie.getvalue()
