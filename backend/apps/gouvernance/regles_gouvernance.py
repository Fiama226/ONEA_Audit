"""Service unique des règles de gouvernance : lecture (avec cache), validation, modification.

Toute règle métier paramétrable par l'ADMIN est lue ici, jamais directement en base. Les
valeurs par défaut sont les plus prudentes, conformes aux Normes IIA 2024 et aux fiches IFACI.

* Lecture : `valeur(cle)` et les accesseurs typés (`step_order_strict()`...). Le cache partagé
  (`django.core.cache`) est invalidé à chaque changement, immédiatement et à la validation de la
  transaction ; une panne du cache se replie sur la base.
* Écriture : `modifier()` (ADMIN actif seulement, droit non délégable). Validation stricte
  (énumérations, bornes, champs inconnus refusés) ; un changement qui affaiblit un contrôle exige
  un motif et notifie le DG et le RAI. Le journal d'audit garde qui, quand, avant, après, motif.
* Non-rétroactivité : une règle est lue au moment de l'action ; rien n'est recalculé sur les
  dossiers clos (missions clôturées ou annulées, acceptations déjà décidées).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.utils import timezone

from apps.core.exceptions import RegleMetierError
from apps.core.services import enregistrer
from apps.users.models import Role, User

from .models import RegleGouvernance

logger = logging.getLogger(__name__)

__all__ = ["PermissionDenied"]

# --- Clés (anglais dans le code ; libellés français pour l'interface) -----------------------

PROGRAM_APPROVAL = "program_approval"
RISK_ACCEPTANCE = "risk_acceptance_escalation"
OBJECTIVITY = "objectivity_check"
PROGRAM_RISK_LINK = "program_risk_link"
AUDITEE_RESPONSE = "auditee_response"
STEP_ORDER = "step_order"
SEARCH_FALLBACK = "search_fallback"
AUDITEE_STEP_READ = "auditee_step_read"

CLES: tuple[str, ...] = (
    PROGRAM_APPROVAL,
    RISK_ACCEPTANCE,
    OBJECTIVITY,
    PROGRAM_RISK_LINK,
    AUDITEE_RESPONSE,
    STEP_ORDER,
    SEARCH_FALLBACK,
    AUDITEE_STEP_READ,
)

CLE_CACHE = "gouvernance:regles:v1"
DUREE_CACHE = 300  # secondes ; l'invalidation explicite reste la règle

MSG_MOTIF = "Le motif est obligatoire : ce changement assouplit un contrôle."
MSG_DROIT = "Seul l'administrateur de la plateforme peut modifier les règles de gouvernance."
MSG_VALEUR = "La valeur doit être un objet."
MSG_INCONNU = "Champ inconnu."

Sens = Literal["croissant", "neutre"]


@dataclass(frozen=True)
class Champ:
    """Champ d'une règle. `choix` est ordonné du plus faible au plus fort contrôle ; un booléen
    est plus fort à vrai ; un entier plus fort quand il croît. `sens="neutre"` : sans effet sur
    la force du contrôle (préférence d'usage)."""

    nom: str
    type: Literal["choix", "booleen", "entier"]
    choix: tuple[str, ...] = ()
    minimum: int = 0
    maximum: int = 0
    sens: Sens = "croissant"

    def valider(self, valeur: Any) -> str | None:
        if self.type == "booleen":
            return None if isinstance(valeur, bool) else "Valeur attendue : vrai ou faux."
        if self.type == "entier":
            if isinstance(valeur, bool) or not isinstance(valeur, int):
                return "Valeur attendue : un nombre entier."
            if not self.minimum <= valeur <= self.maximum:
                return f"La valeur doit être comprise entre {self.minimum} et {self.maximum}."
            return None
        if not isinstance(valeur, str) or valeur not in self.choix:
            return f"Valeur inconnue (attendu : {', '.join(self.choix)})."
        return None

    def rang(self, valeur: Any) -> int:
        if self.type == "choix":
            return self.choix.index(valeur)
        return int(valeur)


@dataclass(frozen=True)
class Regle:
    cle: str
    libelle: str
    description: str
    reference: str
    champs: tuple[Champ, ...]
    defaut: dict[str, Any]
    issue_des_normes: bool = False
    controle: Callable[[dict[str, Any]], dict[str, list[str]]] | None = field(default=None)

    def champ(self, nom: str) -> Champ | None:
        return next((c for c in self.champs if c.nom == nom), None)


APPROBATEURS = ("NONE", "DG", "DG_AND_BOARD")
VALIDATEURS = ("NONE", "RAI", "DG", "BOARD")
NIVEAUX = ("low", "medium", "high")
# Niveau de risque du référentiel (FAIBLE, MOYEN, ELEVE) -> champ de la règle d'escalade.
NIVEAU_RISQUE = {"FAIBLE": "low", "MOYEN": "medium", "ELEVE": "high"}


def _escalade_croissante(valeur: dict[str, Any]) -> dict[str, list[str]]:
    """Un niveau de risque plus élevé n'est jamais validé par une autorité plus basse."""
    erreurs: dict[str, list[str]] = {}
    precedent = 0
    for niveau in NIVEAUX:
        rang = VALIDATEURS.index(valeur[niveau])
        if rang < precedent:
            erreurs[niveau] = [
                "Un niveau de risque plus élevé ne peut pas être validé par une autorité "
                "inférieure à celle d'un niveau plus faible."
            ]
        precedent = max(precedent, rang)
    return erreurs


REGLES: dict[str, Regle] = {
    PROGRAM_APPROVAL: Regle(
        cle=PROGRAM_APPROVAL,
        libelle="Approbation du programme annuel",
        description=(
            "Qui approuve le programme annuel validé par le RAI, et si cette approbation est "
            "exigée avant de lancer une mission inscrite au programme."
        ),
        reference="Normes IIA 2024, 9.4 (le Conseil approuve le plan d'audit)",
        champs=(
            Champ("approver", "choix", choix=APPROBATEURS),
            Champ("required_before_launch", "booleen"),
        ),
        defaut={"approver": "DG_AND_BOARD", "required_before_launch": True},
        issue_des_normes=True,
    ),
    RISK_ACCEPTANCE: Regle(
        cle=RISK_ACCEPTANCE,
        libelle="Escalade d'une acceptation de risque",
        description=(
            "Autorité qui valide l'acceptation d'un risque par la direction auditée, selon le "
            "niveau du constat. Tant qu'elle n'est pas validée, l'acceptation ne couvre pas la "
            "recommandation."
        ),
        reference="Normes IIA 2024, 11.5 (acceptation des risques)",
        champs=tuple(Champ(n, "choix", choix=VALIDATEURS) for n in NIVEAUX),
        defaut={"low": "RAI", "medium": "RAI", "high": "DG"},
        controle=_escalade_croissante,
    ),
    OBJECTIVITY: Regle(
        cle=OBJECTIVITY,
        libelle="Contrôle d'objectivité",
        description=(
            "À l'affectation d'un intervenant et à l'émission de l'ordre de mission : appartenance "
            "à une entité auditée, responsabilité ou mission de conseil récente sur la même "
            "entité. Blocage ou simple avertissement, et durée de refroidissement."
        ),
        reference="Normes IIA 2024, 2.2 (garantir l'objectivité)",
        champs=(
            Champ("enabled", "booleen"),
            Champ("mode", "choix", choix=("WARN", "BLOCK")),
            Champ("cooling_off_months", "entier", minimum=0, maximum=60),
        ),
        defaut={"enabled": True, "mode": "BLOCK", "cooling_off_months": 12},
        issue_des_normes=True,
    ),
    PROGRAM_RISK_LINK: Regle(
        cle=PROGRAM_RISK_LINK,
        libelle="Lien programme ↔ risque",
        description=(
            "Une mission inscrite au programme annuel doit, dès sa création, désigner les "
            "risques de la cartographie qu'elle couvre."
        ),
        reference="Normes IIA 2024, 9.4 (plan fondé sur les risques)",
        champs=(Champ("required", "booleen"),),
        defaut={"required": True},
    ),
    AUDITEE_RESPONSE: Regle(
        cle=AUDITEE_RESPONSE,
        libelle="Réponse de l'audité",
        description=(
            "Délai de réponse au rapport provisoire, contrôles de clôture qui exigent la "
            "participation de l'audité (étapes XIII, XIV et XVI) et autorité qui peut y déroger."
        ),
        reference="Fiches IFACI XIII, XIV et XVI ; Normes IIA 2024, 11.2 et 14.4",
        champs=(
            Champ("delay_days", "entier", minimum=1, maximum=60),
            Champ("waiver_by", "choix", choix=("RAI", "DG")),
            Champ("reason_required", "booleen"),
            Champ("evidence_agreement", "booleen"),
            Champ("findings_agreed", "booleen"),
            Champ("response_or_deadline", "booleen"),
        ),
        defaut={
            "delay_days": 15,
            "waiver_by": "RAI",
            "reason_required": True,
            "evidence_agreement": True,
            "findings_agreed": True,
            "response_or_deadline": True,
        },
    ),
    STEP_ORDER: Regle(
        cle=STEP_ORDER,
        libelle="Ordre des étapes",
        description=(
            "Strict : une étape ne démarre que lorsque les précédentes sont closes ; le RAI peut "
            "déroger avec un motif journalisé. Libre : les étapes démarrent dans n'importe quel "
            "ordre."
        ),
        reference="Fiches méthodologiques IFACI (enchaînement des 18 étapes)",
        champs=(Champ("mode", "choix", choix=("FREE", "STRICT")),),
        defaut={"mode": "STRICT"},
    ),
    SEARCH_FALLBACK: Regle(
        cle=SEARCH_FALLBACK,
        libelle="Repli de la recherche",
        description=(
            "Quand le moteur de recherche est indisponible : chercher en base les missions "
            "seules, ou les missions et les constats (plus lourd pour la base)."
        ),
        reference="Choix d'exploitation (sans exigence normative)",
        champs=(
            Champ("scope", "choix", choix=("MISSIONS", "MISSIONS_AND_FINDINGS"), sens="neutre"),
        ),
        defaut={"scope": "MISSIONS"},
    ),
    AUDITEE_STEP_READ: Regle(
        cle=AUDITEE_STEP_READ,
        libelle="Lecture des étapes par l'audité",
        description=(
            "L'audité affecté lit la liste des étapes de sa mission (statuts et dates, sans "
            "charges ni journal)."
        ),
        reference="Choix de transparence (sans exigence normative)",
        champs=(Champ("allowed", "booleen", sens="neutre"),),
        defaut={"allowed": True},
    ),
}

assert tuple(REGLES) == CLES  # noqa: S101 - ordre d'affichage figé


class RegleInconnueError(Http404):
    def __init__(self, cle: str) -> None:
        super().__init__(f"Règle de gouvernance inconnue : {cle}.")


class RegleInvalideError(RegleMetierError):
    status_http = 400


def regle(cle: str) -> Regle:
    try:
        return REGLES[cle]
    except KeyError:
        raise RegleInconnueError(cle) from None


def _erreurs(definition: Regle, valeur: Any) -> dict[str, list[str]]:
    if not isinstance(valeur, dict):
        return {"valeur": [MSG_VALEUR]}
    erreurs: dict[str, list[str]] = {}
    for nom in valeur:
        if definition.champ(nom) is None:
            erreurs[nom] = [MSG_INCONNU]
    for champ in definition.champs:
        if champ.nom not in valeur:
            erreurs[champ.nom] = ["Champ obligatoire."]
            continue
        message = champ.valider(valeur[champ.nom])
        if message:
            erreurs[champ.nom] = [message]
    if not erreurs and definition.controle is not None:
        erreurs.update(definition.controle(valeur))
    return erreurs


# --- Lecture -------------------------------------------------------------------------------


def _depuis_base() -> dict[str, dict[str, Any]]:
    valeurs = {cle: dict(r.defaut) for cle, r in REGLES.items()}
    for cle, stockee in RegleGouvernance.objects.filter(cle__in=CLES).values_list("cle", "valeur"):
        definition = REGLES[cle]
        complete = {**definition.defaut, **stockee} if isinstance(stockee, dict) else stockee
        if _erreurs(definition, complete):
            logger.error("Règle de gouvernance %s invalide en base : valeur par défaut.", cle)
            continue
        valeurs[cle] = complete
    return valeurs


def _toutes() -> dict[str, dict[str, Any]]:
    try:
        en_cache = cache.get(CLE_CACHE)
    except Exception:  # noqa: BLE001 - cache indisponible : la base fait foi
        logger.warning("Cache indisponible : règles de gouvernance lues en base.")
        return _depuis_base()
    if isinstance(en_cache, dict) and set(en_cache) == set(CLES):
        return en_cache
    valeurs = _depuis_base()
    try:
        cache.set(CLE_CACHE, valeurs, DUREE_CACHE)
    except Exception:  # noqa: BLE001
        logger.warning("Cache indisponible : règles de gouvernance non mises en cache.")
    return valeurs


def invalider_cache() -> None:
    try:
        cache.delete(CLE_CACHE)
    except Exception:  # noqa: BLE001
        logger.warning("Cache indisponible : invalidation des règles de gouvernance ignorée.")


def valeur(cle: str) -> dict[str, Any]:
    """Valeur effective (copie) de la règle `cle`."""
    regle(cle)
    return dict(_toutes()[cle])


def affaiblit(cle: str, avant: dict[str, Any], apres: dict[str, Any]) -> bool:
    """Vrai si au moins un champ passe à un contrôle plus faible."""
    for champ in regle(cle).champs:
        if champ.sens == "neutre":
            continue
        if champ.rang(apres[champ.nom]) < champ.rang(avant[champ.nom]):
            return True
    return False


def est_assouplie(cle: str) -> bool:
    """La valeur courante est plus faible que la valeur de référence (par défaut)."""
    return affaiblit(cle, regle(cle).defaut, valeur(cle))


def etat_regles() -> list[dict[str, Any]]:
    """Toutes les règles, dans l'ordre d'affichage, avec l'auteur du dernier changement."""
    lignes = {
        r.cle: r for r in RegleGouvernance.objects.select_related("updated_by").filter(cle__in=CLES)
    }
    valeurs = _toutes()
    etats: list[dict[str, Any]] = []
    for cle, definition in REGLES.items():
        ligne = lignes.get(cle)
        courante = valeurs[cle]
        etats.append(
            {
                "cle": cle,
                "libelle": definition.libelle,
                "description": definition.description,
                "reference": definition.reference,
                "issue_des_normes": definition.issue_des_normes,
                "valeur": courante,
                "defaut": dict(definition.defaut),
                "assouplie": affaiblit(cle, definition.defaut, courante),
                "modifie_le": ligne.updated_at if ligne else None,
                "modifie_par": ligne.updated_by if ligne else None,
                "motif": ligne.motif if ligne else "",
            }
        )
    return etats


# --- Accesseurs typés (seuls points de lecture des autres applications) ----------------------


def program_approval() -> dict[str, Any]:
    """`approver` (NONE, DG, DG_AND_BOARD) et `required_before_launch`."""
    return valeur(PROGRAM_APPROVAL)


def risk_acceptance_validator(niveau_risque: str) -> str:
    """Autorité qui valide l'acceptation d'un risque de ce niveau : NONE, RAI, DG ou BOARD."""
    champ = NIVEAU_RISQUE.get(niveau_risque, "high")
    return str(valeur(RISK_ACCEPTANCE)[champ])


@dataclass(frozen=True)
class Objectivite:
    actif: bool
    bloquant: bool
    refroidissement_mois: int


def objectivity() -> Objectivite:
    v = valeur(OBJECTIVITY)
    return Objectivite(bool(v["enabled"]), v["mode"] == "BLOCK", int(v["cooling_off_months"]))


def program_risk_link_required() -> bool:
    return bool(valeur(PROGRAM_RISK_LINK)["required"])


def auditee_response() -> dict[str, Any]:
    """`delay_days`, `waiver_by` (RAI, DG), `reason_required` et les trois contrôles de clôture
    (`evidence_agreement` XIII, `findings_agreed` XIV, `response_or_deadline` XVI)."""
    return valeur(AUDITEE_RESPONSE)


def step_order_strict() -> bool:
    return bool(valeur(STEP_ORDER)["mode"] == "STRICT")


def search_fallback_includes_findings() -> bool:
    return bool(valeur(SEARCH_FALLBACK)["scope"] == "MISSIONS_AND_FINDINGS")


def auditee_step_read_allowed() -> bool:
    return bool(valeur(AUDITEE_STEP_READ)["allowed"])


# --- Écriture ------------------------------------------------------------------------------


def _exiger_admin(by: User) -> None:
    """ADMIN actif, relu en base : aucune délégation ne donne ce droit."""
    from apps.users.delegation import est_administrateur

    if not (isinstance(by, User) and by.role == Role.ADMIN and est_administrateur(by)):
        raise PermissionDenied(MSG_DROIT)


def _notifier_assouplissement(
    ligne: RegleGouvernance, definition: Regle, motif: str, by: User
) -> None:
    from apps.notifications.models import TypeNotification
    from apps.notifications.services import notifier

    destinataires = User.objects.filter(role__in=(Role.DG, Role.RAI), is_active=True)
    notifier(
        destinataires,
        type=TypeNotification.REGLE_ASSOUPLIE,
        titre=f"Règle de gouvernance assouplie : {definition.libelle}",
        message=(f"{by.nom_complet} a assoupli la règle « {definition.libelle} ». Motif : {motif}"),
        lien="/administration/gouvernance",
        objet=ligne,
        cle=f"regle-assouplie:{definition.cle}:{timezone.now().isoformat()}",
    )


@transaction.atomic
def modifier(cle: str, partiel: Any, *, motif: str, by: User) -> RegleGouvernance | None:
    """Change tout ou partie de la règle `cle` ; renvoie la ligne, ou None si rien ne change."""
    definition = regle(cle)
    _exiger_admin(by)
    if not isinstance(partiel, dict):
        raise RegleInvalideError("Données invalides.", {"valeur": [MSG_VALEUR]})
    inconnus = {nom: [MSG_INCONNU] for nom in partiel if definition.champ(nom) is None}
    if inconnus:
        raise RegleInvalideError("Données invalides.", inconnus)
    ligne = RegleGouvernance.objects.select_for_update().filter(cle=cle).first()
    actuelle = valeur(cle)
    nouvelle = {**actuelle, **partiel}
    erreurs = _erreurs(definition, nouvelle)
    if erreurs:
        raise RegleInvalideError("Données invalides.", erreurs)
    if nouvelle == actuelle:
        return ligne
    motif = (motif or "").strip()
    assouplissement = affaiblit(cle, actuelle, nouvelle)
    if assouplissement and not motif:
        raise RegleInvalideError(MSG_MOTIF, {"motif": [MSG_MOTIF]})
    if ligne is None:
        # Création à la valeur courante, puis changement : le journal garde un « avant ».
        ligne = RegleGouvernance(cle=cle, valeur=actuelle)
        enregistrer(ligne, by=by, creation=True)
    ligne.valeur = nouvelle
    ligne.motif = motif
    ligne.audit_motif = motif
    ligne.audit_affaiblissement = assouplissement
    enregistrer(ligne, by=by)
    invalider_cache()
    transaction.on_commit(invalider_cache)
    if assouplissement:
        _notifier_assouplissement(ligne, definition, motif, by)
    return ligne
