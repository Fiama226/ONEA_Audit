"""Frozen JSON contract of the account API (copied verbatim into the T6 MSW fixtures)."""

import io
import json
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.users.keycloak_admin import KeycloakRefus
from apps.users.models import User
from apps.users.provisioning import importer_csv

from ..conftest import FakeKeycloakAdmin

ENTETE = "identifiant;email;prenom;nom;matricule;direction;fonction;role\n"


def test_contrat_compte_utilisateur(
    api_client: APIClient, admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    importer_csv(
        (ENTETE + "kabore.l;l.kabore@onea.bf;Landry;Kabore;M-042;;Auditeur;AUDITEUR\n").encode(),
        by=admin,
        dry_run=False,
        envoyer_courriel=False,
    )
    cible = User.objects.get(username="kabore.l")
    cible.keycloak_id = fake_keycloak.add_user("kabore.l")
    cible.save(update_fields=["keycloak_id"])
    fake_keycloak.fail_with(KeycloakRefus("Keycloak a refusé l'opération (HTTP 403).", 403))
    api_client.force_authenticate(admin)
    r = api_client.post(
        f"/api/v1/user-accounts/{cible.id}/deactivate/", {"motif": "Départ"}, format="json"
    )
    assert r.status_code == 200
    data = r.json()
    # Volatile values are normalised so that the contract is deterministic.
    for cle in ("date_joined", "desactive_le", "mot_de_passe_expire_le"):
        assert data.pop(cle)
    assert data["keycloak_sync"].pop("derniere_tentative_le")
    attendu: dict[str, Any] = {
        "id": cible.id,
        "username": "kabore.l",
        "nom_complet": "Landry Kabore",
        "email": "l.kabore@onea.bf",
        "role": "AUDITEUR",
        "direction_code": "",
        "direction_libelle": None,
        "fonction": "Auditeur",
        "matricule": "M-042",
        "is_active": False,
        "origine": "CSV",
        "en_attente_connexion": True,
        "keycloak_sync_statut": "ECHEC",
        "first_name": "Landry",
        "last_name": "Kabore",
        "keycloak_lie": True,
        "role_provisoire": False,
        "premiere_connexion_le": None,
        "profil_gere_localement": True,
        "desactive_par": {
            "id": admin.id,
            "username": admin.username,
            "nom_complet": admin.nom_complet,
        },
        "motif_desactivation": "Départ",
        "doit_changer_mot_de_passe": True,
        "verrouille_jusqu_a": None,
        "otp_connexion_actif": False,
        "keycloak_sync": {
            "statut": "ECHEC",
            "erreur": "Keycloak a refusé l'opération (HTTP 403).",
            "tentatives": 1,
            "manuel": True,
        },
        "actions": {
            "modifier_profil": True,
            "desactiver": False,
            "reactiver": True,
            "resynchroniser_profil": True,
            "relancer_synchro_keycloak": True,
            "reinitialiser_mot_de_passe": False,
            "desactiver_otp": False,
            "modifier_courriel": True,
            "modifier_direction": True,
            "changer_role": True,
        },
    }
    assert data == attendu


def test_contrat_rapport_import(api_client: APIClient, admin: User) -> None:
    api_client.force_authenticate(admin)
    contenu = ENTETE + "a.b;a@onea.bf;;;;;;AUDITEUR\nchef;;;;;;;ADMIN\n"
    fichier = SimpleUploadedFile("c.csv", contenu.encode(), content_type="text/csv")
    r = api_client.post(
        "/api/v1/user-accounts/import-csv/", {"fichier": fichier}, format="multipart"
    )
    assert r.status_code == 200
    assert r.json() == {
        "dry_run": True,
        "crees": ["a.b"],
        "mis_a_jour": [],
        "ignores": [
            {
                "ligne": 3,
                "identifiant": "chef",
                "motif": (
                    "Le rôle ADMIN ne s'attribue pas par import : créez le compte, puis "
                    "changez son rôle."
                ),
            }
        ],
        "fichier_mots_de_passe_id": None,
    }


@pytest.mark.django_db
def test_schema_expose_user_accounts_sans_collision() -> None:
    out = io.StringIO()
    call_command(
        "spectacular",
        "--validate",
        "--fail-on-warn",
        "--format",
        "openapi-json",
        urlconf="config.urls",
        stdout=out,
    )
    schema = json.loads(out.getvalue())
    paths = schema["paths"]
    for p in (
        "/api/v1/user-accounts/",
        "/api/v1/user-accounts/{id}/",
        "/api/v1/user-accounts/{id}/deactivate/",
        "/api/v1/user-accounts/{id}/reactivate/",
        "/api/v1/user-accounts/{id}/resync-profile/",
        "/api/v1/user-accounts/{id}/retry-keycloak-sync/",
        "/api/v1/user-accounts/{id}/reset-password/",
        "/api/v1/user-accounts/{id}/disable-otp/",
        "/api/v1/user-accounts/{id}/change-role/",
        "/api/v1/user-accounts/{id}/delegation/",
        "/api/v1/user-accounts/directory-search/",
        "/api/v1/user-accounts/import-directory/",
        "/api/v1/user-accounts/import-csv/",
        "/api/v1/user-accounts/import-passwords/{fichier_id}/",
    ):
        assert p in paths, p
    composants = schema["components"]["schemas"]
    for nom in (
        "CompteUtilisateur",
        "CompteUtilisateurListe",
        "PaginatedCompteUtilisateurListeList",
        "PatchedProfilUtilisateurRequest",
        "MotifDesactivationRequest",
        "CreationCompteRequest",
        "ReinitialisationCompteRequest",
        "MotDePasseTemporaire",
        "ImportAnnuaireRequest",
        "ImportCsvRequest",
        "RapportImport",
        "LigneImportIgnoree",
        "EntreeAnnuaire",
        "SyncKeycloak",
        "ActionsCompte",
        "ChangementRoleRequest",
        "DelegationGestionComptes",
        "DelegationGestionComptesRequest",
        "DroitsGestionComptes",
        "KeycloakSyncStatutEnum",
        "OrigineCompteEnum",
    ):
        assert nom in composants, nom
    assert "manuel" in composants["SyncKeycloak"]["properties"]
