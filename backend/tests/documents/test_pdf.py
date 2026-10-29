from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.test import override_settings

from apps.documents.pdf import (
    ConversionPdfError,
    GotenbergIndisponibleError,
    convertir_en_pdf,
)

PDF = b"%PDF-1.7\nfake"
REGLAGES = {"GOTENBERG_URL": "http://gotenberg:3000", "GOTENBERG_TIMEOUT": 30}


def _reponse(status: int = 200, content: bytes = PDF) -> MagicMock:
    reponse = MagicMock()
    reponse.status_code = status
    reponse.content = content
    return reponse


@override_settings(DOCUMENTS_PDFA=True, **REGLAGES)
def test_conversion_envoie_le_docx_et_pdfa() -> None:
    with patch("apps.documents.pdf.requests.post", return_value=_reponse()) as post:
        resultat = convertir_en_pdf(b"docx-bytes", nom="note.docx")

    assert resultat == PDF
    args, kwargs = post.call_args
    assert args[0] == "http://gotenberg:3000/forms/libreoffice/convert"
    assert kwargs["files"] == {"files": ("note.docx", b"docx-bytes")}
    assert kwargs["data"] == {"pdfa": "PDF/A-2b"}
    assert kwargs["timeout"] == (5, 30)
    assert kwargs["allow_redirects"] is False


@override_settings(DOCUMENTS_PDFA=True, **REGLAGES)
def test_pdfa_desactive_par_parametre() -> None:
    with patch("apps.documents.pdf.requests.post", return_value=_reponse()) as post:
        convertir_en_pdf(b"x", pdfa=False)
    assert post.call_args.kwargs["data"] == {}


@override_settings(DOCUMENTS_PDFA=False, **REGLAGES)
def test_pdfa_suit_le_reglage_par_defaut() -> None:
    with patch("apps.documents.pdf.requests.post", return_value=_reponse()) as post:
        convertir_en_pdf(b"x")
    assert post.call_args.kwargs["data"] == {}


@pytest.fixture(autouse=True)
def _sans_attente() -> Any:
    with patch("apps.documents.pdf.time.sleep") as sleep:
        yield sleep


@override_settings(DOCUMENTS_PDFA=True, **REGLAGES)
@pytest.mark.parametrize(
    "effet",
    [
        {"return_value": _reponse(500, b"")},
        {"return_value": _reponse(503, b"")},
        {"side_effect": requests.ConnectionError("down")},
        {"side_effect": requests.Timeout("lent")},
    ],
)
def test_5xx_et_reseau_indisponible(effet: dict[str, Any]) -> None:
    with (
        patch("apps.documents.pdf.requests.post", **effet),
        pytest.raises(GotenbergIndisponibleError),
    ):
        convertir_en_pdf(b"x")


@override_settings(DOCUMENTS_PDFA=True, **REGLAGES)
@pytest.mark.parametrize(
    "reponse",
    [_reponse(400, b"bad"), _reponse(302, b""), _reponse(200, b"<html>pas un pdf</html>")],
)
def test_4xx_ou_reponse_non_pdf(reponse: MagicMock) -> None:
    with (
        patch("apps.documents.pdf.requests.post", return_value=reponse),
        pytest.raises(ConversionPdfError),
    ):
        convertir_en_pdf(b"x")


@override_settings(DOCUMENTS_PDFA=True, **REGLAGES)
def test_503_au_demarrage_a_froid_est_retente(_sans_attente: MagicMock) -> None:
    with patch(
        "apps.documents.pdf.requests.post",
        side_effect=[_reponse(503, b""), requests.ConnectionError("x"), _reponse()],
    ) as post:
        assert convertir_en_pdf(b"x") == PDF
    assert post.call_count == 3
    assert _sans_attente.call_count == 2


@override_settings(DOCUMENTS_PDFA=True, **REGLAGES)
def test_retry_borne_apres_trois_tentatives() -> None:
    with (
        patch("apps.documents.pdf.requests.post", return_value=_reponse(503, b"")) as post,
        pytest.raises(GotenbergIndisponibleError),
    ):
        convertir_en_pdf(b"x")
    assert post.call_count == 3


@override_settings(DOCUMENTS_PDFA=True, **REGLAGES)
@pytest.mark.parametrize("reponse", [_reponse(500, b""), _reponse(400, b"bad")])
def test_pas_de_retry_hors_503(reponse: MagicMock) -> None:
    with (
        patch("apps.documents.pdf.requests.post", return_value=reponse) as post,
        pytest.raises((GotenbergIndisponibleError, ConversionPdfError)),
    ):
        convertir_en_pdf(b"x")
    assert post.call_count == 1


@override_settings(DOCUMENTS_PDFA=True, **REGLAGES)
def test_pas_de_retry_sur_timeout() -> None:
    with (
        patch("apps.documents.pdf.requests.post", side_effect=requests.Timeout("lent")) as post,
        pytest.raises(GotenbergIndisponibleError),
    ):
        convertir_en_pdf(b"x")
    assert post.call_count == 1
