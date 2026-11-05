from collections.abc import Iterable
from typing import Any, cast

from django.apps import AppConfig


class MissionsConfig(AppConfig):
    name = "apps.missions"
    label = "missions"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.core.audit import register

        from .models import (
            AffectationMission,
            DeclarationIndependance,
            Entretien,
            EtapeMission,
            EvenementEtape,
            Mission,
            Reunion,
            RisqueMission,
        )

        register(Mission, m2m_fields={"processus", "entites", "risques_couverts"})
        register(AffectationMission)
        register(DeclarationIndependance)
        register(EtapeMission)
        register(EvenementEtape)
        register(Reunion, m2m_fields={"participants"})
        register(Entretien, m2m_fields={"auditeurs", "interlocuteurs"})
        register(RisqueMission)

        _connecter_gardes_m2m()


_ACTIONS_GARDEES = {"pre_add", "pre_remove", "pre_clear"}


def _connecter_gardes_m2m() -> None:
    """Gèle les M2M comme les champs : mission figée, étape I (D17), étape de la réunion /
    de l'entretien close."""
    from django.db.models.signals import m2m_changed

    from . import gardes
    from .models import Entretien, Mission, Reunion

    def garde_mission(
        sender: type,
        instance: object,
        action: str,
        reverse: bool,
        pk_set: set[Any] | None,
        **_: object,
    ) -> None:
        if action not in _ACTIONS_GARDEES:
            return
        if reverse:
            # Ex. processus.missions.add(...) : `instance` est le processus.
            cibles: Iterable[Mission] = (
                Mission.all_objects.filter(pk__in=pk_set)
                if pk_set
                else sender_missions(instance, sender)
            )
        else:
            cibles = [cast(Mission, instance)]
        for mission in cibles:
            gardes.controler_m2m_mission(mission, d17=True)

    def sender_missions(instance: object, sender: type) -> list[Mission]:
        champ = {
            Mission.processus.through: "processus",
            Mission.entites.through: "entites",
            Mission.risques_couverts.through: "risques_couverts",
        }[sender]
        return list(Mission.all_objects.filter(**{champ: instance}))

    def garde_enfant(
        sender: type, instance: object, action: str, reverse: bool, **_: object
    ) -> None:
        if action in _ACTIONS_GARDEES and not reverse:
            gardes.controler_ecriture(instance)

    de_mission: tuple[Any, ...] = (
        Mission.processus.through,
        Mission.entites.through,
        Mission.risques_couverts.through,
    )
    d_enfants: tuple[Any, ...] = (
        Reunion.participants.through,
        Entretien.auditeurs.through,
        Entretien.interlocuteurs.through,
    )
    for through in de_mission:
        m2m_changed.connect(garde_mission, sender=through, weak=False)
    for through in d_enfants:
        m2m_changed.connect(garde_enfant, sender=through, weak=False)
