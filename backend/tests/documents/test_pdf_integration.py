import io
import os
import zipfile

import pytest
import requests
from django.test import override_settings

from apps.documents.pdf import convertir_en_pdf

GOTENBERG_URL = os.environ.get("GOTENBERG_URL", "http://localhost:3000")

_CT = "application/vnd.openxmlformats-package.relationships+xml"
_DOC = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _gotenberg_disponible() -> bool:
    try:
        return requests.get(f"{GOTENBERG_URL}/health", timeout=2).status_code == 200
    except requests.RequestException:
        return False


def _docx_minimal(texte: str) -> bytes:
    contenu = io.BytesIO()
    with zipfile.ZipFile(contenu, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            f'<Default Extension="rels" ContentType="{_CT}"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            f'<Override PartName="/word/document.xml" ContentType="{_DOC}"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{_REL}" Target="word/document.xml"/>'
            "</Relationships>",
        )
        archive.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<w:document xmlns:w="{_W}">'
            f"<w:body><w:p><w:r><w:t>{texte}</w:t></w:r></w:p></w:body></w:document>",
        )
    return contenu.getvalue()


@pytest.mark.gotenberg
@pytest.mark.skipif(not _gotenberg_disponible(), reason="Gotenberg indisponible")
@override_settings(GOTENBERG_URL=GOTENBERG_URL, GOTENBERG_TIMEOUT=60)
def test_integration_docx_reel_vers_pdf() -> None:
    assert convertir_en_pdf(_docx_minimal("Bonjour"), pdfa=False).startswith(b"%PDF-")
