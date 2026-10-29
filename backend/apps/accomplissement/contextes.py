"""Contextes de données des documents de l'accomplissement (contrats du moteur, lot 4).

Chaque fonction est pure (aucune écriture), borne ses requêtes (six au plus, bloc `mission`
compris) et renvoie le contexte SANS les blocs communs `onea` et `document`. Règle du moteur :
uniquement des textes déjà formatés (dates `JJ/MM/AAAA`, nombres décimaux à la française,
booléens en « Oui » / « Non »), une valeur absente est une chaîne vide. `provisoire` vaut
« Oui » tant que le document n'est pas définitif, sinon « ».

Minimisation : aucune clé de stockage, aucun identifiant interne ; les pièces n'exposent que
libellé, nom d'origine et empreinte abrégée.
"""

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from apps.analyse.contextes import _date, _libelle, _nom, bloc_mission
from apps.analyse.services.objectifs import code_objectif
from apps.missions.models import Mission

from .models import (
    ConclusionTest,
    EvenementFiche,
    FicheDeTest,
    InstantaneProgramme,
    MethodeSelection,
    NatureTest,
    PieceJustificative,
    ProgrammeDeTravail,
    StatutFiche,
    StatutTest,
    TestPrevu,
    TypeEvenementFiche,
)

OUI = "Oui"
NON = "Non"
ZERO = Decimal(0)
AUCUNE_FICHE = "Aucune fiche"
NON_AFFECTE = "Non affecté"


class CodeDocumentAccomplissement:
    PROGRAMME_TRAVAIL = "PROGRAMME_TRAVAIL"
    FEUILLE_COUVERTURE = "FEUILLE_COUVERTURE"
    FEUILLE_TRAVAIL = "FEUILLE_TRAVAIL"
    FICHE_TEST = "FICHE_TEST"


# --- Formatage -------------------------------------------------------------------------------


def formater_decimal(valeur: Decimal | None) -> str:
    """Nombre décimal à la française : `Decimal("40.5")` -> « 40,5 » ; absent -> « »."""
    if valeur is None:
        return ""
    return f"{valeur:f}".replace(".", ",")


def formater_entier(valeur: int | None) -> str:
    return "" if valeur is None else str(valeur)


def formater_pourcentage(partie: int, total: int) -> str:
    return f"{round(100 * partie / total)} %" if total else ""


def empreinte_abregee(empreinte: str) -> str:
    """Empreinte abrégée 8…8 : les huit premiers et les huit derniers caractères."""
    return f"{empreinte[:8]}…{empreinte[-8:]}" if len(empreinte) > 16 else empreinte


def _oui_non(valeur: bool) -> str:
    return OUI if valeur else NON


# --- Programme de travail (n° 13) ------------------------------------------------------------


def _ligne_test_programme(t: TestPrevu) -> dict[str, str]:
    return {
        "code": t.code,
        "libelle": t.libelle,
        "objectif_test": t.objectif_test,
        "nature": _libelle(NatureTest, t.nature),
        "procedure": t.procedure,
        "population": t.population,
        "taille_echantillon": formater_entier(t.taille_echantillon),
        "methode_selection": _libelle(MethodeSelection, t.methode_selection),
        "auditeur": _nom(t.auditeur) if t.auditeur else "",
        "charge_prevue_jours": formater_decimal(t.charge_prevue_jours),
        "date_debut_prevue": _date(t.date_debut_prevue),
        "date_fin_prevue": _date(t.date_fin_prevue),
        "complementaire": _oui_non(t.complementaire),
    }


def contexte_programme_travail(mission: Mission) -> dict[str, Any]:
    """Objectifs -> tests, ressources, totaux, dernier instantané validé (trois requêtes + bloc)."""
    programmes = list(
        ProgrammeDeTravail.objects.filter(mission=mission)
        .select_related("objectif")
        .order_by("objectif__numero")
    )
    tests = list(
        TestPrevu.objects.filter(mission=mission, statut=StatutTest.PREVU)
        .select_related("auditeur")
        .order_by("numero")
    )
    instantane = (
        InstantaneProgramme.objects.filter(mission=mission).select_related("valide_par").first()
    )
    par_programme: dict[Any, list[dict[str, str]]] = {}
    par_auditeur: dict[Any, list[Any]] = {}
    sans_auditeur: list[str] = []
    total = ZERO
    for t in tests:
        par_programme.setdefault(t.programme_id, []).append(_ligne_test_programme(t))
        charge = t.charge_prevue_jours or ZERO
        total += charge
        if t.auditeur is None:
            sans_auditeur.append(t.code)
            continue
        ligne = par_auditeur.setdefault(t.auditeur_id, [_nom(t.auditeur), 0, ZERO])
        ligne[1] += 1
        ligne[2] += charge
    return {
        "mission": bloc_mission(mission),
        "provisoire": "" if instantane else OUI,
        "objectifs": [
            {
                "code": code_objectif(p.objectif),
                "libelle": p.objectif.libelle,
                "techniques": p.techniques,
                "criteres_preuve": p.criteres_preuve,
                "commentaire": p.commentaire,
                "tests": par_programme.get(p.pk, []),
            }
            for p in programmes
        ],
        "ressources": [
            {"auditeur": nom, "nb_tests": str(nb), "charge_jours": formater_decimal(charge)}
            for nom, nb, charge in sorted(par_auditeur.values(), key=lambda ligne: ligne[0])
        ],
        "tests_sans_auditeur": sans_auditeur,
        "totaux": {
            "nb_tests": str(len(tests)),
            "charge_jours": formater_decimal(total),
            "budget_jours": formater_decimal(mission.budget_jours),
            "depassement_budget": _oui_non(total > mission.budget_jours),
        },
        "instantane": {
            "le": _date(instantane.valide_le) if instantane else "",
            "par": _nom(instantane.valide_par) if instantane else "",
            "empreinte": instantane.empreinte if instantane else "",
        },
    }


# --- Feuille de couverture des tests (n° 15) -------------------------------------------------


def contexte_feuille_couverture(mission: Mission) -> dict[str, Any]:
    """Tests prévus, complémentaires, abandonnés (avec motif), fiche, conclusion, constats."""
    tests = list(
        TestPrevu.objects.filter(mission=mission)
        .select_related("programme__objectif", "auditeur")
        .order_by("numero")
    )
    fiches: dict[Any, tuple[str, str]] = {}
    constats: dict[Any, list[str]] = {}
    lignes = (
        FicheDeTest.objects.filter(mission=mission)
        .order_by("constats__numero")
        .values_list(
            "test_id", "statut", "conclusion", "constats__reference", "constats__deleted_at"
        )
    )
    for test_id, statut, conclusion, reference, supprime_le in lignes:
        fiches[test_id] = (statut, conclusion)
        if reference and supprime_le is None:
            constats.setdefault(test_id, []).append(reference)

    def ligne(t: TestPrevu) -> dict[str, str]:
        statut, conclusion = fiches.get(t.pk, ("", ""))
        return {
            "code": t.code,
            "objectif": code_objectif(t.programme.objectif),
            "libelle": t.libelle,
            "nature": _libelle(NatureTest, t.nature),
            "auditeur": _nom(t.auditeur) if t.auditeur else NON_AFFECTE,
            "statut_fiche": _libelle(StatutFiche, statut) or AUCUNE_FICHE,
            "conclusion": _libelle(ConclusionTest, conclusion),
            "constats": ", ".join(constats.get(t.pk, [])),
        }

    prevus = [t for t in tests if t.statut == StatutTest.PREVU and not t.complementaire]
    complementaires = [t for t in tests if t.statut == StatutTest.PREVU and t.complementaire]
    abandonnes = [t for t in tests if t.statut == StatutTest.ABANDONNE]
    retenus = prevus + complementaires
    validees = sum(1 for t in retenus if fiches.get(t.pk, ("",))[0] == StatutFiche.VALIDE)
    return {
        "mission": bloc_mission(mission),
        "provisoire": "" if retenus and validees == len(retenus) else OUI,
        "tests_prevus": [ligne(t) for t in prevus],
        "tests_complementaires": [ligne(t) for t in complementaires],
        "tests_abandonnes": [{**ligne(t), "motif": t.motif_abandon} for t in abandonnes],
        "synthese": {
            "nb_prevus": str(len(prevus)),
            "nb_complementaires": str(len(complementaires)),
            "nb_abandonnes": str(len(abandonnes)),
            "nb_fiches_validees": str(validees),
            "taux_validation": formater_pourcentage(validees, len(retenus)),
        },
    }


# --- Feuille de travail (n° 16) et fiche de test ---------------------------------------------


def _fiche_chargee(fiche: FicheDeTest) -> FicheDeTest:
    """La fiche et tout ce que lisent les contextes, en une seule requête."""
    chargee: FicheDeTest = FicheDeTest.objects.select_related(
        "mission",
        "test__programme__objectif",
        "test__auditeur",
        "auteur",
        "soumise_par",
        "validee_par",
    ).get(pk=fiche.pk)
    return chargee


def _bloc_test(f: FicheDeTest) -> dict[str, str]:
    t = f.test
    objectif = t.programme.objectif
    return {
        "code": t.code,
        "libelle": t.libelle,
        "objectif_audit": f"{code_objectif(objectif)} — {objectif.libelle}",
        "objectif_test": t.objectif_test,
        "nature": _libelle(NatureTest, t.nature),
        "procedure": t.procedure,
        "population": t.population,
        "taille_echantillon": formater_entier(t.taille_echantillon),
        "methode_selection": _libelle(MethodeSelection, t.methode_selection),
        "auditeur": _nom(t.auditeur) if t.auditeur else NON_AFFECTE,
        "charge_prevue_jours": formater_decimal(t.charge_prevue_jours),
    }


def _bloc_validation(f: FicheDeTest) -> dict[str, str]:
    return {
        "statut": _libelle(StatutFiche, f.statut),
        "auteur": _nom(f.auteur),
        "soumise_le": _date(f.soumise_le),
        "soumise_par": _nom(f.soumise_par) if f.soumise_par else "",
        "validee_le": _date(f.validee_le),
        "validee_par": _nom(f.validee_par) if f.validee_par else "",
    }


def _provisoire_fiche(f: FicheDeTest) -> str:
    return "" if f.statut == StatutFiche.VALIDE else OUI


def contexte_feuille_travail(fiche: FicheDeTest) -> dict[str, Any]:
    """Test, travaux réalisés, résultat, conclusion, validation et renvoi aux constats."""
    f = _fiche_chargee(fiche)
    constats = list(f.constats.order_by("numero").values_list("reference", "titre"))
    exceptions, taille = f.nombre_exceptions, f.taille_testee
    taux = formater_pourcentage(exceptions, taille) if exceptions is not None and taille else ""
    return {
        "mission": bloc_mission(f.mission),
        "provisoire": _provisoire_fiche(f),
        "test": _bloc_test(f),
        "realisation": {
            "date_realisation": _date(f.date_realisation),
            "travaux_realises": f.travaux_realises,
            "echantillon_teste": f.echantillon_teste,
            "taille_testee": formater_entier(taille),
            "nombre_exceptions": formater_entier(exceptions),
            "taux_exception": taux,
            "resultat": f.resultat,
            "conclusion": _libelle(ConclusionTest, f.conclusion),
            "commentaire_conclusion": f.commentaire_conclusion,
            "charge_reelle_jours": formater_decimal(f.charge_reelle_jours),
        },
        "validation": _bloc_validation(f),
        "constats": [{"reference": ref, "titre": titre} for ref, titre in constats],
    }


def contexte_fiche_test(fiche: FicheDeTest) -> dict[str, Any]:
    """Fiche d'identification du test : pièces (empreinte abrégée) et journal des transitions."""
    f = _fiche_chargee(fiche)
    pieces = PieceJustificative.objects.filter(fiche=f).order_by("numero")
    evenements = EvenementFiche.objects.filter(fiche=f).select_related("par").order_by("le")
    return {
        "mission": bloc_mission(f.mission),
        "provisoire": _provisoire_fiche(f),
        "test": _bloc_test(f),
        "fiche": {
            "date_realisation": _date(f.date_realisation),
            "conclusion": _libelle(ConclusionTest, f.conclusion),
            "justification_sans_piece": f.justification_sans_piece,
            **_bloc_validation(f),
        },
        "pieces": [
            {
                "numero": str(p.numero),
                "libelle": p.libelle,
                "nom_fichier": p.nom_fichier_original,
                "empreinte": empreinte_abregee(p.empreinte_sha256),
            }
            for p in pieces
        ],
        "journal": [
            {
                "evenement": _libelle(TypeEvenementFiche, e.type),
                "le": _date(e.le),
                "par": _nom(e.par),
                "motif": e.motif,
            }
            for e in evenements
        ],
    }


CONTEXTES_MISSION: dict[str, Callable[[Mission], dict[str, Any]]] = {
    CodeDocumentAccomplissement.PROGRAMME_TRAVAIL: contexte_programme_travail,
    CodeDocumentAccomplissement.FEUILLE_COUVERTURE: contexte_feuille_couverture,
}
CONTEXTES_FICHE: dict[str, Callable[[FicheDeTest], dict[str, Any]]] = {
    CodeDocumentAccomplissement.FEUILLE_TRAVAIL: contexte_feuille_travail,
    CodeDocumentAccomplissement.FICHE_TEST: contexte_fiche_test,
}
