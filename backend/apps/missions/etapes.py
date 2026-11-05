"""Registre des 18 étapes IFACI (source : docs/domaine/processus-ifaci.md).

`lot_livrables` : lot du plan qui gère les livrables de l'étape (D7). Les étapes I, II, IV et XI
(lot 3) ont des contrôles de livrables dès ce lot.
"""

from dataclasses import dataclass

from .models import Phase, StatutMission, TypeReunion


@dataclass(frozen=True)
class DefinitionEtape:
    numero: int
    romain: str
    titre: str
    phase: Phase
    jalon: bool
    objectif: str
    livrables: tuple[str, ...]
    acteurs: str
    lot_livrables: int


_P, _A, _C = Phase.PLANIFICATION, Phase.ACCOMPLISSEMENT, Phase.COMMUNICATION

ETAPES: tuple[DefinitionEtape, ...] = (
    DefinitionEtape(
        1,
        "I",
        "Préciser les objectifs et le périmètre de la mission",
        _P,
        False,
        "Préciser les objectifs, le périmètre et les livrables de la mission, en fonction de "
        "l'événement déclenchant la mission et conformément aux attentes des clients de la "
        "mission.",
        ("Ordre de mission",),
        "RAI (ou délégataire), Clients de la mission",
        3,
    ),
    DefinitionEtape(
        2,
        "II",
        "Conduire la réunion d'ouverture",
        _P,
        False,
        "Matérialiser le démarrage officiel de la mission et en expliciter le contenu et les "
        "modalités.",
        (
            "Compte rendu de la réunion d'ouverture",
            "Calendrier des premiers entretiens",
            "Liste de contacts",
        ),
        "RAI, Auditeurs, Audités",
        3,
    ),
    DefinitionEtape(
        3,
        "III",
        "Analyser les processus et leurs objectifs",
        _P,
        False,
        "Comprendre le domaine audité, ses enjeux, les processus mis en œuvre et leurs objectifs.",
        ("Description des processus du domaine audité et de leurs objectifs",),
        "Auditeurs",
        5,
    ),
    DefinitionEtape(
        4,
        "IV",
        "Identifier et évaluer les risques",
        _P,
        False,
        "Faire l'inventaire des événements qui pourraient empêcher l'atteinte des objectifs du "
        "domaine audité, mesurer leur probabilité de survenance et leur impact.",
        ("Cartographie des risques du domaine audité",),
        "Auditeurs, Audités",
        3,
    ),
    DefinitionEtape(
        5,
        "V",
        "Évaluer la conception du dispositif de contrôle",
        _P,
        False,
        "Identifier les contrôles clés existants et évaluer la conception du dispositif de "
        "contrôle au regard de référentiels externes s'ils s'appliquent.",
        ("Le référentiel d'audit",),
        "Auditeurs ; Audités (responsables du domaine audité)",
        5,
    ),
    DefinitionEtape(
        6,
        "VI",
        "Valider le référentiel d'audit",
        _P,
        True,
        "Valider, avec les audités, la référence à partir de laquelle le dispositif de contrôle "
        "interne va être évalué au cours de la mission.",
        ("Référentiel d'audit validé",),
        "Auditeurs ; Responsables du domaine audité",
        5,
    ),
    DefinitionEtape(
        7,
        "VII",
        "Sélectionner les objectifs d'audit",
        _P,
        False,
        "Définir le périmètre des travaux à réaliser sur le terrain.",
        ("Les objectifs d'audit",),
        "Auditeurs",
        5,
    ),
    DefinitionEtape(
        8,
        "VIII",
        "Élaborer le programme de travail",
        _P,
        False,
        "Définir les procédures d'audit qui permettront d'atteindre les objectifs d'audit.",
        ("Programme de travail",),
        "Auditeurs",
        6,
    ),
    DefinitionEtape(
        9,
        "IX",
        "Ajuster le budget et allouer les ressources",
        _P,
        False,
        "Évaluer les ressources nécessaires à la mise en œuvre du programme de travail ; "
        "identifier les ressources disponibles et les affecter.",
        ("Programme de travail enrichi du budget et du calendrier",),
        "RAI, Superviseur",
        6,
    ),
    DefinitionEtape(
        10,
        "X",
        "Valider l'organisation de la mission",
        _P,
        True,
        "Approuver formellement le programme de travail.",
        ("Programme de travail validé",),
        "RAI",
        6,
    ),
    DefinitionEtape(
        11,
        "XI",
        "Conduire la réunion de lancement de la phase Accomplissement",
        _A,
        False,
        "Matérialiser le démarrage officiel de la phase Accomplissement de la mission.",
        (
            "Compte rendu de la réunion de lancement",
            "Calendrier des premiers entretiens",
            "Liste de contacts",
        ),
        "RAI, Auditeurs (superviseur, chef de mission, directeur de mission, auditeur expert, "
        "consultant externe), Audités",
        3,
    ),
    DefinitionEtape(
        12,
        "XII",
        "Collecter les informations et constituer les preuves d'audit",
        _A,
        False,
        "Obtenir des preuves sur la capacité des dispositifs de contrôle à maîtriser les "
        "risques ou non.",
        ("Fiches de tests",),
        "Auditeurs ; Audités (évaluation des résultats et conclusions)",
        6,
    ),
    DefinitionEtape(
        13,
        "XIII",
        "Valider les preuves d'audit",
        _A,
        True,
        "Valider, avec les audités, le résultat des tests d'audit.",
        ("Fiches de tests validées",),
        "Auditeurs, Audités",
        6,
    ),
    DefinitionEtape(
        14,
        "XIV",
        "Analyser les causes, élaborer les recommandations",
        _A,
        False,
        "Identifier les raisons pour lesquelles les contrôles ne sont pas mis en œuvre de "
        "façon satisfaisante ; élaborer des mesures correctives.",
        ("Observations d'audit validées par les audités",),
        "Auditeurs, Audités",
        6,
    ),
    DefinitionEtape(
        15,
        "XV",
        "Conduire la réunion de clôture",
        _C,
        False,
        "Faire valider par les responsables du domaine audité la cohérence et la formulation "
        "définitive de l'ensemble des observations d'audit.",
        (
            "Observations d'audit validées par les responsables du domaine audité "
            "(et ébauche du plan d'actions)",
        ),
        "Auditeurs ; Audités (responsables du domaine audité)",
        7,
    ),
    DefinitionEtape(
        16,
        "XVI",
        "Finaliser le plan d'actions",
        _C,
        False,
        "Documenter les modalités de mise en œuvre opérationnelles des mesures correctives.",
        ("Plan d'actions finalisé",),
        "Responsables du domaine audité ; responsables des domaines concernés par les mesures "
        "correctives ; Audités",
        7,
    ),
    DefinitionEtape(
        17,
        "XVII",
        "Rédiger le rapport",
        _C,
        False,
        "Documenter les résultats définitifs et officiels de la mission pour diffusion aux "
        "clients de la mission.",
        ("Rapport d'audit",),
        "Auditeur, Chef de mission",
        7,
    ),
    DefinitionEtape(
        18,
        "XVIII",
        "Valider le rapport",
        _C,
        True,
        "Approuver formellement le rapport d'audit.",
        ("Rapport d'audit validé",),
        "RAI",
        7,
    ),
)

_PAR_NUMERO: dict[int, DefinitionEtape] = {e.numero: e for e in ETAPES}

JALONS: frozenset[int] = frozenset(e.numero for e in ETAPES if e.jalon)
JALONS_DELEGABLES: frozenset[int] = frozenset({6, 10, 13})

PHASE_DU_STATUT: dict[str, Phase] = {
    StatutMission.EN_PLANIFICATION: Phase.PLANIFICATION,
    StatutMission.EN_ACCOMPLISSEMENT: Phase.ACCOMPLISSEMENT,
    StatutMission.EN_COMMUNICATION: Phase.COMMUNICATION,
}

# Étapes à clore avant de démarrer une étape (enchaînement IFACI dans une phase). Les premières
# étapes d'une phase (XI, XV) sont gardées par le changement de phase ; XII et XIII se déroulent
# en parallèle après XI. Un jalon précédent doit être validé, pas seulement terminé.
PREDECESSEURS: dict[int, tuple[int, ...]] = {
    **{n: (n - 1,) for n in range(2, 11)},
    11: (),
    12: (11,),
    13: (11,),
    14: (12, 13),
    15: (),
    **{n: (n - 1,) for n in range(16, 19)},
}

ETAPES_DE_PHASE: dict[Phase, range] = {
    Phase.PLANIFICATION: range(1, 11),
    Phase.ACCOMPLISSEMENT: range(11, 15),
    Phase.COMMUNICATION: range(15, 19),
}

JALON_DE_PHASE: dict[Phase, int] = {Phase.PLANIFICATION: 10, Phase.ACCOMPLISSEMENT: 13}

ETAPE_DE_REUNION: dict[str, int] = {
    TypeReunion.OUVERTURE: 2,
    TypeReunion.LANCEMENT: 11,
    TypeReunion.CLOTURE: 15,
}


def etape(numero: int) -> DefinitionEtape:
    return _PAR_NUMERO[numero]


def romain(numero: int) -> str:
    return _PAR_NUMERO[numero].romain
