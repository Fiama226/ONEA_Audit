import hashlib
from typing import Any
from unittest.mock import Mock

import pytest
from rest_framework.test import APIClient

from apps.documents.models import GabaritDocument, StatutGabarit
from apps.documents.moteur.registre import TypeDocument
from apps.documents.services import gabarits as gabarits_service
from apps.users.models import User

from .api_fixtures import depot, octets
from .conftest import chemin_fichier
from .fabrique import docx_avec

pytestmark = pytest.mark.django_db


def test_depot_gabarit_multipart_201(
    api_client: APIClient, admin: User, type_test: TypeDocument
) -> None:
    api_client.force_authenticate(admin)
    r = api_client.post("/api/v1/templates/", depot(), format="multipart")
    assert r.status_code == 201, r.content
    corps = r.json()
    assert (corps["version"], corps["statut"], corps["type_document"]) == (1, "DEPOSE", "TEST_DOC")
    assert corps["type_document_libelle"] == "Document de test"
    assert corps["balises"] == ["mission"] and corps["created_by"]["id"] == admin.id
    assert "fichier" not in corps


def test_depot_gabarit_multipart_422_liste_les_erreurs(
    api_client: APIClient, admin: User, type_test: TypeDocument
) -> None:
    api_client.force_authenticate(admin)
    contenu = docx_avec("{{ inconnue.x }} et {{ autre }}")
    r = api_client.post("/api/v1/templates/", depot(contenu=contenu), format="multipart")
    assert r.status_code == 422
    assert r.json()["detail"] and len(r.json()["errors"]["fichier"]) >= 2
    assert GabaritDocument.all_objects.count() == 0


def test_depot_trop_gros_refuse_avant_lecture(
    api_client: APIClient, admin: User, type_test: TypeDocument, settings: Any
) -> None:
    settings.DOCUMENTS_MAX_GABARIT_MO = 1
    gros = depot(contenu=b"x" * (1024 * 1024 + 1))
    api_client.force_authenticate(admin)
    # the size is read from the upload metadata: the service (and its analysis) never runs
    r = api_client.post("/api/v1/templates/", gros, format="multipart")
    assert r.status_code == 422 and "1 Mo" in r.json()["errors"]["fichier"][0]
    assert GabaritDocument.all_objects.count() == 0


def test_depot_reserve_a_l_admin(
    api_client: APIClient, rai: User, type_test: TypeDocument, user: User
) -> None:
    for acteur in (rai, user):
        api_client.force_authenticate(acteur)
        r = api_client.post("/api/v1/templates/", depot(), format="multipart")
        assert r.status_code == 403
    # 403 before 400: an empty body is refused for the right reason
    api_client.force_authenticate(rai)
    assert api_client.post("/api/v1/templates/", {}, format="multipart").status_code == 403


def test_depot_sans_fichier_400(
    api_client: APIClient, admin: User, type_test: TypeDocument
) -> None:
    api_client.force_authenticate(admin)
    r = api_client.post("/api/v1/templates/", {"type_document": "TEST_DOC"}, format="multipart")
    assert r.status_code == 400 and "fichier" in r.json()["errors"]


def test_activer(
    api_client: APIClient, admin: User, rai: User, gabarit_actif_test: GabaritDocument
) -> None:
    api_client.force_authenticate(admin)
    nouveau = api_client.post("/api/v1/templates/", depot(), format="multipart").json()
    api_client.force_authenticate(rai)
    assert api_client.post(f"/api/v1/templates/{nouveau['id']}/activate/").status_code == 403
    api_client.force_authenticate(admin)
    r = api_client.post(f"/api/v1/templates/{nouveau['id']}/activate/")
    assert r.status_code == 200 and r.json()["statut"] == "ACTIF" and r.json()["active_le"]
    gabarit_actif_test.refresh_from_db()
    assert gabarit_actif_test.statut == StatutGabarit.ARCHIVE


def test_liste_filtres_et_lecture_rai(
    api_client: APIClient, rai: User, gabarit_actif_test: GabaritDocument
) -> None:
    api_client.force_authenticate(rai)
    r = api_client.get("/api/v1/templates/?type_document=TEST_DOC&statut=ACTIF")
    assert r.status_code == 200 and r.json()["count"] == 1
    assert api_client.get("/api/v1/templates/?statut=ARCHIVE").json()["count"] == 0
    assert api_client.get(f"/api/v1/templates/{gabarit_actif_test.pk}/").status_code == 200


def test_file_et_en_tetes(
    api_client: APIClient, admin: User, gabarit_actif_test: GabaritDocument
) -> None:
    api_client.force_authenticate(admin)
    r = api_client.get(f"/api/v1/templates/{gabarit_actif_test.pk}/file/")
    assert r.status_code == 200
    contenu = octets(r)
    assert hashlib.sha256(contenu).hexdigest() == gabarit_actif_test.empreinte
    assert 'filename="gabarit.docx"' in r["Content-Disposition"]
    assert r["Content-Disposition"].startswith("attachment")
    assert r["Cache-Control"] == "private, no-store" and r["X-Content-Type-Options"] == "nosniff"


def test_nom_dangereux_assaini(
    api_client: APIClient, admin: User, gabarit_actif_test: GabaritDocument
) -> None:
    g = gabarit_actif_test
    dangereux = GabaritDocument.objects.create(
        type_document=g.type_document,
        version=2,
        fichier=g.fichier.name,
        nom_original='a"b\r\nSet-Cookie: x=1é.docx',
        taille=g.taille,
        empreinte=g.empreinte,
        contrat_version=g.contrat_version,
        created_by=admin,
    )
    api_client.force_authenticate(admin)
    r = api_client.get(f"/api/v1/templates/{dangereux.pk}/file/")
    assert r.status_code == 200
    assert "\r" not in r["Content-Disposition"] and "\n" not in r["Content-Disposition"]
    assert "Set-Cookie" not in r.headers


def test_preview_docx_et_pdf(
    api_client: APIClient,
    admin: User,
    gabarit_actif_test: GabaritDocument,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gabarits_service, "convertir_en_pdf", Mock(return_value=b"%PDF-1.7 apercu"))
    api_client.force_authenticate(admin)
    base = f"/api/v1/templates/{gabarit_actif_test.pk}/preview/"
    r = api_client.get(base + "?format=docx")
    assert r.status_code == 200 and "apercu-test_doc-v1.docx" in r["Content-Disposition"]
    r = api_client.get(base + "?format=pdf")
    assert r.status_code == 200 and octets(r).startswith(b"%PDF")
    assert r["Content-Type"] == "application/pdf"
    assert api_client.get(base + "?format=exe").status_code == 400


def test_template_altere_409(
    api_client: APIClient, admin: User, gabarit_actif_test: GabaritDocument
) -> None:
    chemin_fichier(gabarit_actif_test.fichier.name).write_bytes(b"altere")
    api_client.force_authenticate(admin)
    r = api_client.get(f"/api/v1/templates/{gabarit_actif_test.pk}/file/")
    assert r.status_code == 409 and "altéré" in r.json()["detail"] and r.json()["errors"] == {}


def test_listes_requetes_bornees(
    api_client: APIClient,
    admin: User,
    gabarit_actif_test: GabaritDocument,
    django_assert_max_num_queries: Any,
) -> None:
    api_client.force_authenticate(admin)
    with django_assert_max_num_queries(3):
        assert api_client.get("/api/v1/templates/").status_code == 200
    with django_assert_max_num_queries(4):
        r = api_client.get("/api/v1/document-types/")
    assert r.status_code == 200


def test_document_types_contenu(
    api_client: APIClient, admin: User, gabarit_actif_test: GabaritDocument
) -> None:
    api_client.force_authenticate(admin)
    corps = api_client.get("/api/v1/document-types/").json()
    t = next(x for x in corps if x["code"] == "TEST_DOC")
    assert t["etape"] is None and t["etape_romain"] is None and t["contrat_version"] == 1
    assert t["gabarit_actif"]["version"] == 1 and t["gabarit_actif"]["provisoire"] is False
    assert {c["nom"] for c in t["champs"]} >= {"onea", "document", "mission", "equipe"}
    equipe = next(c for c in t["champs"] if c["nom"] == "equipe")
    assert {e["nom"] for e in equipe["enfants"]} == {"nom", "role"}
    assert t["format_numerotation"]["apercu"] == "DAI/2026/M07/TD-01"
