"""Types de documents d'analyse enregistrés auprès du moteur de documents (lot 4).

Contrats v1 : toute rupture exige une version 2. Les pages `docs/documents/contrats/<CODE>.md`
sont générées par `python manage.py contrats_documents --ecrire`, jamais écrites à la main.
Appelé par `AnalyseConfig.ready` ; l'objet source de chaque document est la mission.
"""

from typing import Any
from uuid import UUID

from django.shortcuts import get_object_or_404

from apps.documents.moteur.contrats import BLOC_MISSION, EXEMPLE_COMMUN, Champ, Contrat, TypeChamp
from apps.documents.moteur.registre import TypeDocument, enregistrer_type
from apps.missions.models import Mission
from apps.signatures.models import Confirmation
from apps.users.models import User

from .contextes import CONTEXTES, CodeDocumentAnalyse
from .droits import droits_analyse
from .services.referentiel import referentiel_valide

T, TL, L, B = TypeChamp.TEXTE, TypeChamp.TEXTE_LONG, TypeChamp.LISTE, TypeChamp.BLOC

_PROVISOIRE = Champ("provisoire", T, "« Oui » tant que le document n'est pas définitif, sinon vide")
_VALIDATION = Champ(
    "validation",
    B,
    "Validation du référentiel d'audit (vide tant qu'il n'est pas validé)",
    (
        Champ("le", T, "Date de validation (JJ/MM/AAAA)"),
        Champ("par", T, "Personne ayant validé"),
        Champ("empreinte", T, "Empreinte SHA-256 de l'instantané validé"),
    ),
)


def _force(*, avec_consequence: bool) -> tuple[Champ, ...]:
    champs = [
        Champ("numero", T, "Numéro"),
        Champ("libelle", T, "Libellé"),
        Champ("processus", T, "Processus concerné"),
    ]
    if avec_consequence:
        champs.append(Champ("consequence", TL, "Conséquence"))
    champs.append(Champ("commentaire", TL, "Commentaire"))
    return tuple(champs)


_FORCES = Champ("forces", L, "Forces", _force(avec_consequence=False))
_FAIBLESSES = Champ("faiblesses", L, "Faiblesses", _force(avec_consequence=True))

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
_VALIDATION_EX = {"le": "15/03/2026", "par": "Prénom Nom", "empreinte": "0" * 64}
_FORCE_EX = {
    "numero": "1",
    "libelle": "Double signature des bons de commande",
    "processus": "Achats",
    "commentaire": "",
}
_FAIBLESSE_EX = {
    "numero": "1",
    "libelle": "Absence de rapprochement des factures",
    "processus": "Achats",
    "consequence": "Paiements indus non détectés",
    "commentaire": "",
}

_QUESTIONNAIRES = Champ(
    "questionnaires",
    L,
    "Questionnaires de la mission",
    (
        Champ("titre", T, "Titre du questionnaire"),
        Champ("processus", T, "Processus concerné (vide si général)"),
        Champ(
            "themes",
            L,
            "Thèmes",
            (
                Champ("theme", T, "Intitulé du thème"),
                Champ(
                    "questions",
                    L,
                    "Questions du thème",
                    (
                        Champ("numero", T, "Numéro de la question"),
                        Champ("libelle", T, "Question"),
                        Champ("appreciation", T, "Appréciation : Oui, Non, Sans objet ou vide"),
                        Champ("reponse", TL, "Réponse"),
                    ),
                ),
            ),
        ),
    ),
)
_QUESTIONNAIRE_EX = {
    "titre": "Questionnaire de prise de connaissance",
    "processus": "",
    "themes": [
        {
            "theme": "Objectifs",
            "questions": [
                {
                    "numero": "1",
                    "libelle": "Quels sont les objectifs du processus ?",
                    "appreciation": "Oui",
                    "reponse": "Sécuriser les achats.",
                }
            ],
        }
    ],
}


def _contrat(
    code: CodeDocumentAnalyse, champs: tuple[Champ, ...], exemple: dict[str, Any]
) -> Contrat:
    return Contrat(
        code=code.value,
        libelle=code.label,
        version=1,
        champs=(BLOC_MISSION, _PROVISOIRE, *champs),
        exemple=EXEMPLE_COMMUN
        | {"mission": _MISSION_EX, "provisoire": "Oui"}
        | exemple
        | {"document": EXEMPLE_COMMUN["document"] | {"type": code.label}},
    )


_LIGNE_MARC = (
    Champ("numero", T, "Numéro de la ligne"),
    Champ("risque_code", T, "Code du risque"),
    Champ("risque_libelle", T, "Libellé du risque"),
    Champ("niveau", T, "Niveau du risque"),
    Champ("objet_auditable", T, "Objet auditable"),
    Champ("operation", T, "Opération"),
    Champ("objectif_controle", TL, "Objectif de contrôle"),
    Champ("controle_attendu", TL, "Contrôle attendu"),
    Champ("controle_existant", TL, "Contrôle existant"),
    Champ("composante", T, "Composante du contrôle interne"),
    Champ("nature", T, "Nature du contrôle"),
    Champ("evaluation", T, "Évaluation de la conception"),
    Champ("appreciation", T, "Force ou faiblesse"),
    Champ("cle", T, "Contrôle clé : Oui ou Non"),
)
_LIGNE_MARC_EX = {
    "numero": "1",
    "risque_code": "ACH-01",
    "risque_libelle": "Fractionnement des marchés",
    "niveau": "Élevé",
    "objet_auditable": "Commission des marchés",
    "operation": "Passation d'un marché",
    "objectif_controle": "Respecter les seuils de passation",
    "controle_attendu": "Revue par la commission",
    "controle_existant": "Double signature",
    "composante": "Activité de contrôle",
    "nature": "Préventif",
    "evaluation": "Conception adéquate — risque maîtrisé",
    "appreciation": "Force",
    "cle": "Oui",
}

_OBJECTIFS = (
    Champ("code", T, "Code de l'objectif (OA-01)"),
    Champ("libelle", T, "Objectif d'audit"),
)

CONTRATS: dict[str, Contrat] = {
    c.code: c
    for c in (
        _contrat(
            CodeDocumentAnalyse.QUESTIONNAIRE_PRISE_CONNAISSANCE,
            (_QUESTIONNAIRES,),
            {"questionnaires": [_QUESTIONNAIRE_EX]},
        ),
        _contrat(
            CodeDocumentAnalyse.QCI,
            (_QUESTIONNAIRES,),
            {
                "questionnaires": [
                    _QUESTIONNAIRE_EX | {"titre": "Questionnaire de contrôle interne"}
                ]
            },
        ),
        _contrat(
            CodeDocumentAnalyse.GRILLE_SEPARATION_TACHES,
            (
                Champ(
                    "grilles",
                    L,
                    "Grilles de séparation des tâches (une par processus)",
                    (
                        Champ("processus", T, "Processus"),
                        Champ("acteurs", L, "Acteurs (colonnes)"),
                        Champ(
                            "lignes",
                            L,
                            "Tâches (lignes)",
                            (
                                Champ("tache", T, "Tâche"),
                                Champ(
                                    "roles_par_acteur",
                                    L,
                                    "Rôles de chaque acteur, dans l'ordre des acteurs : "
                                    "E, A, En, C séparés par « / »",
                                ),
                            ),
                        ),
                        Champ(
                            "cumuls",
                            L,
                            "Cumuls de rôles incompatibles",
                            (
                                Champ("tache", T, "Tâche"),
                                Champ("acteur", T, "Acteur"),
                                Champ("roles", T, "Rôles cumulés"),
                            ),
                        ),
                        Champ("taches_sans_acteur", L, "Tâches sans acteur"),
                        Champ("taches_multi_executants", L, "Tâches à plusieurs exécutants"),
                    ),
                ),
            ),
            {
                "grilles": [
                    {
                        "processus": "Achats",
                        "acteurs": ["Agent", "Chef de service"],
                        "lignes": [
                            {"tache": "Saisir la commande", "roles_par_acteur": ["E / C", "A"]}
                        ],
                        "cumuls": [
                            {"tache": "Saisir la commande", "acteur": "Agent", "roles": "E / C"}
                        ],
                        "taches_sans_acteur": [],
                        "taches_multi_executants": [],
                    }
                ]
            },
        ),
        _contrat(
            CodeDocumentAnalyse.MARC,
            (
                Champ("lignes", L, "Lignes de la matrice", _LIGNE_MARC),
                _VALIDATION,
            ),
            {"lignes": [_LIGNE_MARC_EX], "validation": _VALIDATION_EX},
        ),
        _contrat(
            CodeDocumentAnalyse.FORCES_FAIBLESSES,
            (_FORCES, _FAIBLESSES, _VALIDATION),
            {"forces": [_FORCE_EX], "faiblesses": [_FAIBLESSE_EX], "validation": _VALIDATION_EX},
        ),
        _contrat(
            CodeDocumentAnalyse.RAPPORT_ORIENTATION,
            (
                Champ("variante", T, "Variante : complet ou simplifié"),
                Champ(
                    "rappel_ordre",
                    B,
                    "Rappel de l'ordre de mission",
                    (
                        Champ("objectifs", TL, "Objectifs"),
                        Champ("perimetre", TL, "Périmètre"),
                        Champ("exclusions", TL, "Exclusions"),
                        Champ("clients", TL, "Clients de la mission"),
                        Champ("livrables_attendus", TL, "Livrables attendus"),
                        Champ("emis_le", T, "Date d'émission de l'ordre (JJ/MM/AAAA)"),
                    ),
                ),
                Champ("contexte", TL, "Contexte"),
                Champ("approche", TL, "Approche d'audit"),
                Champ(
                    "risques_majeurs",
                    L,
                    "Risques de niveau élevé",
                    (
                        Champ("code", T, "Code du risque"),
                        Champ("libelle", T, "Libellé du risque"),
                        Champ("score", T, "Score"),
                    ),
                ),
                _FORCES,
                _FAIBLESSES,
                Champ(
                    "objectifs_retenus",
                    L,
                    "Objectifs d'audit retenus",
                    (
                        *_OBJECTIFS,
                        Champ("risque_code", T, "Code du risque couvert"),
                        Champ("controle", TL, "Contrôle attendu"),
                    ),
                ),
                Champ(
                    "objectifs_non_retenus",
                    L,
                    "Objectifs d'audit non retenus",
                    (
                        *_OBJECTIFS,
                        Champ("motif", T, "Motif de non-test"),
                        Champ("justification", TL, "Justification"),
                    ),
                ),
                Champ(
                    "couverture",
                    B,
                    "Couverture de l'ordre de mission",
                    (
                        Champ("valeur", T, "Couverture exacte ou élargie"),
                        Champ("justification", TL, "Justification"),
                    ),
                ),
                Champ(
                    "calendrier",
                    B,
                    "Calendrier et budget",
                    (
                        Champ("date_debut_prevue", T, "Date de début prévue (JJ/MM/AAAA)"),
                        Champ("date_fin_prevue", T, "Date de fin prévue (JJ/MM/AAAA)"),
                        Champ("budget_jours", T, "Budget en jours"),
                    ),
                ),
                Champ(
                    "equipe",
                    L,
                    "Équipe de la mission",
                    (Champ("nom", T, "Nom"), Champ("role", T, "Rôle dans la mission")),
                ),
                Champ(
                    "validation_referentiel",
                    B,
                    "Validation du référentiel d'audit",
                    _VALIDATION.enfants,
                ),
                Champ("observations", TL, "Observations"),
            ),
            {
                "variante": "Rapport d'orientation complet",
                "rappel_ordre": {
                    "objectifs": "Évaluer le dispositif de contrôle interne des achats.",
                    "perimetre": "Processus achats, exercice 2025.",
                    "exclusions": "",
                    "clients": "Direction générale",
                    "livrables_attendus": "Rapport d'audit",
                    "emis_le": "20/02/2026",
                },
                "contexte": "Contexte de la mission.",
                "approche": "Tests de conformité sur échantillon.",
                "risques_majeurs": [
                    {"code": "ACH-01", "libelle": "Fractionnement des marchés", "score": "20"}
                ],
                "forces": [_FORCE_EX],
                "faiblesses": [_FAIBLESSE_EX],
                "objectifs_retenus": [
                    {
                        "code": "OA-01",
                        "libelle": "Vérifier le respect des seuils",
                        "risque_code": "ACH-01",
                        "controle": "Revue par la commission",
                    }
                ],
                "objectifs_non_retenus": [
                    {
                        "code": "OA-02",
                        "libelle": "Vérifier l'archivage",
                        "motif": "Conception adaptée",
                        "justification": "Contrôle jugé suffisant.",
                    }
                ],
                "couverture": {"valeur": "Couverture exacte", "justification": ""},
                "calendrier": {
                    "date_debut_prevue": "02/03/2026",
                    "date_fin_prevue": "30/04/2026",
                    "budget_jours": "40.0",
                },
                "equipe": [{"nom": "A. Ouédraogo", "role": "Chef de mission"}],
                "validation_referentiel": _VALIDATION_EX,
                "observations": "",
            },
        ),
    )
}

# (étape, abréviation du numéro) — abréviations à confirmer avec l'ONEA.
_PARAMETRES: dict[str, tuple[int, str]] = {
    CodeDocumentAnalyse.QUESTIONNAIRE_PRISE_CONNAISSANCE.value: (3, "QPC"),
    CodeDocumentAnalyse.GRILLE_SEPARATION_TACHES.value: (3, "GST"),
    CodeDocumentAnalyse.QCI.value: (5, "QCI"),
    CodeDocumentAnalyse.MARC.value: (6, "MARC"),
    CodeDocumentAnalyse.FORCES_FAIBLESSES.value: (6, "FF"),
    CodeDocumentAnalyse.RAPPORT_ORIENTATION.value: (7, "RO"),
}


class FournisseurAnalyse:
    """Fournisseur du moteur : l'objet source est la mission (un document par mission)."""

    def __init__(self, code: str) -> None:
        self.code = code

    def objet(self, objet_id: UUID) -> Mission:
        return get_object_or_404(Mission, pk=objet_id)

    def mission_de(self, objet: Mission) -> Mission:
        return objet

    def objets_de_mission(self, mission: Mission) -> list[Mission]:
        return [mission]

    def peut_consulter(self, user: User, objet: Mission) -> bool:
        return droits_analyse(user, objet).voir_travaux

    def peut_generer(self, user: User, objet: Mission) -> bool:
        return droits_analyse(user, objet).voir_travaux

    def raison_non_generable(self, objet: Mission) -> str | None:
        return None

    def contexte(self, objet: Mission) -> dict[str, Any]:
        return CONTEXTES[self.code](objet)

    def confirmation(self, objet: Mission) -> Confirmation | None:
        if self.code in ("MARC", "FORCES_FAIBLESSES", "RAPPORT_ORIENTATION"):
            return referentiel_valide(objet)
        return None


def enregistrer_types() -> None:
    """Enregistre les six types ; idempotent si l'application est rechargée."""
    for code, contrat in CONTRATS.items():
        etape, abreviation = _PARAMETRES[code]
        try:
            enregistrer_type(
                TypeDocument(
                    code=code,
                    libelle=contrat.libelle,
                    etape=etape,
                    contrat=contrat,
                    abreviation=abreviation,
                    modele_numero="{mission}/{code}-{sequence:02d}",
                    portee_numero="MISSION",
                    fournisseur=FournisseurAnalyse(code),  # type: ignore[arg-type]
                )
            )
        except ValueError:
            continue
