"""Commande `peupler_demo` : refus, volumes, déterminisme, exhaustivité et piste d'audit."""

import importlib
import re
from collections.abc import Callable
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from auditlog.models import LogEntry
from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import transaction

from apps.core import demo
from apps.documents.models import DocumentVersion, StatutGeneration
from apps.missions.models import EtapeMission, Mission, StatutEtape, StatutMission
from apps.programmation.models import LigneProgramme, ProgrammeAnnuel
from apps.referentiel.models import (
    CartographieVersion,
    Direction,
    Processus,
    Risque,
    StatutCartographie,
)
from apps.users.demo import COMPTES_TEST
from apps.users.models import FichierMotsDePasse, Role, User
from config.documents_settings import configuration_stockage
from tests.factories import DirectionFactory

ECHELLE = "0.05"


@pytest.fixture(autouse=True)
def stockage_tmp(tmp_path: Path, settings: Any) -> None:
    settings.DOCUMENTS_ROOT = str(tmp_path)
    settings.STORAGES = {
        **settings.STORAGES,
        "documents": configuration_stockage(
            {"DOCUMENTS_STORAGE": "filesystem", "DOCUMENTS_ROOT": str(tmp_path)}
        ),
    }


def lancer(*args: str) -> str:
    sortie = StringIO()
    call_command("peupler_demo", *args, stdout=sortie)
    return sortie.getvalue()


def instantane() -> dict[str, list[Any]]:
    """Libellés de la base (sans identifiants ni dates) pour comparer deux exécutions."""
    return {
        "utilisateurs": sorted(User.objects.values_list("username", "first_name", "last_name")),
        "directions": sorted(Direction.objects.values_list("code", "libelle")),
        "processus": sorted(Processus.objects.values_list("code", "libelle")),
        "risques": sorted(Risque.objects.values_list("code", "libelle", "probabilite", "impact")),
        "programmes": sorted(LigneProgramme.objects.values_list("numero", "titre")),
        "missions": sorted(Mission.objects.values_list("reference", "titre", "statut")),
        "etapes": sorted(
            EtapeMission.objects.values_list("mission__reference", "numero", "statut")
        ),
    }


# --- Refus -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module", ["config.settings.prod", "config.settings.production", "autre.prod"]
)
def test_refuse_en_production(module: str, monkeypatch: pytest.MonkeyPatch, db: None) -> None:
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", module)
    with pytest.raises(CommandError, match=r"Interdit en production\."):
        lancer("--profil", "formation")
    assert not Direction.objects.exists()


def test_production_refusee_meme_avec_recette(monkeypatch: pytest.MonkeyPatch, db: None) -> None:
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "config.settings.prod")
    with pytest.raises(CommandError, match=r"Interdit en production\."):
        lancer("--profil", "formation", "--recette")


def test_recette_exige_l_option_explicite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "config.settings.recette")
    with pytest.raises(CommandError, match="--recette"):
        demo.verifier_environnement(recette=False)
    demo.verifier_environnement(recette=True)  # autorisé, sans exception


def test_module_inconnu_refuse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "config.settings.inconnu")
    with pytest.raises(CommandError):
        demo.verifier_environnement(recette=True)


def test_refuse_sur_base_non_vide(db: None) -> None:
    DirectionFactory()
    with pytest.raises(CommandError, match="objets métier"):
        lancer("--profil", "formation")
    assert not User.objects.filter(username="demo").exists()


def test_a_blanc_n_ecrit_rien(db: None) -> None:
    sortie = lancer("--profil", "volumetrie", "--echelle", ECHELLE, "--a-blanc")
    assert "à blanc" in sortie.lower()
    assert not User.objects.exists()
    assert not Direction.objects.exists()


# --- Volumes ---------------------------------------------------------------------------------


def test_volumes_proportionnels() -> None:
    v1 = demo.volumes("volumetrie", 1.0)
    assert (v1.utilisateurs, v1.processus, v1.entites) == (60, 11, 30)
    assert (v1.cartographies, v1.risques_par_cartographie) == (3, 150)
    assert (v1.programmes, v1.lignes_par_programme, v1.missions, v1.versions) == (3, 40, 60, 300)
    petit = demo.volumes("volumetrie", 0.05)
    assert petit.missions == 4  # plancher
    assert petit.utilisateurs < v1.utilisateurs
    assert demo.volumes("formation", 1.0).missions == 6


def test_volumes_echelle_invalide() -> None:
    with pytest.raises(CommandError):
        demo.volumes("volumetrie", 0)


@pytest.fixture
def base_peuplee(db: None, stockage_tmp: None) -> str:
    return lancer("--profil", "volumetrie", "--echelle", ECHELLE)


def test_peuplement_volumetrie_reduit(base_peuplee: str) -> None:
    v = demo.volumes("volumetrie", float(ECHELLE))
    assert User.objects.filter(is_active=True).count() + 1 >= v.utilisateurs  # + acteur « demo »
    assert (
        User.objects.filter(username__in=["rai", "auditeur1", "audite1", "dg", "admin"]).count()
        == 5
    )
    assert Processus.objects.count() == v.processus
    assert Direction.objects.count() == v.entites
    assert CartographieVersion.objects.count() == v.cartographies
    assert (
        CartographieVersion.objects.filter(statut=StatutCartographie.VALIDEE).count()
        == v.cartographies - 1
    )
    assert Risque.objects.count() == v.cartographies * v.risques_par_cartographie
    assert ProgrammeAnnuel.objects.count() == v.programmes
    assert LigneProgramme.objects.count() == v.programmes * v.lignes_par_programme
    assert Mission.objects.count() == v.missions
    statuts = set(Mission.objects.values_list("statut", flat=True))
    assert {StatutMission.BROUILLON, StatutMission.PLANIFIEE, StatutMission.EN_PLANIFICATION} <= (
        statuts
    )
    assert EtapeMission.objects.count() == 18 * v.missions
    versions = DocumentVersion.objects.filter(statut=StatutGeneration.PRETE)
    assert versions.count() == v.versions
    assert all(version.taille_docx for version in versions)
    # Données fictives uniquement.
    assert not User.objects.exclude(email="").exclude(email__endswith="@example.org").exists()


def test_six_demo_accounts_must_change_password(base_peuplee: str) -> None:
    affiches = dict(re.findall(r"^\s+(\S+) : (\S+)$", base_peuplee, flags=re.MULTILINE))
    assert set(affiches) == set(COMPTES_TEST)
    assert len(set(affiches.values())) == 6
    for identifiant in COMPTES_TEST:
        compte = User.objects.get(username=identifiant)
        assert compte.is_active and compte.doit_changer_mot_de_passe is True
        assert compte.mot_de_passe_expire_le is not None
        assert compte.check_password(affiches[identifiant])
    assert User.objects.get(username="admin").role == Role.ADMIN
    # The passwords are shown once: no stored copy is left behind.
    assert not FichierMotsDePasse.objects.exists()
    # The other demo accounts got a temporary password too, never displayed.
    autres = User.objects.filter(is_active=True).exclude(username__in=COMPTES_TEST)
    assert autres.exists()
    assert all(c.doit_changer_mot_de_passe for c in autres)


def test_une_mission_par_statut_atteignable_au_complet(base_peuplee: str) -> None:
    statuts = set(Mission.objects.values_list("statut", flat=True))
    assert statuts <= set(StatutMission.values)
    # Étape la plus avancée : au moins la prise de connaissance et le référentiel validé.
    assert EtapeMission.objects.filter(numero=6, statut=StatutEtape.VALIDEE).exists()
    assert EtapeMission.objects.filter(numero=3, statut=StatutEtape.TERMINEE).exists()


def test_aucune_entree_de_piste_sans_acteur(base_peuplee: str) -> None:
    sans_acteur = LogEntry.objects.filter(actor__isnull=True)
    assert not sans_acteur.exists(), sorted(
        {(e.content_type.model, e.action) for e in sans_acteur.select_related("content_type")}
    )
    assert LogEntry.objects.filter(actor__username="demo").exists()


def test_deuxieme_execution_ne_duplique_rien(base_peuplee: str) -> None:
    avant = instantane()
    sortie = lancer("--profil", "volumetrie", "--echelle", ECHELLE)
    assert "déjà" in sortie
    assert instantane() == avant


def test_meme_graine_memes_libelles(db: None, stockage_tmp: None) -> None:
    def une_base(graine: str) -> dict[str, list[Any]]:
        with transaction.atomic():
            lancer("--profil", "volumetrie", "--echelle", ECHELLE, "--graine", graine)
            resultat = instantane()
            transaction.set_rollback(True)
        return resultat

    premiere = une_base("7")
    assert User.objects.count() == 0  # la première base a bien été annulée
    assert une_base("7") == premiere
    assert une_base("8") != premiere


def test_profil_formation_une_mission_lisible_par_etape(db: None, stockage_tmp: None) -> None:
    lancer("--profil", "formation")
    assert Mission.objects.count() == 6
    assert User.objects.filter(username__startswith="formation.").count() == 7
    assert all(m.titre.startswith("Formation") for m in Mission.objects.all())
    assert not User.objects.filter(username__startswith="charge").exists()


# --- Exhaustivité ----------------------------------------------------------------------------


def applications_a_modeles() -> list[str]:
    return [
        config.label
        for config in apps.get_app_configs()
        if config.name.startswith("apps.") and list(config.get_models())
    ]


def test_chaque_app_a_son_peuplement() -> None:
    manquantes = [label for label in applications_a_modeles() if label not in demo.ORDRE]
    assert not manquantes, f"Applications sans peuplement enregistré : {manquantes}"
    for label in demo.ORDRE:
        module = importlib.import_module(f"apps.{label}.demo")
        peupler: Callable[..., None] = module.peupler
        assert callable(peupler)
