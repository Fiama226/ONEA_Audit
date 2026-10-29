"""Markdown documentation of tag contracts, published under docs/documents/contrats/."""

from pathlib import Path

from .contrats import CHAMPS_COMMUNS, Champ, Contrat, TypeChamp

_LIBELLES_TYPE = {
    TypeChamp.TEXTE: "texte",
    TypeChamp.TEXTE_LONG: "texte long",
    TypeChamp.LISTE: "liste",
    TypeChamp.BLOC: "bloc",
}

ENTETE_TABLEAU = "| Balise | Type | Description |\n|---|---|---|"


def dossier_par_defaut() -> Path:
    """`docs/documents/contrats/` at the repository root."""
    return Path(__file__).resolve().parents[4] / "docs" / "documents" / "contrats"


def _lignes(champs: tuple[Champ, ...], prefixe: str = "") -> list[tuple[str, Champ]]:
    sortie: list[tuple[str, Champ]] = []
    for champ in champs:
        chemin = f"{prefixe}{champ.nom}"
        sortie.append((chemin, champ))
        suffixe = "[]." if champ.type is TypeChamp.LISTE else "."
        sortie.extend(_lignes(champ.enfants, f"{chemin}{suffixe}"))
    return sortie


def _tableau(champs: tuple[Champ, ...]) -> str:
    lignes = [ENTETE_TABLEAU]
    for chemin, champ in _lignes(champs):
        type_ = _LIBELLES_TYPE[champ.type]
        lignes.append(f"| `{chemin}` | {type_} | {champ.description} |")
    return "\n".join(lignes)


def _premier_scalaire(champs: tuple[Champ, ...], prefixe: str = "") -> str | None:
    for champ in champs:
        if champ.type in (TypeChamp.TEXTE, TypeChamp.TEXTE_LONG):
            return f"{prefixe}{champ.nom}"
        if champ.type is TypeChamp.BLOC:
            trouve = _premier_scalaire(champ.enfants, f"{prefixe}{champ.nom}.")
            if trouve:
                return trouve
    return None


def _premiere_liste(champs: tuple[Champ, ...]) -> Champ | None:
    return next((c for c in champs if c.type is TypeChamp.LISTE), None)


def documenter(c: Contrat) -> str:
    """Markdown page of a contract: tag table and usage examples."""
    scalaire = _premier_scalaire(c.champs) or "document.numero"
    parties = [
        f"# {c.libelle}",
        f"Code du type : `{c.code}` — version du contrat : {c.version}",
        "Les blocs `onea` et `document` sont communs à tous les documents : voir "
        "[COMMUN.md](COMMUN.md). Toutes les valeurs sont des textes déjà formatés "
        "(dates `JJ/MM/AAAA`) ; une valeur absente est une chaîne vide.",
        "## Balises",
        _tableau(c.champs),
        "## Utilisation dans le gabarit Word",
        f"- Valeur simple : `{{{{ {scalaire} }}}}`",
    ]
    liste = _premiere_liste(c.champs)
    if liste is not None:
        colonne = next((e.nom for e in liste.enfants), None)
        cellule = f"l.{colonne}" if colonne else "l"
        parties.append(
            "- Tableau répété : trois lignes de tableau contenant "
            f"`{{%tr for l in {liste.nom} %}}`, `{{{{ {cellule} }}}}` puis `{{%tr endfor %}}`."
        )
    parties.append(
        "- Les balises inconnues, les fautes de frappe et la syntaxe invalide "
        "sont refusées au dépôt du gabarit."
    )
    return "\n\n".join(parties) + "\n"


def documenter_communs() -> str:
    return (
        "\n\n".join(
            [
                "# Balises communes",
                "Ces blocs sont disponibles dans le gabarit de chaque type de document.",
                _tableau(CHAMPS_COMMUNS),
            ]
        )
        + "\n"
    )


def contenus_attendus(contrats: list[Contrat]) -> dict[str, str]:
    """File name -> expected Markdown content for the contracts directory."""
    fichiers = {"COMMUN.md": documenter_communs()}
    for c in contrats:
        fichiers[f"{c.code}.md"] = documenter(c)
    index = ["# Contrats de balises des documents", ""]
    index.append("Fichiers générés par `python manage.py contrats_documents --ecrire`.")
    index.append("")
    index.append("- [Balises communes](COMMUN.md)")
    for c in sorted(contrats, key=lambda x: x.code):
        index.append(f"- [{c.libelle}]({c.code}.md)")
    fichiers["README.md"] = "\n".join(index) + "\n"
    return fichiers
