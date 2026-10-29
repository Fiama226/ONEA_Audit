"""Versioned tag contracts: the typed tree of variables a Word template may use."""

import copy
import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TypeChamp(StrEnum):
    TEXTE = "texte"
    TEXTE_LONG = "texte_long"
    LISTE = "liste"
    BLOC = "bloc"


@dataclass(frozen=True)
class Champ:
    nom: str
    type: TypeChamp
    description: str
    enfants: tuple["Champ", ...] = ()


@dataclass(frozen=True)
class Contrat:
    """`exemple` is a complete sample context, common blocks (`onea`, `document`) included.

    It is deep-copied and validated at construction; it is excluded from equality and hashing
    so that contracts (and the document types holding them) stay hashable.
    """

    code: str
    libelle: str
    version: int
    champs: tuple[Champ, ...]
    exemple: dict[str, Any] = field(compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "exemple", copy.deepcopy(self.exemple))
        ecarts = ecarts_contexte(self, self.exemple)
        if ecarts:
            raise ValueError(f"Exemple non conforme au contrat {self.code} : " + " ".join(ecarts))


CHAMPS_COMMUNS: tuple[Champ, ...] = (
    Champ(
        "onea",
        TypeChamp.BLOC,
        "Organisme émetteur",
        (
            Champ("nom", TypeChamp.TEXTE, "Nom complet de l'ONEA"),
            Champ("sigle", TypeChamp.TEXTE, "Sigle de l'ONEA"),
            Champ("departement", TypeChamp.TEXTE, "Département émetteur"),
        ),
    ),
    Champ(
        "document",
        TypeChamp.BLOC,
        "Informations du document généré",
        (
            Champ("numero", TypeChamp.TEXTE, "Numéro définitif du document"),
            Champ("version", TypeChamp.TEXTE, "Numéro de version du document"),
            Champ("type", TypeChamp.TEXTE, "Libellé du type de document"),
            Champ("genere_le", TypeChamp.TEXTE, "Date de génération (JJ/MM/AAAA)"),
            Champ("genere_par", TypeChamp.TEXTE, "Nom de la personne qui a généré le document"),
        ),
    ),
)

EXEMPLE_COMMUN: dict[str, Any] = {
    "onea": {
        "nom": "Office National de l'Eau et de l'Assainissement",
        "sigle": "ONEA",
        "departement": "Département Audit Interne",
    },
    "document": {
        "numero": "DAI/2026/M01/XX-01",
        "version": "1",
        "type": "Document d'exemple",
        "genere_le": "28/10/2026",
        "genere_par": "Prénom Nom",
    },
}

BLOC_MISSION = Champ(
    "mission",
    TypeChamp.BLOC,
    "Mission d'audit",
    (
        Champ("reference", TypeChamp.TEXTE, "Référence de la mission"),
        Champ("titre", TypeChamp.TEXTE, "Titre de la mission"),
        Champ("type", TypeChamp.TEXTE, "Type de mission"),
        Champ(
            "processus",
            TypeChamp.LISTE,
            "Processus audités",
            (
                Champ("code", TypeChamp.TEXTE, "Code du processus"),
                Champ("libelle", TypeChamp.TEXTE, "Libellé du processus"),
            ),
        ),
        Champ("processus_texte", TypeChamp.TEXTE, "Processus audités, séparés par des virgules"),
        Champ(
            "entites",
            TypeChamp.LISTE,
            "Entités auditées",
            (
                Champ("code", TypeChamp.TEXTE, "Code de l'entité"),
                Champ("libelle", TypeChamp.TEXTE, "Libellé de l'entité"),
            ),
        ),
        Champ("entites_texte", TypeChamp.TEXTE, "Entités auditées, séparées par des virgules"),
        Champ("periode", TypeChamp.TEXTE, "Période auditée"),
        Champ("date_debut_prevue", TypeChamp.TEXTE, "Date de début prévue (JJ/MM/AAAA)"),
        Champ("date_fin_prevue", TypeChamp.TEXTE, "Date de fin prévue (JJ/MM/AAAA)"),
        Champ("chef_mission", TypeChamp.TEXTE, "Chef de mission"),
    ),
)


def champ_vers_dict(champ: Champ) -> dict[str, Any]:
    """JSON-serialisable form of a field tree (sent to the rendering subprocess)."""
    return {
        "nom": champ.nom,
        "type": champ.type.value,
        "description": champ.description,
        "enfants": [champ_vers_dict(e) for e in champ.enfants],
    }


def champ_depuis_dict(donnees: dict[str, Any]) -> Champ:
    return Champ(
        donnees["nom"],
        TypeChamp(donnees["type"]),
        donnees["description"],
        tuple(champ_depuis_dict(e) for e in donnees["enfants"]),
    )


def _tous_les_champs(c: Contrat) -> tuple[Champ, ...]:
    return CHAMPS_COMMUNS + c.champs


def balises_racines(c: Contrat) -> frozenset[str]:
    """Names usable at the top level of a template (common blocks included)."""
    return frozenset(champ.nom for champ in _tous_les_champs(c))


def _ecarts_valeur(champ: Champ, valeur: Any, chemin: str, ecarts: list[str]) -> None:
    if valeur is None:
        ecarts.append(f"Valeur nulle pour « {chemin} » : utilisez une chaîne vide.")
    elif champ.type in (TypeChamp.TEXTE, TypeChamp.TEXTE_LONG):
        if not isinstance(valeur, str):
            ecarts.append(f"Type incorrect pour « {chemin} » : texte attendu.")
    elif champ.type is TypeChamp.BLOC:
        if not isinstance(valeur, dict):
            ecarts.append(f"Type incorrect pour « {chemin} » : bloc attendu.")
        else:
            _ecarts_dict(champ.enfants, valeur, chemin, ecarts)
    elif not isinstance(valeur, list):
        ecarts.append(f"Type incorrect pour « {chemin} » : liste attendue.")
    else:
        for i, element in enumerate(valeur):
            sous = f"{chemin}[{i}]"
            if champ.enfants:
                if isinstance(element, dict):
                    _ecarts_dict(champ.enfants, element, sous, ecarts)
                else:
                    ecarts.append(f"Type incorrect pour « {sous} » : bloc attendu.")
            elif not isinstance(element, str):
                ecarts.append(f"Type incorrect pour « {sous} » : texte attendu.")


def _ecarts_dict(
    champs: tuple[Champ, ...], valeurs: dict[str, Any], prefixe: str, ecarts: list[str]
) -> None:
    attendus = {c.nom: c for c in champs}
    for nom, champ in attendus.items():
        chemin = f"{prefixe}.{nom}" if prefixe else nom
        if nom not in valeurs:
            ecarts.append(f"Champ manquant : « {chemin} ».")
        else:
            _ecarts_valeur(champ, valeurs[nom], chemin, ecarts)
    for nom in valeurs:
        if nom not in attendus:
            chemin = f"{prefixe}.{nom}" if prefixe else nom
            ecarts.append(f"Champ inattendu : « {chemin} ».")


def ecarts_contexte(c: Contrat, contexte: dict[str, Any]) -> list[str]:
    """List the differences between a context and the contract (empty when it conforms)."""
    ecarts: list[str] = []
    _ecarts_dict(_tous_les_champs(c), contexte, "", ecarts)
    return ecarts


def empreinte_json(donnees: dict[str, Any]) -> str:
    """SHA-256 of the canonical JSON form (sorted keys, compact, non-ASCII kept)."""
    canonique = json.dumps(donnees, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonique.encode("utf-8")).hexdigest()
