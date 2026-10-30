"""Instantané immuable du programme validé (étape X, D14)."""

import json
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from apps.analyse.services.objectifs import code_objectif
from apps.core.services import enregistrer
from apps.missions.gardes import verrouiller_mission
from apps.missions.models import EtapeMission, Mission
from apps.signatures.services import empreinte
from apps.users.models import User

from ..models import InstantaneProgramme, ProgrammeDeTravail, TestPrevu
from .synthese import synthese_programme

TYPE_EMPREINTE = "programme"


def _tests(mission: Mission) -> list[dict[str, Any]]:
    tests = TestPrevu.objects.filter(mission=mission).select_related("programme__objectif")
    return [
        {
            "code": t.code,
            "objectif": code_objectif(t.programme.objectif),
            "libelle": t.libelle,
            "objectif_test": t.objectif_test,
            "nature": t.nature,
            "procedure": t.procedure,
            "population": t.population,
            "taille_echantillon": t.taille_echantillon,
            "methode_selection": t.methode_selection,
            "auditeur_id": str(t.auditeur_id) if t.auditeur_id else None,
            "charge_prevue_jours": t.charge_prevue_jours,
            "date_debut_prevue": t.date_debut_prevue,
            "date_fin_prevue": t.date_fin_prevue,
            "risque_mission_id": str(t.risque_mission_id) if t.risque_mission_id else None,
            "complementaire": t.complementaire,
            "statut": t.statut,
            "motif_abandon": t.motif_abandon,
        }
        for t in tests.order_by("numero")
    ]


def _programmes(mission: Mission) -> list[dict[str, Any]]:
    programmes = ProgrammeDeTravail.objects.filter(mission=mission).select_related("objectif")
    return [
        {
            "objectif": code_objectif(p.objectif),
            "objectif_libelle": p.objectif.libelle,
            "techniques": p.techniques,
            "criteres_preuve": p.criteres_preuve,
            "commentaire": p.commentaire,
        }
        for p in programmes.order_by("objectif__numero")
    ]


def donnees_programme(mission: Mission) -> dict[str, Any]:
    """Données canoniques (après aller-retour JSON, identiques à ce que la base conservera)."""
    brut = {
        "synthese": synthese_programme(mission).en_dict(),
        "programmes": _programmes(mission),
        "tests": _tests(mission),
    }
    donnees: dict[str, Any] = json.loads(json.dumps(brut, cls=DjangoJSONEncoder))
    return donnees


@transaction.atomic
def creer_instantane(etape_x: EtapeMission, *, by: User) -> InstantaneProgramme:
    """Fige le programme à la validation de X ; à appeler dans la transaction de la validation."""
    mission = verrouiller_mission(etape_x.mission_id)
    donnees = donnees_programme(mission)
    instantane = InstantaneProgramme(
        mission=mission,
        etape=etape_x,
        donnees=donnees,
        empreinte=empreinte(TYPE_EMPREINTE, donnees),
        valide_par=by,
        valide_le=etape_x.validee_le or timezone.now(),
    )
    enregistrer(instantane, by=by, creation=True)
    return instantane
