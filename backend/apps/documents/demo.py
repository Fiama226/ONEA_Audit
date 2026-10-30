"""Documents de démonstration : gabarits provisoires puis versions générées par les services.

Aucune file de tâches n'est requise : la génération Word est exécutée en ligne. La conversion
PDF (Gotenberg) n'est tentée qu'avec `--avec-pdf` ; sinon elle est marquée en échec
explicite (« relancer le PDF » reste possible depuis l'interface), jamais laissée en attente.
Les versions supplémentaires viennent d'une modification réelle de la mission (date de fin
prévue repoussée d'un jour), qui change le contexte du document.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Any
from unittest import mock

from apps.core.audit import actor_scope
from apps.core.demo import ContexteDemo
from apps.core.exceptions import RegleMetierError
from apps.missions.demo import SuiviMission
from apps.missions.models import TypeReunion
from apps.missions.services.missions import modifier_mission

from . import tasks
from .exceptions import ContratNonRespecteError
from .models import DocumentVersion, GabaritDocument, StatutGabarit, StatutGeneration
from .moteur.provisoires import construire_gabarit_provisoire
from .moteur.registre import types_documents
from .services.gabarits import activer_gabarit, deposer_gabarit
from .services.generation import (
    demander_generation,
    executer_conversion,
    executer_generation,
    marquer_echec_pdf,
)

MAX_TOURS = 40


@contextmanager
def _sans_file_de_taches() -> Iterator[None]:
    """Neutralise l'envoi à Celery : le peuplement exécute lui-même les traitements."""
    with (
        mock.patch.object(tasks.generer_version, "delay", lambda *a, **k: None),
        mock.patch.object(tasks.convertir_pdf, "delay", lambda *a, **k: None),
    ):
        yield


def _installer_gabarits(ctx: ContexteDemo) -> None:
    actifs = set(
        GabaritDocument.objects.filter(statut=StatutGabarit.ACTIF).values_list(
            "type_document", flat=True
        )
    )
    for t in types_documents():
        if t.code in actifs:
            continue
        gabarit = deposer_gabarit(
            type_document=t.code,
            contenu=construire_gabarit_provisoire(t),
            nom_original=f"gabarit-provisoire-{t.code.lower()}.docx",
            by=ctx.acteur,
            commentaire="Gabarit provisoire de démonstration.",
            provisoire=True,
        )
        activer_gabarit(gabarit, by=ctx.acteur)


def _pdf(ctx: ContexteDemo, version_id: str) -> None:
    if ctx.avec_pdf:
        try:
            executer_conversion(version_id)
        except Exception as exc:  # noqa: BLE001 - Gotenberg indisponible : échec explicite
            marquer_echec_pdf(version_id, str(exc).rstrip("."))
    else:
        marquer_echec_pdf(version_id, "conversion non demandée pour les données de démonstration")


def _generer(ctx: ContexteDemo, type_document: str, objet_id: Any) -> bool:
    rai = ctx.rai
    try:
        with actor_scope(rai):
            version = demander_generation(type_document=type_document, objet_id=objet_id, by=rai)
            executer_generation(str(version.pk))
            _pdf(ctx, str(version.pk))
    except (RegleMetierError, ContratNonRespecteError):
        return False
    return True


def _cibles(ctx: ContexteDemo) -> list[tuple[SuiviMission, str, Any, bool]]:
    """(suivi, type, objet, versionnable) pour chaque document possible."""
    from apps.analyse.contextes import CodeDocumentAnalyse

    cibles: list[tuple[SuiviMission, str, Any, bool]] = []
    for s in ctx.etat["suivis"]:
        if s.etape >= 2:
            cibles.append((s, "ORDRE_MISSION", s.mission.pk, False))  # contexte figé
        if s.reunion is not None and s.reunion.type == TypeReunion.OUVERTURE:
            cibles.append((s, "PV_OUVERTURE", s.reunion.pk, True))
        if s.etape >= 3:
            cibles += [(s, code.value, s.mission.pk, True) for code in CodeDocumentAnalyse]
    return cibles


def _nombre() -> int:
    return DocumentVersion.objects.filter(statut=StatutGeneration.PRETE).count()


def peupler(ctx: ContexteDemo) -> None:
    _installer_gabarits(ctx)
    cible = ctx.volumes.versions
    cibles = _cibles(ctx)
    with _sans_file_de_taches():
        for tour in range(MAX_TOURS):
            avant = _nombre()
            if tour:
                mutes: set[Any] = set()
                for s, *_ in cibles:
                    if s.mission.pk not in mutes:
                        mutes.add(s.mission.pk)
                        s.mission.refresh_from_db()
                        modifier_mission(
                            s.mission,
                            by=ctx.rai,
                            date_fin_prevue=(s.mission.date_fin_prevue or date(2026, 12, 31))
                            + timedelta(days=1),
                        )
            for _s, type_document, objet_id, versionnable in cibles:
                if _nombre() >= cible:
                    break
                if tour and not versionnable:
                    continue
                _generer(ctx, type_document, objet_id)
            if _nombre() >= cible or _nombre() == avant:
                break
    if _nombre() < cible:
        ctx.avertir(f"{_nombre()} version(s) de document générée(s) sur {cible} visées.")
