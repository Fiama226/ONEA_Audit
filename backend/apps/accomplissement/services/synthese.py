"""Synthèse du programme : charges par objectif et par auditeur, budget (étape IX, D12)."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID

from apps.analyse.services.objectifs import code_objectif, objectifs_retenus
from apps.missions.models import Mission
from apps.users.models import User

from ..models import StatutTest, TestPrevu

ZERO = Decimal(0)


@dataclass
class LigneObjectif:
    code: str
    libelle: str
    nb_tests: int = 0
    charge: Decimal = ZERO


@dataclass
class LigneAuditeur:
    utilisateur: User
    nb_tests: int = 0
    charge: Decimal = ZERO


@dataclass
class SyntheseProgramme:
    objectifs: list[LigneObjectif] = field(default_factory=list)
    auditeurs: list[LigneAuditeur] = field(default_factory=list)
    total_charge: Decimal = ZERO
    budget_jours: Decimal = ZERO
    depassement_budget: bool = False
    tests_sans_auditeur: list[str] = field(default_factory=list)

    def en_dict(self) -> dict[str, Any]:
        """Forme sérialisable (instantané figé, D14)."""
        return {
            "objectifs": [
                {"code": o.code, "libelle": o.libelle, "nb_tests": o.nb_tests, "charge": o.charge}
                for o in self.objectifs
            ],
            "auditeurs": [
                {
                    "utilisateur_id": str(a.utilisateur.pk),
                    "nom": a.utilisateur.get_full_name() or a.utilisateur.username,
                    "nb_tests": a.nb_tests,
                    "charge": a.charge,
                }
                for a in self.auditeurs
            ],
            "total_charge": self.total_charge,
            "budget_jours": self.budget_jours,
            "depassement_budget": self.depassement_budget,
            "tests_sans_auditeur": self.tests_sans_auditeur,
        }


def synthese_programme(mission: Mission) -> SyntheseProgramme:
    """Trois requêtes : objectifs retenus, tests prévus (non abandonnés), auditeurs."""
    objectifs: dict[UUID, LigneObjectif] = {
        o.pk: LigneObjectif(code_objectif(o), o.libelle)
        for o in objectifs_retenus(mission).only("pk", "numero", "libelle")
    }
    tests = (
        TestPrevu.objects.filter(mission=mission, statut=StatutTest.PREVU)
        .order_by("numero")
        .values_list("code", "programme__objectif_id", "auditeur_id", "charge_prevue_jours")
    )
    donnees = list(tests)
    utilisateurs = {
        u.pk: u for u in User.objects.filter(pk__in={a for _, _, a, _ in donnees if a is not None})
    }
    synthese = SyntheseProgramme(budget_jours=mission.budget_jours)
    par_auditeur: dict[UUID, LigneAuditeur] = {}
    for code, objectif_id, auditeur_id, charge in donnees:
        charge = charge or ZERO
        synthese.total_charge += charge
        ligne = objectifs.get(objectif_id)
        if ligne is not None:
            ligne.nb_tests += 1
            ligne.charge += charge
        if auditeur_id is None:
            synthese.tests_sans_auditeur.append(code)
            continue
        a = par_auditeur.setdefault(auditeur_id, LigneAuditeur(utilisateurs[auditeur_id]))
        a.nb_tests += 1
        a.charge += charge
    synthese.objectifs = list(objectifs.values())
    synthese.auditeurs = sorted(
        par_auditeur.values(), key=lambda a: a.utilisateur.get_full_name() or a.utilisateur.username
    )
    synthese.depassement_budget = synthese.total_charge > synthese.budget_jours
    return synthese
