import hashlib
import logging
import uuid
from typing import Any
from unittest.mock import Mock

import pytest
from django.db import connection

from apps.core.exceptions import RegleMetierError
from apps.documents import pdf
from apps.documents.exceptions import ContratNonRespecteError
from apps.documents.integrite import IntegriteError
from apps.documents.models import ConsultationDocument, DocumentVersion, GabaritDocument
from apps.documents.moteur.registre import TypeDocument
from apps.documents.pdf import GotenbergIndisponibleError
from apps.documents.services.generation import (
    demander_generation,
    ouvrir_version,
    relancer_pdf,
    verifier_integrite,
)
from apps.missions.models import Mission
from apps.users.models import User

from .conftest import chemin_fichier

pytestmark = pytest.mark.django_db


def generer(rai: User, objet: Mission, capture: Any) -> DocumentVersion:
    with capture(execute=True):
        version = demander_generation(type_document="TEST_DOC", objet_id=objet.pk, by=rai)
    version.refresh_from_db()
    return version


def test_pdf_echoue_word_reste_disponible(
    type_test: TypeDocument,
    gabarit_actif_test: GabaritDocument,
    objet_test: Mission,
    rai: User,
    monkeypatch: pytest.MonkeyPatch,
    django_capture_on_commit_callbacks: Any,
) -> None:
    monkeypatch.setattr(pdf, "convertir_en_pdf", Mock(side_effect=GotenbergIndisponibleError))
    with django_capture_on_commit_callbacks(execute=True):
        v = demander_generation(type_document="TEST_DOC", objet_id=objet_test.pk, by=rai)
    v.refresh_from_db()
    assert (v.statut, v.statut_pdf) == ("PRETE", "ECHEC")
    assert "Le document Word reste disponible" in v.erreur_pdf
    contenu, nom = ouvrir_version(v, format="DOCX", by=rai, adresse_ip=None)
    assert hashlib.sha256(contenu).hexdigest() == v.empreinte_docx and nom.endswith("_v1.docx")
    assert nom == "DAI-2026-M01-TD-01_v1.docx"
    with pytest.raises(RegleMetierError, match="PDF n'est pas encore disponible"):
        ouvrir_version(v, format="PDF", by=rai, adresse_ip=None)


def test_generation_nominale_word_et_pdf(
    type_test: TypeDocument,
    gabarit_actif_test: GabaritDocument,
    objet_test: Mission,
    rai: User,
    pdf_factice: bytes,
    django_capture_on_commit_callbacks: Any,
) -> None:
    v = generer(rai, objet_test, django_capture_on_commit_callbacks)
    assert (v.statut, v.statut_pdf, v.numero_version) == ("PRETE", "PRET", 1)
    assert v.document.numero == "DAI/2026/M01/TD-01"
    assert v.empreinte_pdf == hashlib.sha256(pdf_factice).hexdigest()
    contenu, nom = ouvrir_version(v, format="PDF", by=rai, adresse_ip="10.0.0.1")
    assert contenu == pdf_factice and nom == "DAI-2026-M01-TD-01_v1.pdf"
    assert verifier_integrite(v) == {"docx": True, "pdf": True}


def test_deja_a_jour_puis_nouvelle_version_si_donnees_ou_gabarit_changent(
    type_test: TypeDocument,
    gabarit_actif_test: GabaritDocument,
    objet_test: Mission,
    rai: User,
    pdf_factice: bytes,
    django_capture_on_commit_callbacks: Any,
) -> None:
    generer(rai, objet_test, django_capture_on_commit_callbacks)
    with pytest.raises(RegleMetierError, match=r"déjà à jour.*version 1"):
        demander_generation(type_document="TEST_DOC", objet_id=objet_test.pk, by=rai)
    Mission.objects.filter(pk=objet_test.pk).update(titre="Nouveau titre")
    v2 = generer(rai, objet_test, django_capture_on_commit_callbacks)
    assert v2.numero_version == 2 and v2.document.numero == "DAI/2026/M01/TD-01"
    # new template version -> new document version even with the same data
    GabaritDocument.all_objects.filter(pk=gabarit_actif_test.pk).update(statut="ARCHIVE")
    gabarit_actif_test.pk = None
    gabarit_actif_test.id = uuid.uuid4()
    gabarit_actif_test.version = 2
    gabarit_actif_test.statut = "ACTIF"
    gabarit_actif_test.fichier = v2.gabarit.fichier.name
    gabarit_actif_test._state.adding = True
    gabarit_actif_test.save()
    v3 = generer(rai, objet_test, django_capture_on_commit_callbacks)
    assert v3.numero_version == 3


def test_echec_rendu_puis_nouvelle_demande(
    type_test: TypeDocument,
    gabarit_actif_test: GabaritDocument,
    objet_test: Mission,
    rai: User,
    pdf_factice: bytes,
    monkeypatch: pytest.MonkeyPatch,
    django_capture_on_commit_callbacks: Any,
) -> None:
    from apps.documents.moteur.exceptions import RenduError
    from apps.documents.services import generation

    monkeypatch.setattr(generation, "rendre_docx", Mock(side_effect=RenduError("Rendu trop long.")))
    v = generer(rai, objet_test, django_capture_on_commit_callbacks)
    assert v.statut == "ECHEC" and v.erreur == "Rendu trop long." and v.statut_pdf == "NON_DEMANDE"
    monkeypatch.undo()
    monkeypatch.setattr(pdf, "convertir_en_pdf", Mock(return_value=pdf_factice))
    v2 = generer(rai, objet_test, django_capture_on_commit_callbacks)
    assert v2.numero_version == 2 and v2.statut == "PRETE"
    assert v2.document_id == v.document_id


def test_raison_non_generable_422(
    type_test: TypeDocument,
    gabarit_actif_test: GabaritDocument,
    objet_test: Mission,
    rai: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        type_test.fournisseur, "raison_non_generable", lambda objet: "Pas encore prêt."
    )
    with pytest.raises(RegleMetierError, match="Pas encore prêt."):
        demander_generation(type_document="TEST_DOC", objet_id=objet_test.pk, by=rai)


def test_mission_figee_refuse_la_generation(
    type_test: TypeDocument,
    gabarit_actif_test: GabaritDocument,
    objet_test: Mission,
    rai: User,
) -> None:
    Mission.objects.filter(pk=objet_test.pk).update(statut="SUSPENDUE")
    with pytest.raises(RegleMetierError, match=r"DAI/2026/M01.*aucun document ne peut"):
        demander_generation(type_document="TEST_DOC", objet_id=objet_test.pk, by=rai)


def test_aucun_gabarit_actif_ou_contrat_perime(
    type_test: TypeDocument, objet_test: Mission, rai: User, gabarit_actif_test: GabaritDocument
) -> None:
    GabaritDocument.all_objects.filter(pk=gabarit_actif_test.pk).update(contrat_version=0)
    with pytest.raises(RegleMetierError, match="version antérieure du contrat"):
        demander_generation(type_document="TEST_DOC", objet_id=objet_test.pk, by=rai)
    GabaritDocument.all_objects.filter(pk=gabarit_actif_test.pk).update(statut="ARCHIVE")
    with pytest.raises(RegleMetierError, match="Aucun gabarit actif"):
        demander_generation(type_document="TEST_DOC", objet_id=objet_test.pk, by=rai)


def test_contrat_non_respecte_leve(
    type_test: TypeDocument,
    gabarit_actif_test: GabaritDocument,
    objet_test: Mission,
    rai: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(type_test.fournisseur, "contexte", lambda objet: {"mission": {}})
    with pytest.raises(ContratNonRespecteError):
        demander_generation(type_document="TEST_DOC", objet_id=objet_test.pk, by=rai)
    assert DocumentVersion.all_objects.count() == 0


def test_fichier_altere_409_et_journal_critical(
    version_prete: DocumentVersion, rai: User, caplog: pytest.LogCaptureFixture
) -> None:
    chemin = chemin_fichier(version_prete.fichier_docx.name)
    chemin.write_bytes(b"altere")
    with caplog.at_level(logging.CRITICAL), pytest.raises(IntegriteError, match="altéré"):
        ouvrir_version(version_prete, format="DOCX", by=rai, adresse_ip=None)
    assert any(r.levelno == logging.CRITICAL for r in caplog.records)
    assert verifier_integrite(version_prete)["docx"] is False
    assert ConsultationDocument.all_objects.count() == 0


def test_telechargement_journalise_consultation(version_prete: DocumentVersion, rai: User) -> None:
    ouvrir_version(version_prete, format="DOCX", by=rai, adresse_ip="192.168.1.5")
    c = ConsultationDocument.objects.get()
    assert (c.version_id, c.utilisateur_id, c.format, c.adresse_ip) == (
        version_prete.pk,
        rai.pk,
        "DOCX",
        "192.168.1.5",
    )


def test_quota_depasse_refuse(
    type_test: TypeDocument,
    gabarit_actif_test: GabaritDocument,
    objet_test: Mission,
    rai: User,
    settings: Any,
) -> None:
    settings.DOCUMENTS_QUOTA_MO = 1
    with connection.cursor() as cur:  # raw SQL: the model guards freeze the size
        cur.execute(
            "UPDATE documents_gabaritdocument SET taille = %s WHERE id = %s",
            [2 * 1024 * 1024, gabarit_actif_test.pk],
        )
    with pytest.raises(RegleMetierError, match="quota"):
        demander_generation(type_document="TEST_DOC", objet_id=objet_test.pk, by=rai)


def test_relancer_pdf_seulement_si_echec(
    version_prete: DocumentVersion,
    rai: User,
    pdf_factice: bytes,
    django_capture_on_commit_callbacks: Any,
) -> None:
    with pytest.raises(RegleMetierError, match="échoué"):
        relancer_pdf(version_prete, by=rai)
    DocumentVersion.all_objects.filter(pk=version_prete.pk).update(statut_pdf="ECHEC")
    version_prete.refresh_from_db()
    with django_capture_on_commit_callbacks(execute=True):
        relancer_pdf(version_prete, by=rai)
    version_prete.refresh_from_db()
    assert version_prete.statut_pdf == "PRET" and version_prete.empreinte_pdf
