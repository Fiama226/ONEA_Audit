"""Missions de démonstration, conduites par les services jusqu'à l'étape II incluse.

Le niveau visé de chaque mission est un scénario : brouillon, planifiée, ou étape en cours
(1 à 8). Les étapes III et suivantes relèvent de l'application d'analyse
(`apps.analyse.demo`), qui reprend les missions dont le niveau est au moins 3. Les étapes IX à
XVIII ne sont pas atteintes : leurs livrables sont gérés par les lots 6 à 8.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from apps.core.audit import actor_scope
from apps.core.demo import ContexteDemo
from apps.referentiel.models import Direction, Processus
from apps.users.models import User

from .models import (
    EvenementDeclencheur,
    Mission,
    RoleMission,
    TypeMission,
    TypeReunion,
)
from .services.declarations import arbitrer_conflit, confirmer_declaration
from .services.entretiens import creer_entretien, marquer_entretien_realise
from .services.equipe import affecter
from .services.etapes import demarrer_etape, terminer_etape
from .services.missions import (
    annuler_mission,
    creer_mission,
    emettre_ordre_mission,
    lancer_mission,
    planifier_mission,
    suspendre_mission,
)
from .services.reunions import creer_reunion, marquer_reunion_tenue

BROUILLON = "BROUILLON"
PLANIFIEE = "PLANIFIEE"
Niveau = int | str  # étape en cours (1 à 8) ou BROUILLON / PLANIFIEE

# (niveau, état final) ; les quatre premiers couvrent déjà les cas principaux (petite échelle).
SCENARIOS_VOLUMETRIE: tuple[tuple[Niveau, str | None], ...] = (
    (7, None), (BROUILLON, None), (3, None), (PLANIFIEE, None),
    (5, None), (8, None), (2, None), (3, "SUSPENDUE"),
    (6, None), (PLANIFIEE, "ANNULEE"), (4, None), (1, None),
    (BROUILLON, None), (PLANIFIEE, None), (1, None), (2, None),
    (3, None), (5, None), (7, None), (8, None),
)  # fmt: skip
SCENARIOS_FORMATION: tuple[tuple[Niveau, str | None], ...] = (
    (BROUILLON, None), (PLANIFIEE, None), (1, None), (4, None), (7, None), (8, None),
)  # fmt: skip

OBJETS = (
    "Audit du dispositif de contrôle de",
    "Évaluation de la conformité de",
    "Revue de la maîtrise des risques de",
    "Mission de conseil sur l'organisation de",
)
OBJECTIFS = (
    "Évaluer la conception et l'efficacité du dispositif de contrôle interne du domaine audité."
)
PERIMETRE = "Opérations de l'exercice 2025 des entités concernées, sur sites et en central."
FUSEAU_REUNIONS = UTC


@dataclass
class SuiviMission:
    """Mission créée et ce que le peuplement doit en faire."""

    rang: int
    niveau: Niveau
    final: str | None
    mission: Mission
    chef: User | None = None
    superviseur: User | None = None
    auditeurs: list[User] = field(default_factory=list)
    audites: list[User] = field(default_factory=list)
    reunion: Any = None

    @property
    def etape(self) -> int:
        return self.niveau if isinstance(self.niveau, int) else 0

    @property
    def intervenants(self) -> list[User]:
        tous = [self.chef, self.superviseur, *self.auditeurs]
        return [u for u in tous if u is not None]

    @property
    def redacteur(self) -> User:
        return self.auditeurs[0] if self.auditeurs else self.chef  # type: ignore[return-value]


def _tracer[T](par: User, fonction: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Appelle un service en consignant `par` comme acteur, y compris pour ses M2M."""
    with actor_scope(par):
        return fonction(*args, **kwargs)


def _creer(ctx: ContexteDemo, rang: int, niveau: Niveau, final: str | None) -> SuiviMission:
    rng, rai = ctx.rng, ctx.rai
    processus: list[Processus] = rng.sample(
        ctx.etat["processus"], k=min(len(ctx.etat["processus"]), rng.choice((1, 1, 2)))
    )
    entites: list[Direction] = rng.sample(ctx.etat["directions"][1:] or ctx.etat["directions"], k=1)
    prefixe = "Formation — " if ctx.profil == "formation" else ""
    debut = date(2026, 1, 5) + timedelta(days=(rang * 9) % 270)
    mission = _tracer(
        rai,
        creer_mission,
        titre=f"{prefixe}{rng.choice(OBJETS)} {processus[0].libelle.lower()}"[:300],
        type=TypeMission.CONSEIL if rang % 9 == 8 else TypeMission.ASSURANCE,
        by=rai,
        processus=processus,
        entites=entites,
        evenement_declencheur=EvenementDeclencheur.PROGRAMME_ANNUEL,
        periode_debut=date(2025, 1, 1),
        periode_fin=date(2025, 12, 31),
        date_debut_prevue=debut,
        date_fin_prevue=debut + timedelta(days=60),
        budget_jours=rng.randint(20, 80),
        objectifs=OBJECTIFS,
        perimetre=PERIMETRE,
        clients="Direction générale et responsables des entités auditées.",
        livrables_attendus="Rapport d'audit et plan d'actions.",
    )
    return SuiviMission(rang=rang, niveau=niveau, final=final, mission=mission)


def _constituer_equipe(ctx: ContexteDemo, s: SuiviMission) -> None:
    pool = ctx.rng.sample(ctx.groupes["auditeurs"], k=min(4, len(ctx.groupes["auditeurs"])))
    s.chef = pool[0]
    reste = pool[1:]
    if len(reste) >= 2:
        s.superviseur, reste = reste[0], reste[1:]
    s.auditeurs = reste
    s.audites = ctx.rng.sample(ctx.groupes["audites"], k=min(2, len(ctx.groupes["audites"])))
    rai = ctx.rai
    affecter(s.mission, utilisateur=s.chef, role_mission=RoleMission.CHEF_MISSION, by=rai)
    if s.superviseur:
        affecter(s.mission, utilisateur=s.superviseur, role_mission=RoleMission.SUPERVISEUR, by=rai)
    for u in s.auditeurs:
        affecter(s.mission, utilisateur=u, role_mission=RoleMission.AUDITEUR, by=rai)
    for u in s.audites:
        affecter(s.mission, utilisateur=u, role_mission=RoleMission.AUDITE, by=rai)


def _confirmer(ctx: ContexteDemo, s: SuiviMission, *, tous: bool) -> None:
    equipe = s.intervenants if tous else s.intervenants[:1]  # le chef d'abord
    for u in equipe:
        affectation = s.mission.affectations.get(utilisateur=u)
        declaration = affectation.declaration
        # Une mission sur cinq : un auditeur signale une situation, arbitrée par le RAI.
        conflit = tous and bool(s.auditeurs) and u is s.auditeurs[0] and s.rang % 5 == 4
        confirmer_declaration(
            declaration,
            by=u,
            conflit=conflit,
            description_conflit="Ancien responsable d'un service de l'entité auditée."
            if conflit
            else "",
        )
        if conflit:
            declaration.refresh_from_db()
            arbitrer_conflit(
                declaration,
                justification="Situation ancienne, sans lien avec le périmètre : maintenu.",
                by=ctx.rai,
            )


def _etape_ii(ctx: ContexteDemo, s: SuiviMission) -> None:
    """Réunion d'ouverture tenue, entretien planifié ; étape II terminée si le niveau > 2."""
    rai, chef = ctx.rai, s.chef
    if chef is None:
        raise RuntimeError("Mission sans chef.")
    demarrer_etape(s.mission.etapes.get(numero=2), by=rai)
    quand = datetime(2026, 1, 12, 9, 0, tzinfo=FUSEAU_REUNIONS) + timedelta(days=s.rang)
    s.reunion = _tracer(
        chef,
        creer_reunion,
        s.mission,
        type=TypeReunion.OUVERTURE,
        date=quand,
        by=chef,
        participants=[*s.intervenants, *s.audites],
        lieu="Salle de réunion de la direction",
        ordre_du_jour="Objectifs, périmètre, calendrier et modalités de la mission.",
        compte_rendu="Les objectifs et le calendrier ont été présentés et validés.",
        decisions="Premiers entretiens planifiés.",
    )
    marquer_reunion_tenue(s.reunion, by=chef)
    entretien = _tracer(
        chef,
        creer_entretien,
        s.mission,
        objet="Prise de connaissance du domaine audité",
        date_prevue=quand + timedelta(days=3),
        by=chef,
        auditeurs=s.intervenants[:2],
        interlocuteurs=s.audites,
        compte_rendu="Présentation de l'organisation et des principales procédures.",
        duree_minutes=90,
    )
    if s.etape >= 3:
        marquer_entretien_realise(entretien, by=chef)
        terminer_etape(s.mission.etapes.get(numero=2), by=chef)


def _conduire(ctx: ContexteDemo, s: SuiviMission) -> None:
    if s.niveau == BROUILLON:
        return
    planifier_mission(s.mission, by=ctx.rai)
    _constituer_equipe(ctx, s)
    if s.niveau == PLANIFIEE:
        return
    lancer_mission(s.mission, by=ctx.rai)
    _confirmer(ctx, s, tous=s.etape >= 2)
    if s.etape == 1:
        return
    emettre_ordre_mission(s.mission, by=ctx.rai)
    _etape_ii(ctx, s)


def _finaliser(ctx: ContexteDemo) -> None:
    """États finals (suspension, annulation), après les documents : la mission est figée."""
    for s in ctx.etat["suivis"]:
        s.mission.refresh_from_db()
        if s.final == "SUSPENDUE":
            suspendre_mission(
                s.mission, motif="Suspension pour indisponibilité des audités.", by=ctx.rai
            )
        elif s.final == "ANNULEE":
            annuler_mission(
                s.mission, motif="Mission annulée : reportée à l'an prochain.", by=ctx.rai
            )


def peupler(ctx: ContexteDemo) -> None:
    scenarios = SCENARIOS_FORMATION if ctx.profil == "formation" else SCENARIOS_VOLUMETRIE
    suivis: list[SuiviMission] = []
    for rang in range(ctx.volumes.missions):
        niveau, final = scenarios[rang % len(scenarios)]
        s = _creer(ctx, rang, niveau, final)
        _conduire(ctx, s)
        suivis.append(s)
    ctx.etat["suivis"] = suivis
    ctx.finaliseurs.append(lambda: _finaliser(ctx))
