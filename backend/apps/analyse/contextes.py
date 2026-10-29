"""Contextes de données des six documents d'analyse (contrats du moteur de documents, lot 4).

Chaque fonction reçoit la mission et renvoie le contexte SANS les blocs communs `onea` et
`document`. Règle du moteur : uniquement des textes déjà formatés (dates `JJ/MM/AAAA`,
fuseau `Africa/Ouagadougou`, nombres et booléens en texte), une valeur absente est une chaîne
vide. `provisoire` vaut « Oui » tant que le document n'est pas définitif, sinon « ».
Les données du référentiel validé sont lues dans l'instantané de la confirmation (jamais en
base) : une modification postérieure n'altère pas le document.
"""

from collections.abc import Callable
from datetime import date, datetime
from itertools import groupby
from typing import Any

from django.db import models
from django.utils import timezone

from apps.missions.models import (
    AffectationMission,
    Mission,
    RoleMission,
    StatutEtape,
    TypeMission,
)
from apps.referentiel.models import NiveauRisque
from apps.signatures.models import Confirmation

from .gardes import statuts_etapes
from .models import (
    Appreciation,
    Composante,
    CouvertureOrdre,
    EvaluationConception,
    ForceFaiblesse,
    GrilleSeparation,
    MotifNonTest,
    NatureControle,
    ObjectifAudit,
    Questionnaire,
    QuestionQuestionnaire,
    RoleTache,
    TypeForceFaiblesse,
    TypeQuestionnaire,
    VarianteOrientation,
)
from .services.grilles import analyser_grille
from .services.orientation import obtenir_rapport
from .services.referentiel import instantane_referentiel, referentiel_valide

OUI = "Oui"
NON = "Non"
_CODES_ROLE = {
    RoleTache.EXECUTE.value: "E",
    RoleTache.AUTORISE.value: "A",
    RoleTache.ENREGISTRE.value: "En",
    RoleTache.CONTROLE.value: "C",
}
_FINIES = (StatutEtape.TERMINEE, StatutEtape.VALIDEE)


class CodeDocumentAnalyse(models.TextChoices):
    QUESTIONNAIRE_PRISE_CONNAISSANCE = (
        "QUESTIONNAIRE_PRISE_CONNAISSANCE",
        "Questionnaire de prise de connaissance",
    )
    GRILLE_SEPARATION_TACHES = "GRILLE_SEPARATION_TACHES", "Grille de séparation des tâches"
    QCI = "QCI", "Questionnaire de contrôle interne (QCI)"
    MARC = "MARC", "Matrice d'analyse des risques et contrôles (MARC)"
    FORCES_FAIBLESSES = "FORCES_FAIBLESSES", "Tableau des forces et faiblesses"
    RAPPORT_ORIENTATION = "RAPPORT_ORIENTATION", "Rapport d'orientation"


# --- Formatage -------------------------------------------------------------------------------


def _date(valeur: date | datetime | None) -> str:
    if valeur is None:
        return ""
    if isinstance(valeur, datetime):
        valeur = timezone.localtime(valeur)
    return valeur.strftime("%d/%m/%Y")


def _libelle(enum: type[models.TextChoices], valeur: Any) -> str:
    if not valeur:
        return ""
    try:
        return str(enum(valeur).label)
    except ValueError:
        return str(valeur)


def _nom(user: Any) -> str:
    return str(user.get_full_name() or user.username)


def _oui_non(valeur: bool) -> str:
    return OUI if valeur else NON


def _bloc_validation(confirmation: Confirmation | None) -> dict[str, str]:
    if confirmation is None:
        return {"le": "", "par": "", "empreinte": ""}
    return {
        "le": _date(confirmation.confirme_le),
        "par": _nom(confirmation.signataire),
        "empreinte": confirmation.empreinte,
    }


def _provisoire_etape(mission: Mission, numero: int) -> str:
    statut = statuts_etapes(mission.pk, (numero,)).get(numero)
    return "" if statut in _FINIES else OUI


def bloc_mission(mission: Mission) -> dict[str, Any]:
    """Bloc `mission` du contrat commun du moteur (`BLOC_MISSION`)."""
    processus = [{"code": p.code, "libelle": p.libelle} for p in mission.processus.order_by("code")]
    entites = [{"code": e.code, "libelle": e.libelle} for e in mission.entites.order_by("code")]
    debut, fin = _date(mission.periode_debut), _date(mission.periode_fin)
    periode = f"{debut} au {fin}" if debut and fin else debut or fin
    chef = (
        AffectationMission.objects.filter(mission=mission, role_mission=RoleMission.CHEF_MISSION)
        .select_related("utilisateur")
        .order_by("created_at")
        .first()
    )
    return {
        "reference": mission.reference,
        "titre": mission.titre,
        "type": _libelle(TypeMission, mission.type),
        "processus": processus,
        "processus_texte": ", ".join(p["libelle"] for p in processus),
        "entites": entites,
        "entites_texte": ", ".join(e["libelle"] for e in entites),
        "periode": periode,
        "date_debut_prevue": _date(mission.date_debut_prevue),
        "date_fin_prevue": _date(mission.date_fin_prevue),
        "chef_mission": _nom(chef.utilisateur) if chef else "",
    }


# --- Questionnaires --------------------------------------------------------------------------


def _questionnaires(mission: Mission, type_: str) -> list[dict[str, Any]]:
    sortie: list[dict[str, Any]] = []
    for q in (
        Questionnaire.objects.filter(mission=mission, type=type_)
        .select_related("processus")
        .order_by("created_at", "pk")
    ):
        questions = QuestionQuestionnaire.objects.filter(questionnaire=q).order_by(
            "ordre", "created_at", "pk"
        )
        themes: list[dict[str, Any]] = []
        numero = 0
        for theme, groupe in groupby(questions, key=lambda x: x.theme):
            lignes = []
            for question in groupe:
                numero += 1
                lignes.append(
                    {
                        "numero": str(numero),
                        "libelle": question.libelle,
                        "appreciation": _libelle(Appreciation, question.appreciation),
                        "reponse": question.reponse,
                    }
                )
            themes.append({"theme": theme, "questions": lignes})
        sortie.append(
            {
                "titre": q.titre,
                "processus": q.processus.libelle if q.processus else "",
                "themes": themes,
            }
        )
    return sortie


def contexte_questionnaire_prise_connaissance(mission: Mission) -> dict[str, Any]:
    return {
        "mission": bloc_mission(mission),
        "provisoire": _provisoire_etape(mission, 3),
        "questionnaires": _questionnaires(mission, TypeQuestionnaire.PRISE_CONNAISSANCE),
    }


def contexte_qci(mission: Mission) -> dict[str, Any]:
    return {
        "mission": bloc_mission(mission),
        "provisoire": _provisoire_etape(mission, 5),
        "questionnaires": _questionnaires(mission, TypeQuestionnaire.QCI),
    }


# --- Grille de séparation des tâches ---------------------------------------------------------


def _roles(codes: Any) -> str:
    return " / ".join(c for r, c in _CODES_ROLE.items() if r in set(codes))


def contexte_grille(mission: Mission) -> dict[str, Any]:
    grilles = []
    for g in (
        GrilleSeparation.objects.filter(mission=mission)
        .select_related("processus")
        .order_by("created_at", "pk")
    ):
        taches, acteurs = list(g.taches), list(g.acteurs)
        par_cellule = {(c["tache"], c["acteur"]): c["roles"] for c in g.cellules}
        analyse = analyser_grille(g)
        grilles.append(
            {
                "processus": g.processus.libelle,
                "acteurs": [str(a) for a in acteurs],
                "lignes": [
                    {
                        "tache": str(tache),
                        "roles_par_acteur": [
                            _roles(par_cellule.get((i, j), ())) for j in range(len(acteurs))
                        ],
                    }
                    for i, tache in enumerate(taches)
                ],
                "cumuls": [
                    {"tache": c.tache, "acteur": c.acteur, "roles": _roles(c.roles)}
                    for c in analyse.cumuls
                ],
                "taches_sans_acteur": analyse.taches_sans_acteur,
                "taches_multi_executants": analyse.taches_multi_executants,
            }
        )
    return {
        "mission": bloc_mission(mission),
        "provisoire": _provisoire_etape(mission, 3),
        "grilles": grilles,
    }


# --- Référentiel (MARC, forces et faiblesses, rapport) ---------------------------------------


def _donnees_referentiel(mission: Mission) -> tuple[dict[str, Any], Confirmation | None]:
    """Instantané validé si l'étape VI l'est, sinon l'état courant."""
    validation = referentiel_valide(mission)
    if validation is not None:
        return validation.donnees, validation
    return instantane_referentiel(mission), None


def _lignes_marc(donnees: dict[str, Any]) -> list[dict[str, str]]:
    risques = {r["id"]: r for r in donnees["risques"]}
    lignes = []
    for i, ligne in enumerate(donnees["lignes_marc"], start=1):
        risque = risques.get(ligne["risque_id"], {})
        lignes.append(
            {
                "numero": str(i),
                "risque_code": risque.get("code") or "",
                "risque_libelle": risque.get("libelle", ""),
                "niveau": _libelle(NiveauRisque, risque.get("niveau")),
                "objet_auditable": ligne["objet_auditable"] or "",
                "operation": ligne["operation"],
                "objectif_controle": ligne["objectif_controle"],
                "controle_attendu": ligne["controle_attendu"],
                "controle_existant": ligne["controle_existant"],
                "composante": _libelle(Composante, ligne["composante"]),
                "nature": _libelle(NatureControle, ligne["nature"]),
                "evaluation": _libelle(EvaluationConception, ligne["evaluation"]),
                "appreciation": _libelle(TypeForceFaiblesse, ligne["appreciation"]),
                "cle": _oui_non(bool(ligne["cle"])),
            }
        )
    return lignes


def contexte_marc(mission: Mission) -> dict[str, Any]:
    donnees, validation = _donnees_referentiel(mission)
    return {
        "mission": bloc_mission(mission),
        "provisoire": "" if validation else OUI,
        "lignes": _lignes_marc(donnees),
        "validation": _bloc_validation(validation),
    }


def _forces_faiblesses(
    mission: Mission, donnees: dict[str, Any], valide: bool
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """(forces, faiblesses) numérotées séparément ; instantané si validé, base sinon."""
    elements: list[tuple[str, dict[str, str]]] = []
    if valide:
        risques = {r["id"]: r for r in donnees["risques"]}
        processus_ligne = {
            ligne["id"]: risques.get(ligne["risque_id"], {}).get("processus", "")
            for ligne in donnees["lignes_marc"]
        }
        for ff in donnees["forces_faiblesses"]:
            elements.append(
                (
                    ff["type"],
                    {
                        "libelle": ff["libelle"],
                        "processus": processus_ligne.get(ff["ligne_marc_id"] or "", ""),
                        "consequence": ff["consequence"],
                        "commentaire": "",
                    },
                )
            )
    else:
        for ff in ForceFaiblesse.objects.filter(mission=mission).select_related("processus"):
            elements.append(
                (
                    ff.type,
                    {
                        "libelle": ff.libelle,
                        "processus": ff.processus.libelle if ff.processus else "",
                        "consequence": ff.consequence,
                        "commentaire": ff.commentaire,
                    },
                )
            )
    forces: list[dict[str, str]] = []
    faiblesses: list[dict[str, str]] = []
    for type_, valeurs in elements:
        cible = forces if type_ == TypeForceFaiblesse.FORCE else faiblesses
        ligne = {"numero": str(len(cible) + 1), **valeurs}
        if cible is forces:
            ligne.pop("consequence")
        cible.append(ligne)
    return forces, faiblesses


def contexte_forces_faiblesses(mission: Mission) -> dict[str, Any]:
    donnees, validation = _donnees_referentiel(mission)
    forces, faiblesses = _forces_faiblesses(mission, donnees, validation is not None)
    return {
        "mission": bloc_mission(mission),
        "provisoire": "" if validation else OUI,
        "forces": forces,
        "faiblesses": faiblesses,
        "validation": _bloc_validation(validation),
    }


# --- Rapport d'orientation -------------------------------------------------------------------


def contexte_rapport_orientation(mission: Mission) -> dict[str, Any]:
    donnees, validation = _donnees_referentiel(mission)
    forces, faiblesses = _forces_faiblesses(mission, donnees, validation is not None)
    rapport = obtenir_rapport(mission)
    objectifs = list(
        ObjectifAudit.objects.filter(mission=mission)
        .select_related("ligne_marc__risque")
        .order_by("numero")
    )
    equipe = AffectationMission.objects.filter(mission=mission).select_related("utilisateur")
    provisoire = OUI if validation is None or _provisoire_etape(mission, 7) else ""
    return {
        "mission": bloc_mission(mission),
        "provisoire": provisoire,
        "variante": _libelle(VarianteOrientation, rapport.variante) if rapport else "",
        "rappel_ordre": {
            "objectifs": mission.objectifs,
            "perimetre": mission.perimetre,
            "exclusions": mission.exclusions,
            "clients": mission.clients,
            "livrables_attendus": mission.livrables_attendus,
            "emis_le": _date(mission.ordre_mission_emis_le),
        },
        "contexte": rapport.contexte if rapport else "",
        "approche": rapport.approche if rapport else "",
        "risques_majeurs": [
            {"code": r["code"] or "", "libelle": r["libelle"], "score": str(r["score"])}
            for r in donnees["risques"]
            if r["niveau"] == NiveauRisque.ELEVE
        ],
        "forces": forces,
        "faiblesses": faiblesses,
        "objectifs_retenus": [
            {
                "code": o.code,
                "libelle": o.libelle,
                "risque_code": o.ligne_marc.risque.code_source,
                "controle": o.ligne_marc.controle_attendu,
            }
            for o in objectifs
            if o.retenu
        ],
        "objectifs_non_retenus": [
            {
                "code": o.code,
                "libelle": o.libelle,
                "motif": _libelle(MotifNonTest, o.motif_non_test),
                "justification": o.justification,
            }
            for o in objectifs
            if not o.retenu
        ],
        "couverture": {
            "valeur": _libelle(CouvertureOrdre, rapport.couverture_ordre) if rapport else "",
            "justification": rapport.justification_couverture if rapport else "",
        },
        "calendrier": {
            "date_debut_prevue": _date(mission.date_debut_prevue),
            "date_fin_prevue": _date(mission.date_fin_prevue),
            "budget_jours": str(mission.budget_jours),
        },
        "equipe": [
            {"nom": _nom(a.utilisateur), "role": _libelle(RoleMission, a.role_mission)}
            for a in equipe.order_by("created_at", "pk")
        ],
        "validation_referentiel": _bloc_validation(validation),
        "observations": rapport.observations if rapport else "",
    }


CONTEXTES: dict[str, Callable[[Mission], dict[str, Any]]] = {
    CodeDocumentAnalyse.QUESTIONNAIRE_PRISE_CONNAISSANCE.value: (
        contexte_questionnaire_prise_connaissance
    ),
    CodeDocumentAnalyse.GRILLE_SEPARATION_TACHES.value: contexte_grille,
    CodeDocumentAnalyse.QCI.value: contexte_qci,
    CodeDocumentAnalyse.MARC.value: contexte_marc,
    CodeDocumentAnalyse.FORCES_FAIBLESSES.value: contexte_forces_faiblesses,
    CodeDocumentAnalyse.RAPPORT_ORIENTATION.value: contexte_rapport_orientation,
}
