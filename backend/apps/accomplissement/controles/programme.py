"""Contrôles de livrables des étapes VIII, IX et X (D12).

Chaque contrôle de VIII et IX renvoie un message par élément en défaut.
"""

from apps.analyse.services.objectifs import code_objectif, objectifs_retenus
from apps.missions.gardes import STATUTS_ETAPE_CLOSE
from apps.missions.models import EtapeMission
from apps.missions.services.livrables import Controle

from ..models import ProgrammeDeTravail, StatutTest, TestPrevu

MSG_X = "Terminez les étapes VIII et IX avant de soumettre l'organisation de la mission."


def _tests_prevus(etape: EtapeMission) -> list[TestPrevu]:
    tests = TestPrevu.objects.filter(mission_id=etape.mission_id, statut=StatutTest.PREVU)
    return list(tests.order_by("numero"))


def _programmes_et_tests(etape: EtapeMission) -> list[str]:
    objectifs = list(objectifs_retenus(etape.mission_id))
    avec_programme = set(
        ProgrammeDeTravail.objects.filter(mission_id=etape.mission_id).values_list(
            "objectif_id", flat=True
        )
    )
    tests = _tests_prevus(etape)
    avec_tests = {t.programme.objectif_id for t in tests}
    messages = [
        f"Aucun programme de travail pour l'objectif {code_objectif(o)}."
        for o in objectifs
        if o.pk not in avec_programme
    ]
    messages += [
        f"Aucun test n'est prévu pour l'objectif {code_objectif(o)}."
        for o in objectifs
        if o.pk in avec_programme and o.pk not in avec_tests
    ]
    messages += [
        f"Le test {t.code} n'a pas de procédure." for t in tests if not t.procedure.strip()
    ]
    return messages


def _ressources(etape: EtapeMission) -> list[str]:
    messages: list[str] = []
    for t in _tests_prevus(etape):
        if t.auditeur_id is None:
            messages.append(f"Le test {t.code} n'a pas d'auditeur.")
        if t.charge_prevue_jours is None or t.charge_prevue_jours <= 0:
            messages.append(f"Le test {t.code} n'a pas de charge prévue.")
    return messages


def _viii_ix_terminees(etape: EtapeMission) -> str | None:
    statuts = dict(
        EtapeMission.objects.filter(mission_id=etape.mission_id, numero__in=(8, 9)).values_list(
            "numero", "statut"
        )
    )
    return None if all(statuts.get(n) in STATUTS_ETAPE_CLOSE for n in (8, 9)) else MSG_X


CONTROLES_ETAPE: dict[int, list[Controle]] = {
    8: [_programmes_et_tests],
    9: [_ressources],
    10: [_viii_ix_terminees],
}
