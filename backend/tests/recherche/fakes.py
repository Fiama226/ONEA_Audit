"""Moteur de recherche en mémoire : même protocole que `MeilisearchHttp`, sans réseau.

Filtres pris en charge (sous-ensemble de la syntaxe Meilisearch) : `champ = "v"`,
`champ IN ["a", "b"]`, `AND`, `OR`, parenthèses. Un champ liste (ex. `audience`) correspond
si la valeur y figure.
"""

import re
import unicodedata
from typing import Any

from apps.recherche.client import MARQUEUR_DEBUT, MARQUEUR_FIN, Hit

_JETON = re.compile(r'\s*(?:"((?:[^"\\]|\\.)*)"|(\(|\)|\[|\]|,)|([^\s()\[\],"]+))')


def _sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c)).casefold()


def _jetons(filtre: str) -> list[tuple[str, str]]:
    res: list[tuple[str, str]] = []
    pos = 0
    filtre = filtre.rstrip()
    while pos < len(filtre):
        m = _JETON.match(filtre, pos)
        if m is None:
            raise ValueError("Filtre invalide.")
        if m.group(1) is not None:
            res.append(("str", re.sub(r"\\(.)", r"\1", m.group(1))))
        elif m.group(2):
            res.append(("sym", m.group(2)))
        else:
            res.append(("mot", m.group(3)))
        pos = m.end()
    return res


class _Filtre:
    def __init__(self, filtre: str) -> None:
        self.j = _jetons(filtre)
        self.i = 0
        self.arbre = self._ou() if self.j else None
        if self.i != len(self.j):
            raise ValueError("Filtre invalide.")

    def _suivant(self) -> tuple[str, str] | None:
        return self.j[self.i] if self.i < len(self.j) else None

    def _prendre(self) -> tuple[str, str]:
        jeton = self._suivant()
        if jeton is None:
            raise ValueError("Filtre invalide.")
        self.i += 1
        return jeton

    def _ou(self) -> Any:
        termes = [self._et()]
        while self._suivant() == ("mot", "OR"):
            self.i += 1
            termes.append(self._et())
        return ("or", termes)

    def _et(self) -> Any:
        facteurs = [self._facteur()]
        while self._suivant() == ("mot", "AND"):
            self.i += 1
            facteurs.append(self._facteur())
        return ("and", facteurs)

    def _facteur(self) -> Any:
        jeton = self._prendre()
        if jeton == ("sym", "("):
            arbre = self._ou()
            if self._prendre() != ("sym", ")"):
                raise ValueError("Filtre invalide.")
            return arbre
        champ = jeton[1]
        operateur = self._prendre()
        if operateur == ("sym", "=") or operateur[1] == "=":
            valeur = self._prendre()
            if valeur[0] != "str":
                raise ValueError("Filtre invalide.")
            return ("in", champ, [valeur[1]])
        if operateur == ("mot", "IN"):
            if self._prendre() != ("sym", "["):
                raise ValueError("Filtre invalide.")
            valeurs: list[str] = []
            while True:
                v = self._prendre()
                if v[0] != "str":
                    raise ValueError("Filtre invalide.")
                valeurs.append(v[1])
                fin = self._prendre()
                if fin == ("sym", "]"):
                    return ("in", champ, valeurs)
                if fin != ("sym", ","):
                    raise ValueError("Filtre invalide.")
        raise ValueError("Filtre invalide.")

    def evaluer(self, doc: dict[str, Any], noeud: Any = None) -> bool:
        noeud = noeud or self.arbre
        if noeud is None:
            return True
        genre = noeud[0]
        if genre == "or":
            return any(self.evaluer(doc, n) for n in noeud[1])
        if genre == "and":
            return all(self.evaluer(doc, n) for n in noeud[1])
        valeur = doc.get(noeud[1])
        candidats = valeur if isinstance(valeur, list) else [valeur]
        return any(c is not None and str(c) in noeud[2] for c in candidats)


class MoteurMemoire:
    CHAMPS = ("titre", "reference", "mission_reference", "sous_titre", "texte")

    def __init__(self, **_options: Any) -> None:
        self.documents: dict[str, dict[str, Any]] = {}
        self.configure = False

    def configurer(self) -> None:
        self.configure = True

    def indexer(self, documents: list[dict[str, Any]]) -> None:
        for doc in documents:
            self.documents[str(doc["id"])] = dict(doc)

    def retirer(self, ids: list[str]) -> None:
        for i in ids:
            self.documents.pop(i, None)

    def vider(self) -> None:
        self.documents.clear()

    def sante(self) -> bool:
        return True

    @staticmethod
    def _surligner(texte: str, q: str) -> str:
        if not q:
            return texte
        plat = _sans_accents(texte)
        cible = _sans_accents(q)
        debut = plat.find(cible)
        if debut < 0 or len(plat) != len(texte):
            return texte
        fin = debut + len(cible)
        return f"{texte[:debut]}{MARQUEUR_DEBUT}{texte[debut:fin]}{MARQUEUR_FIN}{texte[fin:]}"

    @staticmethod
    def _recadrer(texte: str, q: str, mots: int = 30) -> str:
        liste = texte.split()
        if len(liste) <= mots:
            return texte
        cible = _sans_accents(q)
        pos = next((k for k, m in enumerate(liste) if cible and cible in _sans_accents(m)), 0)
        debut = max(0, min(pos - mots // 2, len(liste) - mots))
        return " ".join(liste[debut : debut + mots])

    def rechercher(self, q: str, *, filtre: str, limite: int) -> list[Hit]:
        critere = _Filtre(filtre)
        cible = _sans_accents(q.strip())
        hits: list[Hit] = []
        for doc in self.documents.values():
            if not critere.evaluer(doc):
                continue
            if cible and not any(cible in _sans_accents(str(doc.get(c, ""))) for c in self.CHAMPS):
                continue
            hits.append(
                Hit(
                    id=str(doc["id"]),
                    type=str(doc.get("type", "")),
                    objet_id=str(doc.get("objet_id", "")),
                    mission_id=doc.get("mission_id"),
                    titre=self._surligner(str(doc.get("titre", "")), q.strip()),
                    sous_titre=str(doc.get("sous_titre", "")),
                    extrait=self._surligner(
                        self._recadrer(str(doc.get("texte", "")), q.strip()), q.strip()
                    ),
                )
            )
        return hits[:limite]
