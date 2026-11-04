"""Synchronisation de l'index : post_save -> on_commit -> tâche ; réconciliation ; commande."""

from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.constats.models import Constat, Recommandation, StatutConstat
from apps.documents.models import StatutGeneration
from apps.missions.models import Mission
from apps.recherche import tasks
from apps.recherche.exceptions import RechercheIndisponibleError
from apps.recherche.services import reconcilier_index
from apps.users.models import User
from tests.constats.factories import ConstatFactory


def test_sauvegarde_indexe_apres_commit(
    mission_lancee: Mission, index: Any, django_capture_on_commit_callbacks: Any
) -> None:
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        constat = ConstatFactory(mission=mission_lancee)
    assert f"CONSTAT-{constat.pk}" not in index.documents  # rien avant le commit
    for callback in callbacks:
        callback()
    assert f"CONSTAT-{constat.pk}" in index.documents
    reco = Recommandation.objects.get(constat=constat)
    assert f"RECOMMANDATION-{reco.pk}" in index.documents


def test_suppression_logique_retire_de_l_index(
    mission_lancee: Mission, index: Any, rai: User, django_capture_on_commit_callbacks: Any
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        constat = ConstatFactory(mission=mission_lancee)
    assert f"CONSTAT-{constat.pk}" in index.documents
    with django_capture_on_commit_callbacks(execute=True):
        constat.soft_delete(rai)
    assert f"CONSTAT-{constat.pk}" not in index.documents
    # Les recommandations du constat supprimé sont retirées avec lui.
    reco = Recommandation.objects.get(constat=constat)
    assert f"RECOMMANDATION-{reco.pk}" not in index.documents


def test_soumission_constat_ouvre_l_audience_audite(
    mission_lancee: Mission, index: Any, django_capture_on_commit_callbacks: Any
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        constat = ConstatFactory(mission=mission_lancee)
    reco = Recommandation.objects.get(constat=constat)
    assert index.documents[f"CONSTAT-{constat.pk}"]["audience"] == ["EQUIPE"]
    assert index.documents[f"RECOMMANDATION-{reco.pk}"]["audience"] == ["EQUIPE"]
    Constat.objects.filter(pk=constat.pk).update(statut=StatutConstat.SOUMIS)
    constat.refresh_from_db()
    with django_capture_on_commit_callbacks(execute=True):
        constat.save()
    assert "AUDITE" in index.documents[f"CONSTAT-{constat.pk}"]["audience"]
    assert "AUDITE" in index.documents[f"RECOMMANDATION-{reco.pk}"]["audience"]


def test_version_prete_indexe_le_document(
    mission_lancee: Mission,
    index: Any,
    creer_document: Any,
    django_capture_on_commit_callbacks: Any,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        document = creer_document(
            mission_lancee, "ORDRE_MISSION", mission_lancee, version=StatutGeneration.EN_ATTENTE
        )
    assert f"DOCUMENT-{document.pk}" not in index.documents
    version = document.versions.get()
    version.statut = StatutGeneration.PRETE
    with django_capture_on_commit_callbacks(execute=True):
        version.save()
    assert f"DOCUMENT-{document.pk}" in index.documents
    assert "CONFIDENTIEL-CONTEXTE-JSON" not in str(index.documents[f"DOCUMENT-{document.pk}"])


def test_moteur_indisponible_ecriture_metier_ok(
    mission_lancee: Mission,
    monkeypatch: pytest.MonkeyPatch,
    django_capture_on_commit_callbacks: Any,
) -> None:
    appels: list[str] = []

    class Panne:
        def indexer(self, documents: list[dict[str, Any]]) -> None:
            appels.append("indexer")
            raise RechercheIndisponibleError

        def retirer(self, ids: list[str]) -> None:
            appels.append("retirer")
            raise RechercheIndisponibleError

    monkeypatch.setattr("apps.recherche.services.moteur", lambda: Panne())
    with django_capture_on_commit_callbacks(execute=True):
        constat = ConstatFactory(mission=mission_lancee)
    assert Constat.objects.filter(pk=constat.pk).exists()  # l'écriture métier a réussi
    assert len(appels) > 1  # la tâche a réessayé (max_retries=5)


def test_courtier_en_panne_ne_casse_pas_l_ecriture(
    mission_lancee: Mission,
    monkeypatch: pytest.MonkeyPatch,
    django_capture_on_commit_callbacks: Any,
) -> None:
    def casse(*a: Any, **k: Any) -> None:
        raise ConnectionError("courtier absent")

    monkeypatch.setattr(tasks.indexer_objet, "delay", casse)
    with django_capture_on_commit_callbacks(execute=True):
        constat = ConstatFactory(mission=mission_lancee)
    assert Constat.objects.filter(pk=constat.pk).exists()


def test_tache_idempotente_retire_un_objet_absent(index: Any, db: None) -> None:
    index.documents["CONSTAT-00000000-0000-0000-0000-000000000001"] = {"id": "x"}
    tasks.indexer_objet.apply(args=("CONSTAT", "00000000-0000-0000-0000-000000000001")).get()
    tasks.indexer_objet.apply(args=("CONSTAT", "00000000-0000-0000-0000-000000000001")).get()
    assert index.documents == {}
    tasks.indexer_objet.apply(args=("INCONNU", "n'importe quoi")).get()  # sans effet


def test_reconciliation_rattrape_les_ecritures_en_masse(
    mission_lancee: Mission, index: Any
) -> None:
    constat = ConstatFactory(mission=mission_lancee)
    index.documents["CONSTAT-fantome"] = {"id": "CONSTAT-fantome"}
    assert tasks.reconcilier.apply().get() >= 2
    assert f"CONSTAT-{constat.pk}" in index.documents
    assert "CONSTAT-fantome" not in index.documents
    assert f"MISSION-{mission_lancee.pk}" in index.documents


def test_reindexer_commande(mission_lancee: Mission, index: Any) -> None:
    constat = ConstatFactory(mission=mission_lancee)
    sortie = StringIO()
    call_command("reindexer", stdout=sortie)
    assert index.configure is True
    assert f"CONSTAT-{constat.pk}" in index.documents
    assert "indexé" in sortie.getvalue()
    index.vider()
    call_command("reindexer", "--type", "MISSION", stdout=StringIO())
    assert set(index.documents) == {f"MISSION-{mission_lancee.pk}"}


def test_reindexer_commande_moteur_indisponible(monkeypatch: pytest.MonkeyPatch) -> None:
    class Panne:
        def configurer(self) -> None:
            raise RechercheIndisponibleError

    monkeypatch.setattr("apps.recherche.management.commands.reindexer.moteur", lambda: Panne())
    with pytest.raises(CommandError):
        call_command("reindexer", stdout=StringIO())


def test_types_documents_audite_et_dg(settings: Any) -> None:
    assert set(settings.RECHERCHE_TYPES_DOCUMENTS_AUDITE) == {
        "ORDRE_MISSION",
        "PV_OUVERTURE",
        "PV_CLOTURE",
        "RAPPORT_FINAL",
    }
    # PLAN_ACTIONS est réservé à l'équipe (fournisseur de documents du lot 7) :
    # jamais indexé pour l'audité
    planification = settings.CELERY_BEAT_SCHEDULE["recherche-reconciliation"]
    assert planification["task"] == "recherche.reconcilier"
    assert (planification["schedule"].hour, planification["schedule"].minute) == ({2}, {0})


def test_reconcilier_index_type_inconnu() -> None:
    with pytest.raises(ValueError):
        reconcilier_index("INCONNU")
