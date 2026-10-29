"""Banque provisoire de questions (gabarits ONEA non reçus ; à confirmer avec ONEA).

Chaque entrée est un couple (thème, question).
"""

from .models import TypeQuestionnaire

QUESTIONS: dict[TypeQuestionnaire, tuple[tuple[str, str], ...]] = {
    TypeQuestionnaire.PRISE_CONNAISSANCE: (
        (
            "Objectifs",
            "Quels sont les objectifs du domaine et comment déclinent-ils ceux de l'ONEA ?",
        ),
        (
            "Objectifs",
            "Quels objectifs relèvent des opérations, de la fiabilité de l'information, "
            "de la stratégie, de la conformité ?",
        ),
        ("Organisation", "Quel est l'organigramme du domaine et quels sont les effectifs ?"),
        ("Organisation", "Quelles délégations de pouvoirs et de signature sont en vigueur ?"),
        ("Procédures", "Quels manuels de procédures et fiches de poste décrivent les activités ?"),
        ("Procédures", "Les procédures sont-elles à jour, diffusées et appliquées ?"),
        ("Systèmes d'information", "Quelles applications supportent le processus ?"),
        (
            "Pilotage",
            "Quels indicateurs de performance (coût, qualité, délais, conformité) sont suivis, "
            "avec quelles cibles ?",
        ),
        ("Réglementation", "Quels textes, contrats et normes encadrent l'activité ?"),
        (
            "Historique",
            "Quels audits, contrôles ou incidents ont concerné le domaine ces trois dernières "
            "années ?",
        ),
        (
            "Changements",
            "Quels changements d'organisation ou de système sont intervenus ou prévus ?",
        ),
    ),
    TypeQuestionnaire.QCI: (
        (
            "Autorisations",
            "Les opérations sont-elles autorisées par une personne habilitée avant exécution ?",
        ),
        ("Autorisations", "Les seuils d'autorisation sont-ils formalisés ?"),
        (
            "Séparation des tâches",
            "Les fonctions d'autorisation, d'exécution, d'enregistrement et de contrôle sont-elles "
            "séparées ?",
        ),
        ("Supervision", "Un responsable revoit-il périodiquement les opérations ?"),
        ("Supervision", "Les revues sont-elles matérialisées (visa, date) ?"),
        ("Vérifications", "Des rapprochements sont-ils effectués et documentés ?"),
        ("Vérifications", "Les anomalies détectées sont-elles suivies jusqu'à leur résolution ?"),
        ("Formalisation", "Les procédures de contrôle sont-elles écrites et diffusées ?"),
        (
            "Conservation des pièces",
            "Les pièces justificatives sont-elles archivées et accessibles ?",
        ),
        ("Conservation des pièces", "L'accès aux pièces et aux données est-il restreint ?"),
    ),
}
