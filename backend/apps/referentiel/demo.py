"""Référentiel de démonstration : entités, processus, objets auditables, cartographies."""

from apps.core.demo import ContexteDemo

from .models import (
    Direction,
    FamilleProcessus,
    NatureObjet,
    ObjetAuditable,
    Processus,
    TypeEntite,
)
from .services import (
    creer_direction,
    creer_objet,
    creer_processus,
    creer_risque,
    creer_version,
    valider_version,
)

DIRECTIONS = (
    ("DAI", "Direction de l'audit interne"),
    ("DAF", "Direction administrative et financière"),
    ("DRH", "Direction des ressources humaines"),
    ("DEX", "Direction de l'exploitation"),
    ("DTE", "Direction technique"),
    ("DCO", "Direction commerciale"),
    ("DSI", "Direction des systèmes d'information"),
    ("DAP", "Direction de l'approvisionnement"),
)
DEPARTEMENTS = (
    "Comptabilité", "Budget et contrôle de gestion", "Trésorerie", "Paie et carrières",
    "Formation", "Production", "Qualité de l'eau", "Distribution", "Études et travaux",
    "Maintenance", "Facturation", "Recouvrement", "Relation clientèle", "Réseaux et sécurité",
    "Applications", "Achats", "Marchés publics", "Stocks", "Transport", "Patrimoine",
    "Assainissement", "Laboratoire",
)  # fmt: skip
PROCESSUS = (
    ("PIL", "Pilotage stratégique", FamilleProcessus.PILOTAGE),
    ("ACH", "Achats et marchés", FamilleProcessus.SUPPORT),
    ("FIN", "Gestion financière", FamilleProcessus.SUPPORT),
    ("RHU", "Gestion des ressources humaines", FamilleProcessus.SUPPORT),
    ("PRO", "Production d'eau potable", FamilleProcessus.REALISATION),
    ("DIS", "Distribution de l'eau", FamilleProcessus.REALISATION),
    ("COM", "Gestion commerciale", FamilleProcessus.REALISATION),
    ("ASS", "Assainissement", FamilleProcessus.REALISATION),
    ("MAI", "Maintenance des installations", FamilleProcessus.SUPPORT),
    ("SIN", "Systèmes d'information", FamilleProcessus.SUPPORT),
    ("LOG", "Logistique et stocks", FamilleProcessus.SUPPORT),
)
RISQUES = (
    "Fractionnement des commandes pour éviter la mise en concurrence",
    "Absence de séparation des tâches sur les paiements",
    "Rapprochements bancaires non réalisés dans les délais",
    "Dépassement des délais de traitement des demandes",
    "Insuffisance de la traçabilité des opérations",
    "Accès non autorisé aux applications sensibles",
    "Inventaires physiques non rapprochés de la comptabilité",
    "Entretien préventif non réalisé selon le calendrier",
    "Facturation erronée ou non émise",
    "Non-conformité à la réglementation applicable",
)
DOMAINES = ("Organisation et procédures", "Suivi et reporting")
OPERATIONS = ("Autorisation des opérations", "Enregistrement et contrôle")
ANNEES = (2024, 2025, 2026)


def peupler(ctx: ContexteDemo) -> None:
    v, rai, rng = ctx.volumes, ctx.rai, ctx.rng

    directions: list[Direction] = []
    for code, libelle in DIRECTIONS[: v.directions]:
        directions.append(
            creer_direction(code=code, libelle=libelle, type=TypeEntite.DIRECTION, by=rai)
        )
    nb_departements = v.entites - len(directions)
    departements: list[Direction] = []
    for k in range(nb_departements):
        parent = directions[k % len(directions)]
        nom = DEPARTEMENTS[k % len(DEPARTEMENTS)]
        departements.append(
            creer_direction(
                code=f"{parent.code}{k // len(directions) + 1:02d}",
                libelle=f"Département {nom.lower()}",
                type=TypeEntite.DEPARTEMENT,
                parent=parent,
                by=rai,
            )
        )
    ctx.etat["directions"] = directions
    ctx.etat["entites"] = directions + departements

    processus: list[Processus] = []
    for ordre, (code, libelle, famille) in enumerate(PROCESSUS[: v.processus]):
        processus.append(
            creer_processus(
                code=code,
                libelle=libelle,
                famille=famille,
                ordre=ordre,
                directions=rng.sample(directions, k=min(len(directions), rng.choice((1, 2)))),
                by=rai,
            )
        )
    ctx.etat["processus"] = processus

    objets: dict[str, list[ObjetAuditable]] = {}
    for p in processus:
        objets[p.code] = []
        for i, domaine in enumerate(DOMAINES):
            d = creer_objet(
                processus=p, nature=NatureObjet.DOMAINE, libelle=domaine, ordre=i, by=rai
            )
            op = creer_objet(
                processus=p,
                nature=NatureObjet.OPERATION,
                libelle=OPERATIONS[i],
                parent=d,
                ordre=i,
                by=rai,
            )
            objets[p.code].extend([d, op])

    for rang in range(v.cartographies):
        annee = ANNEES[rang]
        version = creer_version(
            annee=annee, libelle=f"Cartographie des risques {annee} (démonstration)", by=rai
        )
        for i in range(v.risques_par_cartographie):
            p = processus[i % len(processus)]
            creer_risque(
                version=version,
                processus=p,
                libelle=f"{RISQUES[(i + rang) % len(RISQUES)]} — {p.libelle.lower()}",
                probabilite=rng.randint(1, 5),
                impact=rng.randint(1, 5),
                objet_auditable=rng.choice(objets[p.code]) if i % 3 == 0 else None,
                description="Risque fictif créé pour la démonstration.",
                objectif_controle="Maîtriser le risque dans le périmètre du processus.",
                dispositif_controle="Revue périodique et double validation des opérations.",
                by=rai,
            )
        if rang < v.cartographies - 1:
            valider_version(version, by=rai)
