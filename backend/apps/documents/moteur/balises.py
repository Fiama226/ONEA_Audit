"""Static analysis of Jinja tags against the contract tree (the template is never executed).

Every `Name`/attribute/subscript chain of the parsed template is resolved against the `Champ`
tree, so a typo is found wherever it sits (untaken `{% if %}` branch, `default` filter, header,
footer, footnote, document property).
"""

from typing import Final

from jinja2 import Environment, nodes

from .contrats import CHAMPS_COMMUNS, Champ, Contrat, TypeChamp

_INCONNU: Final = Champ("?", TypeChamp.TEXTE_LONG, "valeur non typée")
_TEXTE: Final = Champ("", TypeChamp.TEXTE, "")
_SCALAIRES: Final = (TypeChamp.TEXTE, TypeChamp.TEXTE_LONG)

# Statements that load other templates or define code: never needed in a Word template.
_INSTRUCTIONS_INTERDITES: Final = (
    nodes.Import,
    nodes.FromImport,
    nodes.Include,
    nodes.Extends,
    nodes.Macro,
    nodes.CallBlock,
    nodes.Block,
)


class AnalyseBalises:
    """Collects the errors and the root tags of one or several parsed sources."""

    def __init__(self, env: Environment, contrat: Contrat) -> None:
        self._env = env
        self._contrat = contrat
        self._racine = Champ("", TypeChamp.BLOC, "", CHAMPS_COMMUNS + contrat.champs)
        self.erreurs: dict[str, None] = {}
        self.racines: set[str] = set()

    def analyser(self, source: str) -> None:
        """Parse `source` (may raise TemplateSyntaxError) and check every tag."""
        self._visiter(self._env.parse(source), {})

    # -- helpers ---------------------------------------------------------------------------

    def _erreur(self, message: str) -> None:
        self.erreurs.setdefault(message, None)

    def _inconnue(self, chemin: str) -> None:
        self._erreur(f"Balise inconnue du contrat « {self._contrat.libelle} » : {chemin}.")

    @staticmethod
    def _chemin(n: nodes.Node) -> str:
        if isinstance(n, nodes.Name):
            return n.name
        if isinstance(n, nodes.Getattr):
            return f"{AnalyseBalises._chemin(n.node)}.{n.attr}"
        if isinstance(n, nodes.Getitem):
            if isinstance(n.arg, nodes.Const) and isinstance(n.arg.value, str):
                return f"{AnalyseBalises._chemin(n.node)}.{n.arg.value}"
            return f"{AnalyseBalises._chemin(n.node)}[…]"
        return "…"

    @staticmethod
    def _element(champ: Champ) -> Champ:
        """Type of one item of a `liste`."""
        if champ.enfants:
            return Champ("", TypeChamp.BLOC, "", champ.enfants)
        return _TEXTE

    def _attribut(self, base: Champ, nom: str, noeud: nodes.Node) -> Champ:
        if nom.startswith("_"):
            self._erreur(f"Accès interdit dans les balises : {self._chemin(noeud)}.")
            return _INCONNU
        if base is _INCONNU or base.type in _SCALAIRES:
            return _INCONNU  # text methods such as .upper() are checked at render time
        if base.type is TypeChamp.BLOC:
            for enfant in base.enfants:
                if enfant.nom == nom:
                    return enfant
        self._inconnue(self._chemin(noeud))
        return _INCONNU

    # -- resolution ------------------------------------------------------------------------

    def _type(self, noeud: nodes.Node, portee: dict[str, Champ]) -> Champ:
        """Resolve an expression to a `Champ`, visiting (and checking) its sub-expressions."""
        if isinstance(noeud, nodes.Name):
            if noeud.name in portee:
                return portee[noeud.name]
            for champ in self._racine.enfants:
                if champ.nom == noeud.name:
                    self.racines.add(noeud.name)
                    return champ
            self._inconnue(noeud.name)
            return _INCONNU
        if isinstance(noeud, nodes.Getattr):
            return self._attribut(self._type(noeud.node, portee), noeud.attr, noeud)
        if isinstance(noeud, nodes.Getitem):
            base = self._type(noeud.node, portee)
            if isinstance(noeud.arg, nodes.Const) and isinstance(noeud.arg.value, str):
                return self._attribut(base, noeud.arg.value, noeud)
            self._visiter(noeud.arg, portee)
            if base.type is TypeChamp.LISTE and base is not _INCONNU:
                return self._element(base)
            return _INCONNU
        self._visiter(noeud, portee)
        return _INCONNU

    def _visiter(self, noeud: nodes.Node, portee: dict[str, Champ]) -> None:
        if isinstance(noeud, _INSTRUCTIONS_INTERDITES):
            self._erreur(f"Instruction interdite dans les balises : {type(noeud).__name__}.")
        elif isinstance(noeud, (nodes.Name, nodes.Getattr, nodes.Getitem)):
            if not (isinstance(noeud, nodes.Name) and noeud.ctx != "load"):
                self._type(noeud, portee)
        elif isinstance(noeud, nodes.For):
            self._boucle(noeud, portee)
        elif isinstance(noeud, (nodes.Assign, nodes.AssignBlock)):
            type_ = _INCONNU
            if isinstance(noeud, nodes.Assign):
                type_ = self._type(noeud.node, portee)
            else:
                for enfant in noeud.body:
                    self._visiter(enfant, portee)
            cible_assign: nodes.Node = noeud.target
            if isinstance(cible_assign, nodes.Name):
                portee[cible_assign.name] = type_
            else:
                for nom in cible_assign.find_all(nodes.Name):
                    portee[nom.name] = _INCONNU
        elif isinstance(noeud, nodes.With):
            interne = dict(portee)
            for valeur in noeud.values:
                self._visiter(valeur, portee)
            for cible_with in noeud.targets:
                if isinstance(cible_with, nodes.Name):
                    interne[cible_with.name] = _INCONNU
            for enfant in noeud.body:
                self._visiter(enfant, interne)
        elif isinstance(noeud, nodes.Filter):
            if noeud.name not in self._env.filters:
                self._erreur(f"Filtre inconnu ou interdit dans les balises : {noeud.name}.")
            for enfant in noeud.iter_child_nodes():
                self._visiter(enfant, portee)
        elif isinstance(noeud, nodes.Test):
            if noeud.name not in self._env.tests:
                self._erreur(f"Test inconnu dans les balises : {noeud.name}.")
            for enfant in noeud.iter_child_nodes():
                self._visiter(enfant, portee)
        else:
            for enfant in noeud.iter_child_nodes():
                self._visiter(enfant, portee)

    def _boucle(self, noeud: nodes.For, portee: dict[str, Champ]) -> None:
        iterable = self._type(noeud.iter, portee)
        if iterable.type is TypeChamp.LISTE and iterable is not _INCONNU:
            element = self._element(iterable)
        else:
            element = _INCONNU
        interne = dict(portee)
        interne["loop"] = _INCONNU
        if isinstance(noeud.target, nodes.Name):
            interne[noeud.target.name] = element
        else:
            for cible in noeud.target.find_all(nodes.Name):
                interne[cible.name] = _INCONNU
        if noeud.test is not None:
            self._visiter(noeud.test, interne)
        for enfant in noeud.body:
            self._visiter(enfant, interne)
        for enfant in noeud.else_:
            self._visiter(enfant, portee)
