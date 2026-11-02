import logging
from typing import Any
from uuid import uuid4

import pytest
from django.http import Http404

from apps.core.exceptions import RegleMetierError
from apps.documents.generators.missions import (
    FONCTION_RAI,
    FournisseurOrdreMission,
    contexte_mission,
)
from apps.documents.models import Document, DocumentVersion
from apps.documents.moteur.contrats import ecarts_contexte
from apps.documents.moteur.registre import type_document
from apps.documents.services.generation import demander_generation
from apps.documents.stockage import lire
from apps.missions.models import Mission, RoleMission, StatutEtape
from apps.missions.services.etapes import rouvrir_etape
from apps.missions.services.missions import emettre_ordre_mission, modifier_mission
from apps.users.models import Role, User
from tests.factories import make_user
from tests.missions.conftest import affecter

from .fabrique import texte_docx
from .missions_support import COMMUN_X, emettre_ordre, gabarits_provisoires  # noqa: F401

pytestmark = pytest.mark.django_db


def test_ordre_mission_reprend_les_donnees_confirmees(
    mission_lancee: Mission,
    rai: User,
    gabarits_provisoires: None,  # noqa: F811
    django_capture_on_commit_callbacks: Any,
) -> None:
    modifier_mission(
        mission_lancee,
        by=rai,
        objectifs="Évaluer le dispositif\nVérifier les achats",
        perimetre="Direction des achats",
    )
    with django_capture_on_commit_callbacks(execute=True):
        c = emettre_ordre_mission(mission_lancee, by=rai)
    mission_lancee.refresh_from_db()
    v = DocumentVersion.objects.get(document__mission=mission_lancee)
    assert v.statut == "PRETE" and v.confirmation_id == c.pk
    assert v.document.numero == f"{mission_lancee.reference}/OM-01"
    texte = texte_docx(lire(v.fichier_docx.name))
    assert c.empreinte in texte and mission_lancee.objectifs.splitlines()[0] in texte


def test_contexte_sans_none(mission_lancee: Mission, rai: User) -> None:
    contexte = contexte_mission(mission_lancee)
    assert all(v is not None for v in contexte.values())
    assert contexte["chef_mission"] == "" and contexte["periode"] == ""
    t = type_document("ORDRE_MISSION")
    emettre_ordre(mission_lancee, rai)
    complet = {**COMMUN_X, **t.fournisseur.contexte(mission_lancee)}
    assert ecarts_contexte(t.contrat, complet) == []


def test_ordre_mission_raison_avant_emission(mission_lancee: Mission) -> None:
    assert FournisseurOrdreMission().raison_non_generable(mission_lancee) == (
        "Émettez l'ordre de mission avant de générer le document."
    )


def test_reemission_apres_reouverture_cree_v2(
    mission_lancee: Mission,
    rai: User,
    gabarits_provisoires: None,  # noqa: F811
    django_capture_on_commit_callbacks: Any,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        emettre_ordre(mission_lancee, rai)
    rouvrir_etape(mission_lancee.etapes.get(numero=1), motif="Périmètre revu", by=rai)
    mission_lancee.refresh_from_db()
    modifier_mission(mission_lancee, by=rai, perimetre="Périmètre élargi")
    with django_capture_on_commit_callbacks(execute=True):
        emettre_ordre_mission(mission_lancee, by=rai)
    assert Document.objects.filter(mission=mission_lancee).count() == 1
    numeros = sorted(DocumentVersion.objects.values_list("numero_version", flat=True))
    assert numeros == [1, 2]
    assert mission_lancee.etapes.get(numero=1).statut == StatutEtape.TERMINEE


def test_auto_generation_sans_gabarit_n_empeche_pas_l_emission(
    mission_lancee: Mission,
    rai: User,
    django_capture_on_commit_callbacks: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING), django_capture_on_commit_callbacks(execute=True):
        c = emettre_ordre(mission_lancee, rai)
    assert c.pk and not DocumentVersion.objects.exists()
    assert "Aucun gabarit actif" in caplog.text


def test_generer_deux_fois_ne_cree_pas_deux_documents(
    mission_lancee: Mission,
    rai: User,
    gabarits_provisoires: None,  # noqa: F811
    django_capture_on_commit_callbacks: Any,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        emettre_ordre(mission_lancee, rai)
    with pytest.raises(RegleMetierError, match="déjà à jour"):
        demander_generation(type_document="ORDRE_MISSION", objet_id=mission_lancee.pk, by=rai)
    assert Document.objects.count() == 1 and DocumentVersion.objects.count() == 1


def test_droits_fournisseur_ordre(mission_lancee: Mission, rai: User) -> None:
    f = FournisseurOrdreMission()
    chef = make_user(Role.AUDITEUR)
    affecter(mission_lancee, chef, RoleMission.CHEF_MISSION)
    audite = make_user(Role.AUDITE)
    affecter(mission_lancee, audite, RoleMission.AUDITE)
    emettre_ordre(mission_lancee, rai)
    mission_lancee.refresh_from_db()
    assert f.peut_generer(rai, mission_lancee) and not f.peut_generer(chef, mission_lancee)
    assert f.peut_consulter(chef, mission_lancee)
    assert f.peut_consulter(audite, mission_lancee) and not f.peut_generer(audite, mission_lancee)
    assert not f.peut_consulter(make_user(Role.AUDITEUR), mission_lancee)
    with pytest.raises(Http404):
        f.objet(uuid4())


def test_fonction_du_signataire_imprimee(
    mission_lancee: Mission,
    rai: User,
    gabarits_provisoires: None,  # noqa: F811
    django_capture_on_commit_callbacks: Any,
) -> None:
    rai.fonction = "Directeur de l'audit interne"
    rai.save(update_fields=["fonction"])
    with django_capture_on_commit_callbacks(execute=True):
        emettre_ordre(mission_lancee, rai)
    contexte = FournisseurOrdreMission().contexte(mission_lancee)
    assert contexte["signature"]["fonction"] == "Directeur de l'audit interne"
    v = DocumentVersion.objects.get(document__mission=mission_lancee)
    assert "Directeur de l'audit interne" in texte_docx(lire(v.fichier_docx.name))


@pytest.mark.parametrize("fonction", ["", "   "])
def test_fonction_vide_repli_sur_titre_rai(
    mission_lancee: Mission, rai: User, fonction: str
) -> None:
    rai.fonction = fonction
    rai.save(update_fields=["fonction"])
    emettre_ordre(mission_lancee, rai)
    contexte = FournisseurOrdreMission().contexte(mission_lancee)
    assert contexte["signature"]["fonction"] == FONCTION_RAI


def test_fonction_echappee_dans_le_docx(
    mission_lancee: Mission,
    rai: User,
    gabarits_provisoires: None,  # noqa: F811
    django_capture_on_commit_callbacks: Any,
) -> None:
    fonction = 'Directeur & <Chef> "adjoint"'
    rai.fonction = fonction
    rai.save(update_fields=["fonction"])
    with django_capture_on_commit_callbacks(execute=True):
        emettre_ordre(mission_lancee, rai)
    v = DocumentVersion.objects.get(document__mission=mission_lancee)
    assert fonction in texte_docx(lire(v.fichier_docx.name))


def test_fonction_vide_imprimee_en_repli_dans_le_docx(
    mission_lancee: Mission,
    rai: User,
    gabarits_provisoires: None,  # noqa: F811
    django_capture_on_commit_callbacks: Any,
) -> None:
    rai.fonction = ""
    rai.save(update_fields=["fonction"])
    with django_capture_on_commit_callbacks(execute=True):
        emettre_ordre(mission_lancee, rai)
    v = DocumentVersion.objects.get(document__mission=mission_lancee)
    assert FONCTION_RAI in texte_docx(lire(v.fichier_docx.name))
