"""Contrats v1 des documents du lot 7 côté communication (D10).

Toute rupture exige une version 2. Les pages `docs/documents/contrats/<CODE>.md` sont générées
par `python manage.py contrats_documents --ecrire`, jamais écrites à la main. Toutes les valeurs
sont des chaînes déjà formatées, jamais `None`.
"""

from typing import Any

from apps.documents.moteur.contrats import BLOC_MISSION, EXEMPLE_COMMUN, Champ, Contrat, TypeChamp

T, TL, L, B = TypeChamp.TEXTE, TypeChamp.TEXTE_LONG, TypeChamp.LISTE, TypeChamp.BLOC

MISSION_EX: dict[str, Any] = {
    "reference": "DAI/2026/M01",
    "titre": "Audit du processus de passation des marchés",
    "type": "Mission planifiée",
    "processus": [{"code": "ACH", "libelle": "Achats"}],
    "processus_texte": "Achats",
    "entites": [{"code": "DAF", "libelle": "Direction administrative et financière"}],
    "entites_texte": "Direction administrative et financière",
    "periode": "du 01/01/2025 au 31/12/2025",
    "date_debut_prevue": "02/03/2026",
    "date_fin_prevue": "30/04/2026",
    "chef_mission": "A. Ouédraogo",
}

_VALIDATION = Champ(
    "validation",
    B,
    "Validation du rapport par le RAI (vide tant que le rapport n'est pas validé)",
    (
        Champ("par", T, "Personne ayant validé"),
        Champ("le", T, "Date de validation (JJ/MM/AAAA)"),
        Champ("heure", T, "Heure de validation (HH:MM)"),
        Champ("empreinte", T, "Empreinte SHA-256 de la confirmation"),
        Champ("mode", T, "Mode de signature"),
    ),
)
VALIDATION_EX = {
    "par": "Prénom Nom",
    "le": "15/03/2026",
    "heure": "10:30",
    "empreinte": "0" * 64,
    "mode": "Confirmation horodatée",
}
VALIDATION_VIDE = {"par": "", "le": "", "heure": "", "empreinte": "", "mode": ""}

_TOTAUX = Champ(
    "totaux",
    B,
    "Totaux du rapport",
    (
        Champ("nb_constats", T, "Nombre de constats"),
        Champ("nb_eleves", T, "Constats de niveau élevé"),
        Champ("nb_moyens", T, "Constats de niveau moyen"),
        Champ("nb_faibles", T, "Constats de niveau faible"),
        Champ("nb_recommandations", T, "Nombre de recommandations"),
        Champ("nb_actions", T, "Nombre d'actions correctives"),
    ),
)
TOTAUX_EX = {
    "nb_constats": "3",
    "nb_eleves": "1",
    "nb_moyens": "1",
    "nb_faibles": "1",
    "nb_recommandations": "4",
    "nb_actions": "5",
}

_POINTS_FORTS = Champ(
    "points_forts",
    L,
    "Points forts relevés",
    (
        Champ("code", T, "Code du test"),
        Champ("libelle", T, "Libellé du test"),
        Champ("commentaire", TL, "Commentaire de conclusion"),
    ),
)
POINTS_FORTS_EX = [
    {
        "code": "T-01",
        "libelle": "Double signature des bons de commande",
        "commentaire": "Dispositif respecté sur tout l'échantillon.",
    }
]

_PLAN_ACTIONS_LIGNE = (
    Champ("reference", T, "Référence de l'action (A-nn)"),
    Champ("libelle", TL, "Mesure corrective"),
    Champ("responsable", T, "Responsable"),
    Champ("echeance", T, "Échéance (JJ/MM/AAAA)"),
    Champ("indicateur", TL, "Indicateur de mise en œuvre"),
)
_CONSTATS_RAPPORT = Champ(
    "constats",
    L,
    "Constats validés, par niveau décroissant puis référence",
    (
        Champ("reference", T, "Référence du constat"),
        Champ("titre", T, "Titre du constat"),
        Champ("entite", T, "Entité concernée"),
        Champ("niveau", T, "Niveau de risque"),
        Champ("fait_constate", TL, "Fait constaté"),
        Champ("referentiel", TL, "Référentiel"),
        Champ("causes_texte", TL, "Causes, par catégorie"),
        Champ("consequence", TL, "Conséquence"),
        Champ("conclusion", TL, "Conclusion"),
        Champ("position_audite", TL, "Position de l'audité sur le constat"),
        Champ("reponse_direction", TL, "Réponse de la direction au rapport provisoire"),
        Champ("recommandations_texte", TL, "Recommandations, une par ligne"),
        Champ("plan_actions", L, "Actions correctives du constat", _PLAN_ACTIONS_LIGNE),
    ),
)
CONSTAT_RAPPORT_EX = {
    "reference": "C-01",
    "titre": "Absence de rapprochement des factures",
    "entite": "Direction administrative et financière",
    "niveau": "Élevé",
    "fait_constate": "Les factures ne sont pas rapprochées des bons de livraison.",
    "referentiel": "Procédure d'achat, article 4.",
    "causes_texte": "Méthodes : procédure non appliquée",
    "consequence": "Paiements indus non détectés.",
    "conclusion": "Le contrôle n'est pas opérant.",
    "position_audite": "Accord — Constat reconnu.",
    "reponse_direction": "La direction s'engage à rapprocher les factures.",
    "recommandations_texte": "1. Rapprocher les factures (Priorité : Haute)",
    "plan_actions": [
        {
            "reference": "A-01",
            "libelle": "Instaurer le rapprochement mensuel",
            "responsable": "A. Kaboré",
            "echeance": "30/06/2026",
            "indicateur": "Taux de factures rapprochées",
        }
    ],
}


def contrat_rapport(code: str, libelle: str) -> Contrat:
    """Contrat commun au rapport provisoire et au rapport final (D10)."""
    final = code == "RAPPORT_FINAL"
    return Contrat(
        code=code,
        libelle=libelle,
        version=1,
        champs=(
            BLOC_MISSION,
            Champ(
                "rapport",
                B,
                "Identification du rapport",
                (
                    Champ("numero_version", T, "Numéro de version du rapport"),
                    Champ("mention_correction", T, "Mention du rapport corrigé (vide sinon)"),
                    Champ("provisoire", T, "« Oui » pour le rapport provisoire, sinon vide"),
                    Champ("date_limite_reponses", T, "Date limite des réponses (JJ/MM/AAAA)"),
                ),
            ),
            Champ(
                "sections",
                B,
                "Sections rédigées par l'équipe",
                (
                    Champ("synthese", TL, "Synthèse pour l'encadrement supérieur"),
                    Champ("appreciation", T, "Appréciation globale"),
                    Champ("commentaire_appreciation", TL, "Commentaire de l'appréciation"),
                    Champ("contexte", TL, "Contexte"),
                    Champ("objectifs", TL, "Objectifs"),
                    Champ("perimetre", TL, "Périmètre"),
                    Champ("methodologie", TL, "Méthodologie"),
                    Champ("conclusion", TL, "Conclusion"),
                    Champ("annexes", TL, "Annexes"),
                ),
            ),
            _CONSTATS_RAPPORT,
            _POINTS_FORTS,
            _TOTAUX,
            Champ(
                "engagements",
                L,
                "Engagement de chaque responsable sur ses actions (rapport final)",
                (
                    Champ("responsable", T, "Responsable"),
                    Champ("nb_actions", T, "Nombre d'actions"),
                    Champ("etat", T, "État de l'engagement"),
                ),
            ),
            _VALIDATION,
        ),
        exemple=EXEMPLE_COMMUN
        | {
            "mission": MISSION_EX,
            "rapport": {
                "numero_version": "1",
                "mention_correction": "",
                "provisoire": "" if final else "Oui",
                "date_limite_reponses": "" if final else "20/03/2026",
            },
            "sections": {
                "synthese": "Le dispositif de contrôle des achats est perfectible.",
                "appreciation": "Maîtrise perfectible",
                "commentaire_appreciation": "Deux contrôles clés ne sont pas opérants.",
                "contexte": "Mission planifiée au programme annuel.",
                "objectifs": "Évaluer le dispositif de contrôle interne des achats.",
                "perimetre": "Direction administrative et financière, exercice 2025.",
                "methodologie": "Tests de conformité sur échantillon.",
                "conclusion": "Les recommandations doivent être mises en œuvre.",
                "annexes": "",
            },
            "constats": [CONSTAT_RAPPORT_EX],
            "points_forts": POINTS_FORTS_EX,
            "totaux": TOTAUX_EX,
            "engagements": [{"responsable": "A. Kaboré", "nb_actions": "2", "etat": "Confirmé"}]
            if final
            else [],
            "validation": VALIDATION_EX if final else VALIDATION_VIDE,
            "document": EXEMPLE_COMMUN["document"] | {"type": libelle},
        },
    )


CONTRAT_RAPPORT_PROVISOIRE = contrat_rapport("RAPPORT_PROVISOIRE", "Rapport provisoire")
CONTRAT_RAPPORT_FINAL = contrat_rapport("RAPPORT_FINAL", "Rapport d'audit")

CONTRAT_NOTE_SYNTHETIQUE = Contrat(
    code="NOTE_SYNTHETIQUE",
    libelle="Note synthétique",
    version=1,
    champs=(
        BLOC_MISSION,
        Champ("synthese", TL, "Note synthétique saisie, à défaut la synthèse du rapport"),
        Champ("appreciation", T, "Appréciation globale"),
        Champ("commentaire_appreciation", TL, "Commentaire de l'appréciation"),
        Champ(
            "constats_eleves",
            L,
            "Constats de niveau élevé",
            (
                Champ("reference", T, "Référence du constat"),
                Champ("titre", T, "Titre du constat"),
                Champ("recommandation_principale", TL, "Recommandation principale"),
            ),
        ),
        _TOTAUX,
        _VALIDATION,
    ),
    exemple=EXEMPLE_COMMUN
    | {
        "mission": MISSION_EX,
        "synthese": "Le dispositif de contrôle des achats est perfectible.",
        "appreciation": "Maîtrise perfectible",
        "commentaire_appreciation": "Deux contrôles clés ne sont pas opérants.",
        "constats_eleves": [
            {
                "reference": "C-01",
                "titre": "Absence de rapprochement des factures",
                "recommandation_principale": "Rapprocher les factures des bons de livraison.",
            }
        ],
        "totaux": TOTAUX_EX,
        "validation": VALIDATION_EX,
        "document": EXEMPLE_COMMUN["document"] | {"type": "Note synthétique"},
    },
)

CONTRAT_PV_CLOTURE = Contrat(
    code="PV_CLOTURE",
    libelle="PV de la réunion de clôture",
    version=1,
    champs=(
        BLOC_MISSION,
        Champ(
            "reunion",
            B,
            "Réunion de clôture",
            (
                Champ("date", T, "Date de la réunion (JJ/MM/AAAA)"),
                Champ("heure", T, "Heure de la réunion (HH:MM)"),
                Champ("lieu", T, "Lieu de la réunion"),
                Champ("ordre_du_jour", TL, "Ordre du jour"),
                Champ("decisions", TL, "Décisions prises"),
                Champ("compte_rendu", TL, "Compte rendu"),
                Champ("tenue_le", T, "Date à laquelle la réunion a été tenue"),
                Champ(
                    "participants",
                    L,
                    "Participants internes",
                    (
                        Champ("nom", T, "Nom du participant"),
                        Champ("fonction", T, "Fonction"),
                        Champ("direction", T, "Direction (code)"),
                    ),
                ),
                Champ("participants_externes", L, "Participants externes"),
                Champ("redacteur", T, "Rédacteur du PV (chef de mission)"),
            ),
        ),
        Champ(
            "constats_presentes",
            L,
            "Constats validés présentés à la réunion",
            (
                Champ("reference", T, "Référence du constat"),
                Champ("titre", T, "Titre du constat"),
                Champ("niveau", T, "Niveau de risque"),
                Champ("position_audite", TL, "Position de l'audité"),
            ),
        ),
        _POINTS_FORTS,
        Champ(
            "modalites",
            B,
            "Modalités de la suite de la communication",
            (Champ("date_limite_reponses", T, "Date limite des réponses (vide si non transmis)"),),
        ),
    ),
    exemple=EXEMPLE_COMMUN
    | {
        "mission": MISSION_EX,
        "reunion": {
            "date": "10/03/2026",
            "heure": "09:00",
            "lieu": "Salle de réunion du siège",
            "ordre_du_jour": "Présentation des constats\nRecommandations",
            "decisions": "Le rapport provisoire sera transmis sous huit jours.",
            "compte_rendu": "La réunion s'est tenue en présence de la direction auditée.",
            "tenue_le": "10/03/2026",
            "participants": [{"nom": "Mme Kaboré", "fonction": "Directrice", "direction": "DAF"}],
            "participants_externes": ["M. Traoré — Cabinet partenaire"],
            "redacteur": "A. Ouédraogo",
        },
        "constats_presentes": [
            {
                "reference": "C-01",
                "titre": "Absence de rapprochement des factures",
                "niveau": "Élevé",
                "position_audite": "Accord — Constat reconnu.",
            }
        ],
        "points_forts": POINTS_FORTS_EX,
        "modalites": {"date_limite_reponses": "20/03/2026"},
        "document": EXEMPLE_COMMUN["document"] | {"type": "PV de la réunion de clôture"},
    },
)

CONTRAT_FICHE_SUIVI_MISSION = Contrat(
    code="FICHE_SUIVI_MISSION",
    libelle="Fiche de suivi de la mission",
    version=1,
    champs=(
        BLOC_MISSION,
        Champ(
            "lignes",
            L,
            "Étapes de la mission",
            (
                Champ("etape", T, "Numéro et titre de l'étape"),
                Champ("statut", T, "Statut de l'étape"),
                Champ("debut_prevu", T, "Début prévu (JJ/MM/AAAA)"),
                Champ("fin_prevue", T, "Fin prévue (JJ/MM/AAAA)"),
                Champ("debut_reel", T, "Début réel (JJ/MM/AAAA)"),
                Champ("fin_reelle", T, "Fin réelle (JJ/MM/AAAA)"),
                Champ("ecart", T, "Écart en jours (positif = retard)"),
                Champ("charge_prevue", T, "Charge prévue en jours"),
                Champ("charge_reelle", T, "Charge réelle en jours"),
            ),
        ),
        Champ(
            "totaux",
            B,
            "Charges de la mission",
            (
                Champ("budget_jours", T, "Budget en jours"),
                Champ("charge_prevue", T, "Total des charges prévues"),
                Champ("charge_reelle", T, "Total des charges réelles"),
            ),
        ),
    ),
    exemple=EXEMPLE_COMMUN
    | {
        "mission": MISSION_EX,
        "lignes": [
            {
                "etape": "I — Ordre de mission",
                "statut": "Validée",
                "debut_prevu": "02/03/2026",
                "fin_prevue": "04/03/2026",
                "debut_reel": "02/03/2026",
                "fin_reelle": "05/03/2026",
                "ecart": "1",
                "charge_prevue": "2.0",
                "charge_reelle": "2.5",
            }
        ],
        "totaux": {"budget_jours": "40.0", "charge_prevue": "2.0", "charge_reelle": "2.5"},
        "document": EXEMPLE_COMMUN["document"] | {"type": "Fiche de suivi de la mission"},
    },
)
