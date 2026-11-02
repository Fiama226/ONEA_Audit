"""Types de documents de l'accomplissement enregistrés auprès du moteur de documents (lot 4).

Contrats v1 : toute rupture exige une version 2. Les pages `docs/documents/contrats/<CODE>.md`
sont générées par `python manage.py contrats_documents --ecrire`, jamais écrites à la main.
Appelé par `AccomplissementConfig.ready`. Programme et feuille de couverture ont la mission pour
objet source ; feuille de travail et fiche de test ont la fiche de test.
"""

from typing import Any
from uuid import UUID

from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.documents.moteur.contrats import BLOC_MISSION, EXEMPLE_COMMUN, Champ, Contrat, TypeChamp
from apps.documents.moteur.registre import TypeDocument, enregistrer_type
from apps.missions.acces import role_dans_mission
from apps.missions.models import ROLES_INTERVENANTS, Mission
from apps.signatures.models import Confirmation
from apps.users.models import Role, User

from .contextes import CONTEXTES_FICHE, CONTEXTES_MISSION, CodeDocumentAccomplissement
from .models import FicheDeTest

T, TL, L, B = TypeChamp.TEXTE, TypeChamp.TEXTE_LONG, TypeChamp.LISTE, TypeChamp.BLOC
C = CodeDocumentAccomplissement

_PROVISOIRE = Champ("provisoire", T, "« Oui » tant que le document n'est pas définitif, sinon vide")

_MISSION_EX: dict[str, Any] = {
    "reference": "DAI/2026/M01",
    "titre": "Audit du processus de passation des marchés",
    "type": "Mission planifiée",
    "processus": [{"code": "ACH", "libelle": "Achats"}],
    "processus_texte": "Achats",
    "entites": [{"code": "DAF", "libelle": "Direction administrative et financière"}],
    "entites_texte": "Direction administrative et financière",
    "periode": "01/01/2025 au 31/12/2025",
    "date_debut_prevue": "02/03/2026",
    "date_fin_prevue": "30/04/2026",
    "chef_mission": "A. Ouédraogo",
}


def _contrat(
    code: str, libelle: str, champs: tuple[Champ, ...], exemple: dict[str, Any]
) -> Contrat:
    return Contrat(
        code=code,
        libelle=libelle,
        version=1,
        champs=(BLOC_MISSION, _PROVISOIRE, *champs),
        exemple=EXEMPLE_COMMUN
        | {"mission": _MISSION_EX, "provisoire": "Oui"}
        | exemple
        | {"document": EXEMPLE_COMMUN["document"] | {"type": libelle}},
    )


# --- Programme de travail --------------------------------------------------------------------

_TEST_PROGRAMME = (
    Champ("code", T, "Code du test (T-01)"),
    Champ("libelle", T, "Libellé du test"),
    Champ("objectif_test", TL, "Objectif du test"),
    Champ("nature", T, "Nature du test"),
    Champ("procedure", TL, "Procédure"),
    Champ("population", TL, "Population"),
    Champ("taille_echantillon", T, "Taille de l'échantillon"),
    Champ("methode_selection", T, "Méthode de sélection"),
    Champ("auditeur", T, "Auditeur chargé du test"),
    Champ("charge_prevue_jours", T, "Charge prévue en jours (nombre à la française)"),
    Champ("date_debut_prevue", T, "Début prévu (JJ/MM/AAAA)"),
    Champ("date_fin_prevue", T, "Fin prévue (JJ/MM/AAAA)"),
    Champ("complementaire", T, "Test complémentaire : Oui ou Non"),
)
_TEST_PROGRAMME_EX = {
    "code": "T-01",
    "libelle": "Contrôle des bons de commande",
    "objectif_test": "Vérifier la double signature.",
    "nature": "Examen documentaire",
    "procedure": "Examiner un échantillon de bons de commande.",
    "population": "Bons de commande de l'exercice 2025",
    "taille_echantillon": "30",
    "methode_selection": "Aléatoire",
    "auditeur": "B. Sawadogo",
    "charge_prevue_jours": "2,5",
    "date_debut_prevue": "02/03/2026",
    "date_fin_prevue": "06/03/2026",
    "complementaire": "Non",
}

_PROGRAMME = (
    Champ(
        "objectifs",
        L,
        "Objectifs d'audit retenus et leurs tests",
        (
            Champ("code", T, "Code de l'objectif (OA-01)"),
            Champ("libelle", T, "Objectif d'audit"),
            Champ("techniques", TL, "Techniques et sources d'information"),
            Champ("criteres_preuve", TL, "Critères de preuve"),
            Champ("commentaire", TL, "Commentaire"),
            Champ("tests", L, "Tests prévus de l'objectif", _TEST_PROGRAMME),
        ),
    ),
    Champ(
        "ressources",
        L,
        "Ressources : charge par auditeur",
        (
            Champ("auditeur", T, "Auditeur"),
            Champ("nb_tests", T, "Nombre de tests"),
            Champ("charge_jours", T, "Charge en jours"),
        ),
    ),
    Champ("tests_sans_auditeur", L, "Codes des tests sans auditeur"),
    Champ(
        "totaux",
        B,
        "Totaux du programme",
        (
            Champ("nb_tests", T, "Nombre de tests prévus"),
            Champ("charge_jours", T, "Charge totale en jours"),
            Champ("budget_jours", T, "Budget de la mission en jours"),
            Champ("depassement_budget", T, "Charge supérieure au budget : Oui ou Non"),
        ),
    ),
    Champ(
        "instantane",
        B,
        "Dernier instantané validé du programme (vide avant la validation de l'étape X)",
        (
            Champ("le", T, "Date de validation (JJ/MM/AAAA)"),
            Champ("par", T, "Personne ayant validé"),
            Champ("empreinte", T, "Empreinte SHA-256 de l'instantané"),
        ),
    ),
)
_PROGRAMME_EX = {
    "objectifs": [
        {
            "code": "OA-01",
            "libelle": "Vérifier le respect des seuils",
            "techniques": "Entretiens, examen documentaire.",
            "criteres_preuve": "Preuve suffisante et fiable.",
            "commentaire": "",
            "tests": [_TEST_PROGRAMME_EX],
        }
    ],
    "ressources": [{"auditeur": "B. Sawadogo", "nb_tests": "1", "charge_jours": "2,5"}],
    "tests_sans_auditeur": [],
    "totaux": {
        "nb_tests": "1",
        "charge_jours": "2,5",
        "budget_jours": "40,0",
        "depassement_budget": "Non",
    },
    "instantane": {"le": "15/03/2026", "par": "Prénom Nom", "empreinte": "0" * 64},
}

# --- Feuille de couverture -------------------------------------------------------------------

_LIGNE_COUVERTURE = (
    Champ("code", T, "Code du test"),
    Champ("objectif", T, "Code de l'objectif d'audit"),
    Champ("libelle", T, "Libellé du test"),
    Champ("nature", T, "Nature du test"),
    Champ("auditeur", T, "Auditeur (« Non affecté » à défaut)"),
    Champ("statut_fiche", T, "Statut de la fiche (« Aucune fiche » à défaut)"),
    Champ("conclusion", T, "Conclusion du test"),
    Champ("constats", T, "Références des constats liés, séparées par des virgules"),
)
_LIGNE_COUVERTURE_EX = {
    "code": "T-01",
    "objectif": "OA-01",
    "libelle": "Contrôle des bons de commande",
    "nature": "Examen documentaire",
    "auditeur": "B. Sawadogo",
    "statut_fiche": "Validée",
    "conclusion": "Anomalie",
    "constats": "C-01",
}
_COUVERTURE = (
    Champ("tests_prevus", L, "Tests prévus", _LIGNE_COUVERTURE),
    Champ("tests_complementaires", L, "Tests complémentaires", _LIGNE_COUVERTURE),
    Champ(
        "tests_abandonnes",
        L,
        "Tests abandonnés",
        (*_LIGNE_COUVERTURE, Champ("motif", TL, "Motif de l'abandon")),
    ),
    Champ(
        "synthese",
        B,
        "Synthèse de la couverture",
        (
            Champ("nb_prevus", T, "Nombre de tests prévus"),
            Champ("nb_complementaires", T, "Nombre de tests complémentaires"),
            Champ("nb_abandonnes", T, "Nombre de tests abandonnés"),
            Champ("nb_fiches_validees", T, "Nombre de fiches validées"),
            Champ("taux_validation", T, "Part des tests retenus dont la fiche est validée"),
        ),
    ),
)
_COUVERTURE_EX = {
    "tests_prevus": [_LIGNE_COUVERTURE_EX],
    "tests_complementaires": [],
    "tests_abandonnes": [
        {**_LIGNE_COUVERTURE_EX, "code": "T-02", "motif": "Doublon du test T-01."}
    ],
    "synthese": {
        "nb_prevus": "1",
        "nb_complementaires": "0",
        "nb_abandonnes": "1",
        "nb_fiches_validees": "1",
        "taux_validation": "100 %",
    },
}

# --- Feuille de travail et fiche de test -----------------------------------------------------

_BLOC_TEST = Champ(
    "test",
    B,
    "Test prévu",
    (
        Champ("code", T, "Code du test"),
        Champ("libelle", T, "Libellé du test"),
        Champ("objectif_audit", T, "Objectif d'audit (code et libellé)"),
        Champ("objectif_test", TL, "Objectif du test"),
        Champ("nature", T, "Nature du test"),
        Champ("procedure", TL, "Procédure"),
        Champ("population", TL, "Population"),
        Champ("taille_echantillon", T, "Taille de l'échantillon prévue"),
        Champ("methode_selection", T, "Méthode de sélection"),
        Champ("auditeur", T, "Auditeur chargé du test"),
        Champ("charge_prevue_jours", T, "Charge prévue en jours"),
    ),
)
_BLOC_TEST_EX = {
    "code": "T-01",
    "libelle": "Contrôle des bons de commande",
    "objectif_audit": "OA-01 — Vérifier le respect des seuils",
    "objectif_test": "Vérifier la double signature.",
    "nature": "Examen documentaire",
    "procedure": "Examiner un échantillon de bons de commande.",
    "population": "Bons de commande de l'exercice 2025",
    "taille_echantillon": "30",
    "methode_selection": "Aléatoire",
    "auditeur": "B. Sawadogo",
    "charge_prevue_jours": "2,5",
}
_CHAMPS_VALIDATION = (
    Champ("statut", T, "Statut de la fiche"),
    Champ("auteur", T, "Auteur de la fiche"),
    Champ("soumise_le", T, "Date de soumission (JJ/MM/AAAA)"),
    Champ("soumise_par", T, "Personne ayant soumis"),
    Champ("validee_le", T, "Date de validation (JJ/MM/AAAA)"),
    Champ("validee_par", T, "Personne ayant validé"),
)
_VALIDATION_EX = {
    "statut": "Validée",
    "auteur": "B. Sawadogo",
    "soumise_le": "10/03/2026",
    "soumise_par": "B. Sawadogo",
    "validee_le": "12/03/2026",
    "validee_par": "C. Zongo",
}
_TRAVAIL = (
    _BLOC_TEST,
    Champ(
        "realisation",
        B,
        "Réalisation du test",
        (
            Champ("date_realisation", T, "Date de réalisation (JJ/MM/AAAA)"),
            Champ("travaux_realises", TL, "Travaux réalisés"),
            Champ("echantillon_teste", TL, "Échantillon testé"),
            Champ("taille_testee", T, "Taille testée"),
            Champ("nombre_exceptions", T, "Nombre d'exceptions"),
            Champ("taux_exception", T, "Taux d'exception (vide si non calculable)"),
            Champ("resultat", TL, "Résultat"),
            Champ("conclusion", T, "Conclusion du test"),
            Champ("commentaire_conclusion", TL, "Commentaire de la conclusion"),
            Champ("charge_reelle_jours", T, "Charge réelle en jours"),
        ),
    ),
    Champ("validation", B, "Rédaction et validation de la fiche", _CHAMPS_VALIDATION),
    Champ(
        "constats",
        L,
        "Constats issus de la fiche",
        (Champ("reference", T, "Référence du constat"), Champ("titre", T, "Titre du constat")),
    ),
)
_TRAVAIL_EX = {
    "test": _BLOC_TEST_EX,
    "realisation": {
        "date_realisation": "09/03/2026",
        "travaux_realises": "Examen de 30 bons de commande.",
        "echantillon_teste": "Bons n° 1 à 30",
        "taille_testee": "30",
        "nombre_exceptions": "3",
        "taux_exception": "10 %",
        "resultat": "Trois bons ne portent qu'une signature.",
        "conclusion": "Anomalie",
        "commentaire_conclusion": "",
        "charge_reelle_jours": "2,0",
    },
    "validation": _VALIDATION_EX,
    "constats": [{"reference": "C-01", "titre": "Bons de commande à signature unique"}],
}
_FICHE_TEST = (
    _BLOC_TEST,
    Champ(
        "fiche",
        B,
        "Fiche de test",
        (
            Champ("date_realisation", T, "Date de réalisation (JJ/MM/AAAA)"),
            Champ("conclusion", T, "Conclusion du test"),
            Champ("justification_sans_piece", TL, "Justification de l'absence de pièce"),
            *_CHAMPS_VALIDATION,
        ),
    ),
    Champ(
        "pieces",
        L,
        "Pièces justificatives",
        (
            Champ("numero", T, "Numéro de la pièce"),
            Champ("libelle", T, "Libellé"),
            Champ("nom_fichier", T, "Nom du fichier d'origine"),
            Champ("empreinte", T, "Empreinte SHA-256 abrégée (8 premiers…8 derniers caractères)"),
        ),
    ),
    Champ(
        "journal",
        L,
        "Journal des transitions de la fiche",
        (
            Champ("evenement", T, "Événement"),
            Champ("le", T, "Date (JJ/MM/AAAA)"),
            Champ("par", T, "Personne"),
            Champ("motif", TL, "Motif"),
        ),
    ),
)
_FICHE_TEST_EX = {
    "test": _BLOC_TEST_EX,
    "fiche": {
        "date_realisation": "09/03/2026",
        "conclusion": "Anomalie",
        "justification_sans_piece": "",
        **_VALIDATION_EX,
    },
    "pieces": [
        {
            "numero": "1",
            "libelle": "Bon de commande n° 12",
            "nom_fichier": "bc-12.pdf",
            "empreinte": "abcdef01…23456789",
        }
    ],
    "journal": [
        {"evenement": "Soumise", "le": "10/03/2026", "par": "B. Sawadogo", "motif": ""},
        {"evenement": "Validée", "le": "12/03/2026", "par": "C. Zongo", "motif": ""},
    ],
}

CONTRATS: dict[str, Contrat] = {
    c.code: c
    for c in (
        _contrat(C.PROGRAMME_TRAVAIL, "Programme de travail", _PROGRAMME, _PROGRAMME_EX),
        _contrat(
            C.FEUILLE_COUVERTURE, "Feuille de couverture des tests", _COUVERTURE, _COUVERTURE_EX
        ),
        _contrat(C.FEUILLE_TRAVAIL, "Feuille de travail", _TRAVAIL, _TRAVAIL_EX),
        _contrat(C.FICHE_TEST, "Fiche de test", _FICHE_TEST, _FICHE_TEST_EX),
    )
}

# (étape, abréviation du numéro) — abréviations à confirmer avec l'ONEA.
_PARAMETRES: dict[str, tuple[int, str]] = {
    C.PROGRAMME_TRAVAIL: (10, "PT"),
    C.FEUILLE_COUVERTURE: (13, "FCT"),
    C.FEUILLE_TRAVAIL: (13, "FDT"),
    C.FICHE_TEST: (12, "FIT"),
}


def _voit(user: User, mission: Mission) -> bool:
    """RAI et intervenants de la mission ; ni l'audité ni les autres."""
    return user.role == Role.RAI or (
        user.role == Role.AUDITEUR and role_dans_mission(user, mission) in ROLES_INTERVENANTS
    )


class FournisseurMission:
    """Programme et feuille de couverture : l'objet source est la mission."""

    def __init__(self, code: str) -> None:
        self.code = code

    def objet(self, objet_id: UUID) -> Mission:
        return get_object_or_404(Mission, pk=objet_id)

    def mission_de(self, objet: Mission) -> Mission:
        return objet

    def objets_de_mission(self, mission: Mission) -> list[Mission]:
        return [mission]

    def peut_consulter(self, user: User, objet: Mission) -> bool:
        return _voit(user, objet)

    def peut_generer(self, user: User, objet: Mission) -> bool:
        return _voit(user, objet)

    def raison_non_generable(self, objet: Mission) -> str | None:
        return None

    def contexte(self, objet: Mission) -> dict[str, Any]:
        return CONTEXTES_MISSION[self.code](objet)

    def confirmation(self, objet: Mission) -> Confirmation | None:
        return None


class FournisseurFiche:
    """Feuille de travail et fiche de test : l'objet source est la fiche de test."""

    def __init__(self, code: str) -> None:
        self.code = code

    def objet(self, objet_id: UUID) -> FicheDeTest:
        try:
            fiche: FicheDeTest = FicheDeTest.objects.select_related("mission").get(pk=objet_id)
            return fiche
        except FicheDeTest.DoesNotExist:
            raise Http404 from None

    def mission_de(self, objet: FicheDeTest) -> Mission:
        return objet.mission

    def objets_de_mission(self, mission: Mission) -> list[FicheDeTest]:
        return list(FicheDeTest.objects.filter(mission=mission).order_by("test__numero"))

    def peut_consulter(self, user: User, objet: FicheDeTest) -> bool:
        return _voit(user, objet.mission)

    def peut_generer(self, user: User, objet: FicheDeTest) -> bool:
        return _voit(user, objet.mission)

    def raison_non_generable(self, objet: FicheDeTest) -> str | None:
        return None

    def contexte(self, objet: FicheDeTest) -> dict[str, Any]:
        return CONTEXTES_FICHE[self.code](objet)

    def confirmation(self, objet: FicheDeTest) -> Confirmation | None:
        return None


def enregistrer_types() -> None:
    """Enregistre les quatre types ; idempotent si l'application est rechargée."""
    for code, contrat in CONTRATS.items():
        etape, abreviation = _PARAMETRES[code]
        fournisseur = (
            FournisseurMission(code) if code in CONTEXTES_MISSION else FournisseurFiche(code)
        )
        try:
            enregistrer_type(
                TypeDocument(
                    code=code,
                    libelle=contrat.libelle,
                    etape=etape,
                    contrat=contrat,
                    abreviation=abreviation,
                    modele_numero="{mission}/{code}-{sequence}",
                    portee_numero="MISSION",
                    fournisseur=fournisseur,  # type: ignore[arg-type]
                )
            )
        except ValueError:
            continue
