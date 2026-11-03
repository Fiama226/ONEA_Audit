# ruff: noqa: F811, F401
"""Signature PAdES réelle (pyHanko) du rapport final : service, API, porte de diffusion."""

import hashlib
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from django.core.management import call_command
from pyhanko.pdf_utils import generic
from pyhanko.pdf_utils.writer import PdfFileWriter

from apps.communication.models import EvenementRapport, Rapport, StatutRapport
from apps.communication.services.diffusion import diffuser
from apps.communication.services.signature import signer_rapport
from apps.communication.services.validation import valider_rapport
from apps.core.exceptions import RegleMetierError
from apps.documents.integrite import IntegriteError
from apps.documents.models import DocumentVersion
from apps.documents.stockage import cle_signature, cle_version, ecrire
from apps.signatures.certificat_dev import generer_pkcs12
from apps.signatures.electronique import (
    enregistrer_signataire_electronique,
    signataire_electronique,
)
from apps.signatures.models import SignatureElectronique
from apps.signatures.pades import SignatairePades, lire_pdf_signe
from apps.signatures.parametres import modifier_mode
from apps.users.models import User
from config.documents_settings import configuration_stockage
from tests.accomplissement.fixtures_api import client_de
from tests.communication.fixtures_api import RAPPORTS, EquipeRapport, equipe
from tests.communication.support_t8 import (
    admin,
    creer_version,
    dg,
    rapport_soumis_reel,
    rapport_valide,
)

pytestmark = pytest.mark.django_db

PHRASE = "phrase-de-test"  # noqa: S105


def _pdf() -> bytes:
    ecrivain = PdfFileWriter()
    ecrivain.insert_page(
        generic.DictionaryObject(
            {
                generic.NameObject("/Type"): generic.NameObject("/Page"),
                generic.NameObject("/MediaBox"): generic.ArrayObject(
                    [generic.NumberObject(v) for v in (0, 0, 595, 842)]
                ),
                generic.NameObject("/Resources"): generic.DictionaryObject(),
            }
        )
    )
    sortie = BytesIO()
    ecrivain.write(sortie)
    return sortie.getvalue()


@pytest.fixture(autouse=True)
def stockage_tmp(tmp_path: Path, settings: Any) -> Path:
    settings.DOCUMENTS_ROOT = str(tmp_path / "docs")
    settings.STORAGES = {
        **settings.STORAGES,
        "documents": configuration_stockage(
            {"DOCUMENTS_STORAGE": "filesystem", "DOCUMENTS_ROOT": str(tmp_path / "docs")}
        ),
    }
    return tmp_path


@pytest.fixture
def certificat(tmp_path: Path, settings: Any) -> Iterator[Path]:
    secrets = tmp_path / "secrets"
    p12, pem = generer_pkcs12(PHRASE)
    secrets.mkdir()
    (secrets / "s.p12").write_bytes(p12)
    (secrets / "ancre.pem").write_bytes(pem)
    settings.SIGNATURE_PKCS12_FILE = str(secrets / "s.p12")
    settings.SIGNATURE_PKCS12_PASSPHRASE = PHRASE
    settings.SIGNATURE_ANCRES_CONFIANCE = str(secrets / "ancre.pem")
    enregistrer_signataire_electronique(SignatairePades())
    yield secrets
    enregistrer_signataire_electronique(None)


def _version_reelle(rapport: Rapport) -> DocumentVersion:
    contenu = _pdf()
    cle = uuid4()
    return creer_version(
        rapport,
        fichier_pdf=ecrire(cle_version(cle, 1, "pdf"), contenu),
        empreinte_pdf=hashlib.sha256(contenu).hexdigest(),
    )


@pytest.fixture
def rapport_pret_a_signer(
    rapport_soumis_reel: Rapport, rai: User, admin: User, certificat: Path
) -> tuple[Rapport, DocumentVersion]:
    modifier_mode("VALIDATION_RAPPORT", mode="CONFIRMATION_ET_SIGNATURE", by=admin)
    rapport = valider_rapport(rapport_soumis_reel, by=rai)
    return rapport, _version_reelle(rapport)


def test_mode_electronique_disponible_avec_certificat(certificat: Path) -> None:
    assert isinstance(signataire_electronique(), SignatairePades)


def test_signature_pades_valide(
    rapport_pret_a_signer: tuple[Rapport, DocumentVersion], rai: User
) -> None:
    rapport, version = rapport_pret_a_signer
    signature = signer_rapport(rapport, by=rai, lieu="Ouagadougou")
    assert signature.signe_par == rai and signature.lieu == "Ouagadougou"
    assert "ONEA" in signature.sujet
    contenu = lire_pdf_signe(signature)
    assert contenu.startswith(b"%PDF") and b"/ByteRange" in contenu
    # Ajout incrémental : le PDF d'origine est un préfixe du PDF signé.
    assert contenu.startswith(_origine(version))
    resultat = SignatairePades().verifier(version)
    assert resultat.valide, resultat.motif
    assert "ONEA" in resultat.signataire and resultat.signe_le is not None
    assert EvenementRapport.objects.filter(rapport=rapport, type="SIGNE").count() == 1


def _origine(version: DocumentVersion) -> bytes:
    from apps.documents.stockage import lire

    return lire(str(version.fichier_pdf.name))


def test_signature_unique_et_immuable(
    rapport_pret_a_signer: tuple[Rapport, DocumentVersion], rai: User
) -> None:
    rapport, _ = rapport_pret_a_signer
    signature = signer_rapport(rapport, by=rai)
    with pytest.raises(RegleMetierError, match="déjà signé"):
        signer_rapport(rapport, by=rai)
    with pytest.raises(RegleMetierError, match="définitive"):
        signature.soft_delete(rai)
    signature.raison = "autre"
    with pytest.raises(RegleMetierError, match="définitive"):
        signature.save()


def test_pdf_signe_ecriture_unique(
    rapport_pret_a_signer: tuple[Rapport, DocumentVersion], rai: User
) -> None:
    rapport, version = rapport_pret_a_signer
    signer_rapport(rapport, by=rai)
    with pytest.raises(FileExistsError):
        ecrire(cle_signature(version.pk), b"autre")


def test_aucune_cle_privee_persistee(
    rapport_pret_a_signer: tuple[Rapport, DocumentVersion],
    rai: User,
    stockage_tmp: Path,
    certificat: Path,
) -> None:
    rapport, _ = rapport_pret_a_signer
    signature = signer_rapport(rapport, by=rai)
    # Disque : aucun fichier du dossier des documents ne contient de clé privée.
    for fichier in (stockage_tmp / "docs").rglob("*"):
        if fichier.is_file():
            assert b"PRIVATE KEY" not in fichier.read_bytes()
    # Base : aucune colonne de la signature ne contient de matériel secret.
    valeurs = " ".join(str(v) for v in SignatureElectronique.objects.values().get().values())
    assert PHRASE not in valeurs and "PRIVATE" not in valeurs
    assert signature.empreinte_certificat != ""


def test_alteration_pdf_signe_409(
    rapport_pret_a_signer: tuple[Rapport, DocumentVersion], rai: User, stockage_tmp: Path
) -> None:
    rapport, version = rapport_pret_a_signer
    signature = signer_rapport(rapport, by=rai)
    chemin = stockage_tmp / "docs" / signature.cle_stockage
    chemin.write_bytes(chemin.read_bytes() + b"\n% altere")
    with pytest.raises(IntegriteError):
        lire_pdf_signe(signature)
    resultat = SignatairePades().verifier(version)
    assert not resultat.valide and "altéré" in resultat.motif


def test_modification_apres_signature_detectee(
    rapport_pret_a_signer: tuple[Rapport, DocumentVersion], rai: User, stockage_tmp: Path
) -> None:
    """Un ajout incrémental après la signature invalide la vérification PAdES."""
    rapport, version = rapport_pret_a_signer
    signature = signer_rapport(rapport, by=rai)
    chemin = stockage_tmp / "docs" / signature.cle_stockage
    octets = bytearray(chemin.read_bytes())
    i = octets.index(b"/ByteRange")
    octets[i + 12] ^= 1  # altère un chiffre de la plage signée
    chemin.write_bytes(bytes(octets))
    # Contourne l'empreinte (un attaquant ayant accès au disque et à la base).
    from django.db import connection

    with connection.cursor() as c:
        c.execute(
            "UPDATE signatures_signatureelectronique SET empreinte_pdf_signe=%s WHERE id=%s",
            [hashlib.sha256(bytes(octets)).hexdigest(), signature.pk],
        )
    resultat = SignatairePades().verifier(version)
    assert not resultat.valide and resultat.motif


def test_certificat_non_reconnu_invalide(
    rapport_pret_a_signer: tuple[Rapport, DocumentVersion],
    rai: User,
    settings: Any,
    tmp_path: Path,
) -> None:
    rapport, version = rapport_pret_a_signer
    signer_rapport(rapport, by=rai)
    _, autre = generer_pkcs12("x", nom_commun="Autre autorite")
    (tmp_path / "autre.pem").write_bytes(autre)
    settings.SIGNATURE_ANCRES_CONFIANCE = str(tmp_path / "autre.pem")
    resultat = SignatairePades().verifier(version)
    assert not resultat.valide and "reconnu" in resultat.motif


def test_phrase_erronee(
    rapport_pret_a_signer: tuple[Rapport, DocumentVersion], rai: User, settings: Any
) -> None:
    rapport, _ = rapport_pret_a_signer
    settings.SIGNATURE_PKCS12_PASSPHRASE = "mauvaise"  # noqa: S105
    with pytest.raises(RegleMetierError, match="phrase secrète"):
        signer_rapport(rapport, by=rai)
    assert not SignatureElectronique.objects.exists()


def test_signature_reservee_au_rai(
    rapport_pret_a_signer: tuple[Rapport, DocumentVersion], chef: User
) -> None:
    from django.core.exceptions import PermissionDenied

    rapport, _ = rapport_pret_a_signer
    with pytest.raises(PermissionDenied):
        signer_rapport(rapport, by=chef)


def test_mode_confirmation_refuse_la_signature(
    rapport_soumis_reel: Rapport, rai: User, certificat: Path
) -> None:
    rapport = valider_rapport(rapport_soumis_reel, by=rai)
    _version_reelle(rapport)
    with pytest.raises(RegleMetierError, match="n'exige pas"):
        signer_rapport(rapport, by=rai)


def test_porte_diffusion_avec_pades_reelle(
    rapport_pret_a_signer: tuple[Rapport, DocumentVersion], rai: User
) -> None:
    rapport, _ = rapport_pret_a_signer
    with pytest.raises(RegleMetierError, match="signé électroniquement"):
        diffuser(rapport, by=rai)
    signer_rapport(rapport, by=rai)
    assert diffuser(rapport, by=rai).rapport.statut == StatutRapport.DIFFUSE


def test_api_signer_verifier_telecharger_signe(
    equipe: EquipeRapport,
    rapport_pret_a_signer: tuple[Rapport, DocumentVersion],
    rai: User,
) -> None:
    rapport, _ = rapport_pret_a_signer
    url = f"{RAPPORTS}{rapport.pk}/"
    avant = client_de(rai).get(f"{url}signature/")
    assert avant.status_code == 200 and avant.json()["signee"] is False
    assert client_de(equipe.users["chef"]).post(f"{url}sign/", {}, format="json").status_code == 403
    r = client_de(rai).post(f"{url}sign/", {"lieu": "Ouagadougou"}, format="json")
    assert r.status_code == 201, r.content
    corps = r.json()
    assert corps["signee"] and corps["valide"] and "ONEA" in corps["signataire"]
    assert client_de(rai).post(f"{url}sign/", {}, format="json").status_code == 422
    verif = client_de(rai).get(f"{url}signature/").json()
    assert verif["valide"] is True and verif["signe_le"]
    # Après diffusion, le DG télécharge le PDF signé.
    assert client_de(rai).post(f"{url}distribute/", {}, format="json").status_code == 200
    pdf = client_de(equipe.users["dg"]).get(f"{url}download/?format=pdf")
    assert pdf.status_code == 200
    assert b"/ByteRange" in b"".join(pdf.streaming_content)
    assert client_de(equipe.users["dg"]).get(f"{url}signature/").json()["valide"] is True


def test_commande_certificat_dev(tmp_path: Path) -> None:
    from django.core.management import CommandError

    call_command("generer_certificat_signature_dev", sortie=str(tmp_path / "s"), phrase="p")
    assert (tmp_path / "s" / "signature-dev.p12").is_file()
    with pytest.raises(CommandError, match="existe déjà"):
        call_command("generer_certificat_signature_dev", sortie=str(tmp_path / "s"), phrase="p")


def test_sans_certificat_le_mode_electronique_reste_indisponible(admin: User) -> None:
    enregistrer_signataire_electronique(None)
    with pytest.raises(RegleMetierError, match="pas encore disponible"):
        modifier_mode("VALIDATION_RAPPORT", mode="CONFIRMATION_ET_SIGNATURE", by=admin)
