"""Document numbering: configurable format, gap-free sequence per scope under an advisory lock."""

import re
from string import Formatter
from typing import TYPE_CHECKING, Any

from django.db import connection
from django.db.models import Max
from django.utils import timezone

from apps.core.exceptions import RegleMetierError
from apps.core.services import enregistrer

from .models import Document, FormatNumerotation, PorteeNumerotation
from .moteur.registre import type_document as type_enregistre

if TYPE_CHECKING:
    from apps.missions.models import Mission
    from apps.users.models import User

LOCK_NUMERO_DOCUMENT = 0x444F4353  # « DOCS »
CHAMPS_NUMERO = ("mission", "annee", "code", "sequence")
LONGUEUR_MAX = 40
_ABREVIATION_RE = re.compile(r"^[A-Za-z0-9-]{1,8}$")
_MISSION_EXEMPLE = "DAI/2026/M07"
_ANNEE_EXEMPLE = 2026


def _champs(modele: str) -> list[str] | None:
    """Names used by the model; None when the braces are malformed or carry a spec."""
    try:
        morceaux = list(Formatter().parse(modele))
    except ValueError:
        return None
    noms: list[str] = []
    for _texte, nom, spec, conversion in morceaux:
        if nom is None:
            continue
        if spec or conversion:
            noms.append(f"{nom}:{spec}" if spec else f"{nom}!{conversion}")
        else:
            noms.append(nom)
    return noms


def _rendre(modele: str, *, mission: str, annee: int, code: str, sequence: int) -> str:
    return modele.format(mission=mission, annee=annee, code=code, sequence=f"{sequence:02d}")


def erreurs_modele(modele: str, portee: str) -> list[str]:
    """Problems of a numbering model, in French (empty list when valid)."""
    permis = ", ".join(f"{{{c}}}" for c in CHAMPS_NUMERO)
    noms = _champs(modele)
    if noms is None:
        return ["Le modèle est mal formé : accolades non appariées."]
    erreurs = [
        f"Champ inconnu : {nom}. Champs permis : {permis}."
        for nom in dict.fromkeys(noms)
        if nom not in CHAMPS_NUMERO
    ]
    if "sequence" not in noms:
        erreurs.append("Le modèle doit contenir {sequence}.")
    if portee == PorteeNumerotation.MISSION and "mission" not in noms:
        erreurs.append("La portée « Par mission » exige {mission}.")
    if portee == PorteeNumerotation.ANNEE and "annee" not in noms:
        erreurs.append("La portée « Par année » exige {annee}.")
    if not erreurs:
        pire = _rendre(modele, mission=_MISSION_EXEMPLE, annee=9999, code="X" * 8, sequence=9999)
        if len(pire) > LONGUEUR_MAX:
            erreurs.append(f"Le numéro dépasse {LONGUEUR_MAX} caractères.")
    return erreurs


def apercu_numero(modele: str, portee: str, abreviation: str) -> str:
    """Example number: mission DAI/2026/M07, year 2026, sequence 1."""
    return _rendre(
        modele, mission=_MISSION_EXEMPLE, annee=_ANNEE_EXEMPLE, code=abreviation, sequence=1
    )


def format_de(type_document: str) -> FormatNumerotation:
    """Format of a type; created from the registry default on first use."""
    t = type_enregistre(type_document)
    fmt, _ = FormatNumerotation.objects.get_or_create(
        type_document=type_document,
        defaults={
            "modele": t.modele_numero,
            "portee": t.portee_numero,
            "abreviation": t.abreviation,
        },
    )
    return fmt


def modifier_format(type_document: str, *, by: "User", **changes: Any) -> FormatNumerotation:
    """Change the format; it applies to the following numbers only."""
    inconnus = set(changes) - {"modele", "portee", "abreviation"}
    if inconnus:
        raise RegleMetierError(
            "Données invalides.", {c: ["Champ non modifiable."] for c in inconnus}
        )
    fmt = format_de(type_document)
    for champ, valeur in changes.items():
        setattr(fmt, champ, valeur)
    erreurs: dict[str, list[str]] = {}
    if fmt.portee not in PorteeNumerotation.values:
        erreurs["portee"] = ["Portée inconnue."]
    if not _ABREVIATION_RE.match(fmt.abreviation):
        erreurs["abreviation"] = ["L'abréviation compte 1 à 8 lettres, chiffres ou tirets."]
    if "portee" not in erreurs and (problemes := erreurs_modele(fmt.modele, fmt.portee)):
        erreurs["modele"] = problemes
    if erreurs:
        raise RegleMetierError("Données invalides.", erreurs)
    enregistrer(fmt, by=by)
    return fmt


def attribuer_numero(type_document: str, *, mission: "Mission") -> tuple[str, int, int]:
    """Next free number as (numero, annee, sequence). Call inside a transaction (D9).

    The advisory lock serialises concurrent callers until the surrounding transaction ends.
    Deleted documents keep their number; a number already taken (after a format change) is
    skipped by moving on to the next sequence.
    """
    fmt = format_de(type_document)
    with connection.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(%s)", [LOCK_NUMERO_DOCUMENT])
    annee = mission.annee or timezone.localdate().year
    portee = Document.all_objects.filter(type_document=type_document)
    if fmt.portee == PorteeNumerotation.MISSION:
        portee = portee.filter(mission=mission)
    else:
        portee = portee.filter(annee=annee)
    sequence = (portee.aggregate(m=Max("sequence"))["m"] or 0) + 1
    while True:
        numero = _rendre(
            fmt.modele,
            mission=mission.reference,
            annee=annee,
            code=fmt.abreviation,
            sequence=sequence,
        )
        if not Document.all_objects.filter(numero=numero).exists():
            return numero, annee, sequence
        sequence += 1
