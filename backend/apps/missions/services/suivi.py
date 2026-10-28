"""Fiche de suivi de la mission (D12) : lecture seule, deux requêtes."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.utils import timezone

from ..models import EtapeMission, EvenementEtape, Mission, StatutEtape

_SANS_ECART = frozenset({StatutEtape.A_FAIRE, StatutEtape.NON_APPLICABLE})


@dataclass
class LigneSuivi:
    numero: int
    romain: str
    titre: str
    phase: str
    jalon: bool
    statut: str
    debut_prevu: date | None
    fin_prevue: date | None
    debut_reel: date | None
    fin_reelle: date | None
    ecart_jours: int | None
    charge_prevue: Decimal | None
    charge_reelle: Decimal | None


@dataclass
class FicheSuivi:
    mission: Mission
    budget_jours: Decimal
    total_prevu: Decimal
    total_reel: Decimal
    lignes: list[LigneSuivi]
    evenements: list[EvenementEtape]


def _ecart(etape: EtapeMission, aujourd_hui: date) -> int | None:
    """Positif = retard (fin réelle, ou aujourd'hui si l'étape est ouverte, moins fin prévue)."""
    if etape.date_fin_prevue is None or etape.statut in _SANS_ECART:
        return None
    fin = etape.date_fin_reelle or aujourd_hui
    return (fin - etape.date_fin_prevue).days


def fiche_de_suivi(mission: Mission, *, aujourd_hui: date | None = None) -> FicheSuivi:
    jour = aujourd_hui or timezone.localdate()
    etapes = list(EtapeMission.objects.filter(mission=mission).order_by("numero"))
    evenements = list(
        EvenementEtape.objects.filter(etape__mission=mission)
        .select_related("etape", "par")
        .order_by("le", "created_at")
    )
    lignes: list[LigneSuivi] = []
    for e in etapes:
        d = e.definition
        lignes.append(
            LigneSuivi(
                numero=e.numero,
                romain=d.romain,
                titre=d.titre,
                phase=d.phase.value,
                jalon=d.jalon,
                statut=e.statut,
                debut_prevu=e.date_debut_prevue,
                fin_prevue=e.date_fin_prevue,
                debut_reel=e.date_debut_reelle,
                fin_reelle=e.date_fin_reelle,
                ecart_jours=_ecart(e, jour),
                charge_prevue=e.charge_prevue_jours,
                charge_reelle=e.charge_reelle_jours,
            )
        )
    return FicheSuivi(
        mission=mission,
        budget_jours=mission.budget_jours,
        total_prevu=sum((x.charge_prevue or Decimal(0) for x in lignes), Decimal(0)),
        total_reel=sum((x.charge_reelle or Decimal(0) for x in lignes), Decimal(0)),
        lignes=lignes,
        evenements=evenements,
    )
