import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from django.db import connection

from apps.core.exceptions import RegleMetierError
from apps.documents.integrite import IntegriteError
from apps.documents.models import (
    ConsultationDocument,
    GabaritDocument,
    StatutGabarit,
)
from apps.documents.moteur import registre
from apps.documents.moteur.registre import TypeDocument
from apps.documents.pdf import GotenbergIndisponibleError
from apps.documents.services.gabarits import (
    activer_gabarit,
    apercu_gabarit,
    deposer_gabarit,
    fichier_gabarit,
    gabarit_actif,
)
from apps.documents.stockage import stockage_documents
from apps.users.models import User

from .fabrique import CONTRAT_TEST, docx_avec, texte_docx

pytestmark = pytest.mark.django_db


def _fichiers(racine: Path) -> list[Path]:
    return [p for p in racine.rglob("*") if p.is_file()]


def _deposer(
    type_test: TypeDocument, rai: User, texte: str = "Mission : {{ mission.titre }}"
) -> GabaritDocument:
    return deposer_gabarit(
        type_document=type_test.code,
        contenu=docx_avec(texte),
        nom_original="modele.docx",
        by=rai,
    )


def test_depot_cree_version_suivante_et_empreinte(type_test: TypeDocument, rai: User) -> None:
    g1 = _deposer(type_test, rai)
    contenu = docx_avec("Mission : {{ mission.titre }} bis")
    g2 = deposer_gabarit(
        type_document=type_test.code,
        contenu=contenu,
        nom_original="m2.docx",
        by=rai,
        commentaire="v2",
    )
    assert (g1.version, g2.version) == (1, 2)
    assert g2.statut == StatutGabarit.DEPOSE
    assert g2.empreinte == hashlib.sha256(contenu).hexdigest()
    assert g2.taille == len(contenu)
    assert g2.contrat_version == CONTRAT_TEST.version
    assert "mission" in g2.balises
    assert g2.commentaire == "v2"
    assert g2.created_by == rai


def test_depot_refuse_n_ecrit_rien(type_test: TypeDocument, rai: User, stockage_tmp: Path) -> None:
    with pytest.raises(RegleMetierError) as exc:
        _deposer(type_test, rai, "{{ inconnue.truc }}")
    assert "fichier" in exc.value.errors
    assert _fichiers(stockage_tmp) == []
    assert GabaritDocument.all_objects.count() == 0


def test_depot_type_inconnu(rai: User) -> None:
    with pytest.raises(RegleMetierError, match="Type de document inconnu"):
        deposer_gabarit(type_document="NOPE", contenu=b"x", nom_original="a.docx", by=rai)


def test_depot_quota_depasse(type_test: TypeDocument, rai: User, settings: object) -> None:
    settings.DOCUMENTS_QUOTA_MO = 1  # type: ignore[attr-defined]
    with (
        patch("apps.documents.services.gabarits._utilise_octets", return_value=1024 * 1024),
        pytest.raises(RegleMetierError, match="quota"),
    ):
        _deposer(type_test, rai)


def test_activer_archive_le_precedent(type_test: TypeDocument, rai: User) -> None:
    g1 = activer_gabarit(_deposer(type_test, rai), by=rai)
    g2 = activer_gabarit(_deposer(type_test, rai), by=rai)
    g1.refresh_from_db()
    assert g1.statut == StatutGabarit.ARCHIVE
    assert g2.statut == StatutGabarit.ACTIF
    assert g2.active_par == rai
    assert g2.active_le is not None
    assert gabarit_actif(type_test.code).pk == g2.pk
    # an archived template can be reactivated
    g1 = activer_gabarit(g1, by=rai)
    g2.refresh_from_db()
    assert (g1.statut, g2.statut) == (StatutGabarit.ACTIF, StatutGabarit.ARCHIVE)


def test_activer_revalide_contre_contrat_courant(type_test: TypeDocument, rai: User) -> None:
    g = _deposer(type_test, rai)
    contrat = replace(
        CONTRAT_TEST,
        version=2,
        champs=tuple(c for c in CONTRAT_TEST.champs if c.nom != "mission"),
        exemple={k: v for k, v in CONTRAT_TEST.exemple.items() if k != "mission"},
    )
    registre._TYPES["TEST_DOC"] = replace(type_test, contrat=contrat)
    with pytest.raises(RegleMetierError) as exc:
        activer_gabarit(g, by=rai)
    assert "fichier" in exc.value.errors
    g.refresh_from_db()
    assert g.statut == StatutGabarit.DEPOSE


def test_gabarit_actif_absent_message(type_test: TypeDocument) -> None:
    with pytest.raises(RegleMetierError) as exc:
        gabarit_actif(type_test.code)
    assert exc.value.message == (
        "Aucun gabarit actif pour « Document de test » : l'administrateur doit en déposer un."
    )


def test_apercu_docx_contient_l_exemple(type_test: TypeDocument, rai: User) -> None:
    g = _deposer(type_test, rai)
    contenu, nom = apercu_gabarit(g, format="docx")
    assert nom == "apercu-test_doc-v1.docx"
    assert "Audit des achats" in texte_docx(contenu)


def test_apercu_pdf_gotenberg_indisponible_422(type_test: TypeDocument, rai: User) -> None:
    g = _deposer(type_test, rai)
    with (
        patch(
            "apps.documents.services.gabarits.convertir_en_pdf",
            side_effect=GotenbergIndisponibleError,
        ),
        pytest.raises(RegleMetierError) as exc,
    ):
        apercu_gabarit(g, format="pdf")
    assert exc.value.message == (
        "Le service de conversion PDF est indisponible : réessayez plus tard."
    )


def test_apercu_pdf(type_test: TypeDocument, rai: User) -> None:
    g = _deposer(type_test, rai)
    with patch("apps.documents.services.gabarits.convertir_en_pdf", return_value=b"%PDF-x"):
        contenu, nom = apercu_gabarit(g, format="pdf")
    assert (contenu, nom) == (b"%PDF-x", "apercu-test_doc-v1.pdf")


def test_telechargement_gabarit_journalise(type_test: TypeDocument, rai: User) -> None:
    g = _deposer(type_test, rai)
    contenu, nom = fichier_gabarit(g, by=rai, adresse_ip="10.0.0.1")
    assert nom == "modele.docx"
    assert contenu[:2] == b"PK"
    c = ConsultationDocument.objects.get()
    assert (c.gabarit_id, c.utilisateur_id, c.format, c.adresse_ip) == (
        g.pk,
        rai.pk,
        "DOCX",
        "10.0.0.1",
    )


def test_integrite_telechargement_altere(type_test: TypeDocument, rai: User) -> None:
    g = _deposer(type_test, rai)
    chemin = Path(stockage_documents().path(g.fichier.name or ""))
    chemin.chmod(0o666)
    chemin.write_bytes(b"altere")
    with pytest.raises(IntegriteError):
        fichier_gabarit(g, by=rai, adresse_ip=None)
    with pytest.raises(IntegriteError):
        activer_gabarit(g, by=rai)
    with pytest.raises(IntegriteError):
        apercu_gabarit(g, format="docx")


def test_activer_gabarit_supprime_refuse(type_test: TypeDocument, rai: User) -> None:
    g = _deposer(type_test, rai)
    g.soft_delete(rai)
    with pytest.raises(RegleMetierError, match="supprimé"):
        activer_gabarit(g, by=rai)


def test_nom_original_assaini(type_test: TypeDocument, rai: User) -> None:
    g = deposer_gabarit(
        type_document=type_test.code,
        contenu=docx_avec("{{ mission.titre }}"),
        nom_original="C:\\dossier\\..\\sous/rep/mo\x00dele" + "x" * 300 + ".docx",
        by=rai,
    )
    assert len(g.nom_original) <= 255
    assert g.nom_original.endswith(".docx")
    assert "/" not in g.nom_original
    assert "\\" not in g.nom_original
    assert "\x00" not in g.nom_original


def test_echec_apres_ecriture_puis_reessai(type_test: TypeDocument, rai: User) -> None:
    with (
        patch("apps.documents.services.gabarits.enregistrer", side_effect=RuntimeError("boom")),
        pytest.raises(RuntimeError),
    ):
        _deposer(type_test, rai)
    assert GabaritDocument.all_objects.count() == 0
    # retry: the identical leftover file is reused instead of failing
    assert _deposer(type_test, rai).version == 1


@pytest.mark.django_db(transaction=True)
def test_premier_depot_concurrent(type_test: TypeDocument, rai: User) -> None:
    def un(i: int) -> int:
        try:
            return deposer_gabarit(
                type_document=type_test.code,
                contenu=docx_avec(f"Mission {i} : {{{{ mission.titre }}}}"),
                nom_original=f"m{i}.docx",
                by=rai,
            ).version
        finally:
            connection.close()

    with ThreadPoolExecutor(2) as ex:
        versions = sorted(ex.map(un, range(2)))
    assert versions == [1, 2]
    assert GabaritDocument.all_objects.count() == 2
