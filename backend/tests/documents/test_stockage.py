"""Write-once document storage on the server disk (no public URL, 0640 files)."""

import os
import shutil
import stat
from collections import namedtuple
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation

from apps.core.exceptions import RegleMetierError
from apps.documents.stockage import (
    EspaceInsuffisantError,
    FichierExistantError,
    StockageIndisponibleError,
    cle_gabarit,
    cle_version,
    configuration_stockage,
    ecrire,
    ecrire_avec_empreinte,
    etat_stockage,
    lire,
    stockage_documents,
)
from config.settings import base as base_settings

_Usage = namedtuple("_Usage", "total used free")  # noqa: PYI024


@pytest.fixture
def stockage_tmp(tmp_path: Path, settings: Any) -> Path:
    settings.DOCUMENTS_ROOT = str(tmp_path)
    settings.STORAGES = {
        **settings.STORAGES,
        "documents": configuration_stockage(
            {"DOCUMENTS_STORAGE": "filesystem", "DOCUMENTS_ROOT": str(tmp_path)}
        ),
    }
    return tmp_path


def test_ecriture_unique_et_permissions(stockage_tmp: Path) -> None:
    nom = ecrire("versions/x/v001.docx", b"PK")
    assert lire(nom) == b"PK"
    if os.name != "nt":
        assert stat.S_IMODE(os.stat(stockage_tmp / nom).st_mode) == 0o640
    with pytest.raises(FichierExistantError):
        ecrire("versions/x/v001.docx", b"autre")
    assert lire(nom) == b"PK"


def test_aucune_url_publique_des_fichiers(stockage_tmp: Path) -> None:
    with pytest.raises(NotImplementedError):
        stockage_documents().url("versions/x/v001.docx")
    assert not getattr(base_settings, "MEDIA_URL", "")
    nginx = Path(settings.BASE_DIR.parent / "docker/nginx/prod.conf").read_text(encoding="utf-8")
    assert "documents" not in nginx


def test_cles() -> None:
    assert cle_gabarit("lettre", 3, "abcdef0123456789ff") == "gabarits/lettre/003-abcdef012345.docx"
    doc = uuid4()
    assert cle_version(doc, 12, "pdf") == f"versions/{doc}/v012.pdf"


def test_chemin_hors_racine_refuse(stockage_tmp: Path) -> None:
    with pytest.raises(SuspiciousFileOperation):
        ecrire("../evasion.docx", b"x")
    assert not (stockage_tmp.parent / "evasion.docx").exists()


def test_espace_insuffisant_refuse_l_ecriture(
    stockage_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(shutil, "disk_usage", lambda _p: _Usage(10**9, 10**9, 0))
    with pytest.raises(EspaceInsuffisantError) as exc:
        ecrire("versions/y/v001.pdf", b"%PDF")
    assert isinstance(exc.value, RegleMetierError)
    assert "Espace disque insuffisant" in exc.value.message
    assert not (stockage_tmp / "versions/y/v001.pdf").exists()


def test_etat_stockage_ok_puis_faible(
    stockage_tmp: Path, monkeypatch: pytest.MonkeyPatch, settings: Any
) -> None:
    settings.DOCUMENTS_ESPACE_MIN_LIBRE_MO = 1
    assert etat_stockage() == "ok"
    settings.DOCUMENTS_ESPACE_MIN_LIBRE_MO = 500
    monkeypatch.setattr(shutil, "disk_usage", lambda _p: _Usage(10**9, 0, 100 * 2**20))
    assert etat_stockage() == "faible"


def test_etat_stockage_indisponible_si_dossier_absent(stockage_tmp: Path, settings: Any) -> None:
    absent = str(stockage_tmp / "absent")
    settings.STORAGES = {
        **settings.STORAGES,
        "documents": configuration_stockage(
            {"DOCUMENTS_STORAGE": "filesystem", "DOCUMENTS_ROOT": absent}
        ),
    }
    assert etat_stockage() == "indisponible"


def test_etat_stockage_indisponible_si_non_inscriptible(
    stockage_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(os, "access", lambda _p, _m: False)
    assert etat_stockage() == "indisponible"


def test_configuration_s3() -> None:
    conf = configuration_stockage(
        {
            "DOCUMENTS_STORAGE": "s3",
            "DOCUMENTS_S3_ENDPOINT_URL": "https://s3.example.org",
            "DOCUMENTS_S3_ACCESS_KEY": "k",
            "DOCUMENTS_S3_SECRET_KEY": "s",
            "DOCUMENTS_S3_BUCKET": "b",
        }
    )
    assert conf["BACKEND"] == "storages.backends.s3.S3Storage"
    assert conf["OPTIONS"]["file_overwrite"] is False
    assert conf["OPTIONS"]["querystring_auth"] is False
    assert conf["OPTIONS"]["bucket_name"] == "b"


def test_configuration_filesystem() -> None:
    conf = configuration_stockage({"DOCUMENTS_STORAGE": "filesystem", "DOCUMENTS_ROOT": "/x"})
    assert conf["BACKEND"] == "apps.documents.stockage.StockageEcritureUnique"
    assert conf["OPTIONS"]["location"] == "/x"


def test_settings_declarent_les_reglages_documents() -> None:
    assert "documents" in settings.STORAGES
    assert settings.GOTENBERG_URL
    assert settings.GOTENBERG_TIMEOUT == 90
    assert "apps.documents" in settings.INSTALLED_APPS
    assert not getattr(base_settings, "MEDIA_URL", "")


def test_compose_sans_minio() -> None:
    root = Path(settings.BASE_DIR).parent
    cibles = [
        *root.glob(".env*.example"),
        root / "Makefile",
        root / "frontend/.env.example",
        *(f for d in ("docker", "scripts") for f in (root / d).rglob("*") if f.is_file()),
    ]
    assert cibles
    for fichier in cibles:
        assert "minio" not in fichier.read_text(encoding="utf-8", errors="ignore").lower(), fichier


def test_compose_prod_monte_le_volume_documents_sur_web_et_worker_seulement() -> None:
    texte = (Path(settings.BASE_DIR).parent / "docker/compose.prod.yml").read_text(encoding="utf-8")
    assert texte.count("source: ${DOCUMENTS_HOST_DIR:?DOCUMENTS_HOST_DIR is required}") == 2
    assert texte.count("target: /var/lib/onea/documents") == 2
    assert texte.count("create_host_path: false") == 2
    assert "--profile storage" not in texte


def _fichiers_sous(racine: Path) -> list[Path]:
    return [p for p in racine.rglob("*") if p.is_file()]


def test_empreinte_sha256_calculee_a_l_ecriture(stockage_tmp: Path) -> None:
    import hashlib

    contenu = b"PK" + b"x" * 200_000
    cle, empreinte = ecrire_avec_empreinte("versions/e/v001.docx", contenu)
    assert empreinte == hashlib.sha256(contenu).hexdigest()
    assert lire(cle) == contenu


def test_echec_d_ecriture_ne_laisse_ni_fichier_final_ni_temporaire_puis_reessai(
    stockage_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def echec(_fd: int) -> None:
        raise OSError("disque plein simule")

    monkeypatch.setattr(os, "fsync", echec)
    with pytest.raises(StockageIndisponibleError) as exc:
        ecrire("versions/f/v001.docx", b"PK")
    assert isinstance(exc.value, RegleMetierError)
    assert _fichiers_sous(stockage_tmp) == []
    monkeypatch.undo()
    assert lire(ecrire("versions/f/v001.docx", b"PK")) == b"PK"
    assert [p.name for p in _fichiers_sous(stockage_tmp)] == ["v001.docx"]


def test_ecriture_existante_n_ecrase_pas_et_ne_laisse_pas_de_temporaire(
    stockage_tmp: Path,
) -> None:
    ecrire("versions/g/v001.docx", b"original")
    with pytest.raises(FichierExistantError):
        ecrire("versions/g/v001.docx", b"autre")
    assert [p.name for p in _fichiers_sous(stockage_tmp)] == ["v001.docx"]
    assert lire("versions/g/v001.docx") == b"original"


def test_suppression_interdite(stockage_tmp: Path) -> None:
    cle = ecrire("versions/h/v001.docx", b"PK")
    with pytest.raises(NotImplementedError):
        stockage_documents().delete(cle)
    assert lire(cle) == b"PK"


@pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
def test_lien_symbolique_dans_le_chemin_refuse(stockage_tmp: Path, tmp_path_factory: Any) -> None:
    dehors = tmp_path_factory.mktemp("dehors")
    (stockage_tmp / "versions").symlink_to(dehors, target_is_directory=True)
    with pytest.raises(SuspiciousFileOperation):
        ecrire("versions/i/v001.docx", b"PK")
    assert list(dehors.rglob("*")) == []


def test_cles_invalides_refusees() -> None:
    for type_document, version, empreinte in [
        ("../x", 1, "abcdef012345"),
        ("1lettre", 1, "abcdef012345"),
        ("", 1, "abcdef012345"),
        ("lettre", -1, "abcdef012345"),
        ("lettre", 1, "zz"),
        ("lettre", 1, "../../etc/passwd"),
    ]:
        with pytest.raises(ValueError, match="invalide"):
            cle_gabarit(type_document, version, empreinte)
    with pytest.raises(ValueError, match="invalide"):
        cle_version(uuid4(), 0, "exe")  # type: ignore[arg-type]


def test_dev_cree_le_dossier_prod_non(tmp_path: Path, settings: Any) -> None:
    from django.apps import apps

    cible = tmp_path / "nouveau"
    settings.DOCUMENTS_ROOT = str(cible)
    settings.DOCUMENTS_CREER_DOSSIER = False
    apps.get_app_config("documents").ready()
    assert not cible.exists()
    settings.DOCUMENTS_CREER_DOSSIER = True
    apps.get_app_config("documents").ready()
    assert cible.is_dir()


def test_s3_existant_est_une_erreur_pas_un_renommage(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from apps.documents import stockage as mod

    faux = SimpleNamespace(
        exists=lambda _c: True, save=lambda *_a, **_k: pytest.fail("saved over existing key")
    )
    monkeypatch.setattr(mod, "stockage_documents", lambda: faux)
    with pytest.raises(FichierExistantError):
        ecrire("versions/s/v001.docx", b"PK")
