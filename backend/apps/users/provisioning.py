"""Pre-provisioning of accounts before their first login (D12).

Two sources: the Keycloak directory and a CSV file. Both run in ONE transaction under the
audit actor and can be rolled back (`dry_run`): the dry run executes the very same code,
so its report is identical to the real one.

Security rules: a CSV can never create an `ADMIN` (that role is only granted in the
directory), never creates `is_staff` / `is_superuser` accounts, and created accounts have
an unusable password. Directory imports reuse the login matching (`filter_users_by_claims`
/ `update_user`): `is_active` is never touched and a locally managed profile is respected.
"""

import csv
import io
import logging
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction

from apps.core.audit import actor_scope

from . import keycloak_admin
from .keycloak_admin import KeycloakIntrouvable
from .models import OrigineCompte, Role, User
from .oidc import OneaOIDCBackend
from .services import DIRECTION_INCONNUE, MATRICULE_PRIS, direction_existe

logger = logging.getLogger(__name__)

CSV_ROLE_ADMIN = "Le rôle ADMIN ne s'attribue que dans l'annuaire (Keycloak)."
CSV_DOUBLON_FICHIER = "Identifiant ou e-mail en doublon dans le fichier."
CSV_COMPTE_EXISTANT = "Un compte existe déjà avec cet identifiant ou cet e-mail."
IDENTIFIANT_PRIS = "Identifiant déjà utilisé par un autre compte."
CSV_IDENTIFIANT_INVALIDE = "Identifiant invalide : lettres, chiffres et @ . + - _ uniquement."
CSV_IDENTIFIANT_MANQUANT = "Identifiant manquant."
CSV_EMAIL_INVALIDE = "Adresse e-mail invalide."
CSV_ROLE_INCONNU = "Rôle inconnu : valeurs admises AUDITE, AUDITEUR, RAI, DG."
CSV_VALEUR_TROP_LONGUE = "Valeur trop longue pour la colonne « {colonne} » (maximum {limite})."
KEYCLOAK_INTROUVABLE = "Compte introuvable dans Keycloak."
ANNUAIRE_COMPTE_SERVICE = "Compte de service : non importé."
ANNUAIRE_COMPTE_DESACTIVE = "Compte désactivé dans l'annuaire : non importé."
ANNUAIRE_ID_INVALIDE = "Identifiant Keycloak invalide."
CSV_CARACTERES_INTERDITS = "Caractères non autorisés dans la colonne « {colonne} »."
ANNUAIRE_IDENTIFIANT_MANQUANT = "Identifiant manquant dans l'annuaire."

CSV_MAX_BYTES = 1024 * 1024
CSV_MAX_ROWS = 1000
CSV_ROLES = {Role.AUDITE.value, Role.AUDITEUR.value, Role.RAI.value, Role.DG.value}
_CSV_LIMITES = {
    "identifiant": 150,
    "email": 254,
    "prenom": 150,
    "nom": 150,
    "matricule": 32,
    "fonction": 128,
}
_username_validator = UnicodeUsernameValidator()
_CONTROLE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_FORMULE = re.compile(r"^[=+\-@]")
_TEXTE_LIBRE = ("prenom", "nom", "matricule", "fonction")
_ECHO_MAX = 150


def _affichable(valeur: str) -> str:
    """Make an untrusted value safe to echo in a report: no control chars, bounded size."""
    propre = _CONTROLE.sub("", valeur)
    return propre if len(propre) <= _ECHO_MAX else propre[:_ECHO_MAX] + "…"


class FichierImportInvalide(Exception):
    """The uploaded file cannot be read at all (400). `message` is French."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class LigneIgnoree:
    ligne: int | None
    identifiant: str
    motif: str

    def __post_init__(self) -> None:
        self.identifiant = _affichable(self.identifiant)


@dataclass
class RapportImport:
    dry_run: bool
    crees: list[str] = field(default_factory=list)
    mis_a_jour: list[str] = field(default_factory=list)
    ignores: list[LigneIgnoree] = field(default_factory=list)


@dataclass
class EntreeAnnuaire:
    keycloak_id: UUID
    username: str
    email: str
    nom_complet: str
    direction: str
    fonction: str
    compte_id: int | None


# --------------------------------------------------------------------------- directory


def _attribut(rep: dict[str, Any], name: str) -> str:
    attributes = rep.get("attributes")
    value = attributes.get(name) if isinstance(attributes, dict) else None
    if isinstance(value, list):
        value = value[0] if value else ""
    return value.strip() if isinstance(value, str) else ""


def claims_depuis_keycloak(rep: dict[str, Any], roles: set[str]) -> dict[str, Any]:
    """Build the OIDC-style claims of a Keycloak user representation."""

    def text(key: str) -> str:
        value = rep.get(key)
        return value.strip() if isinstance(value, str) else ""

    return {
        "sub": text("id"),
        "preferred_username": text("username"),
        "email": text("email"),
        "email_verified": rep.get("emailVerified") is True,
        "given_name": text("firstName"),
        "family_name": text("lastName"),
        "direction": _attribut(rep, "direction"),
        "fonction": _attribut(rep, "fonction"),
        "roles": sorted(roles),
    }


def rechercher_annuaire(q: str) -> list[EntreeAnnuaire]:
    """Search the directory (at most 20 hits) and flag the already known accounts."""
    backend = OneaOIDCBackend()
    entrees: list[EntreeAnnuaire] = []
    for rep in keycloak_admin.get_keycloak_admin().search_users(q, max_results=20):
        claims = claims_depuis_keycloak(rep, set())
        try:
            keycloak_id = UUID(claims["sub"])
        except ValueError:
            continue
        compte = backend.filter_users_by_claims(claims).first()
        entrees.append(
            EntreeAnnuaire(
                keycloak_id=keycloak_id,
                username=claims["preferred_username"],
                email=claims["email"],
                nom_complet=f"{claims['given_name']} {claims['family_name']}".strip()
                or claims["preferred_username"],
                direction=claims["direction"],
                fonction=claims["fonction"],
                compte_id=compte.pk if compte is not None else None,
            )
        )
    return entrees


@dataclass
class _EntreeLue:
    claims: dict[str, Any]
    desactive: bool
    service: bool


def _lire_annuaire(keycloak_ids: list[UUID] | None, rapport: RapportImport) -> list[_EntreeLue]:
    """Fetch the representations and effective roles (network, outside any transaction)."""
    kc = keycloak_admin.get_keycloak_admin()
    reps: list[dict[str, Any]] = []
    if keycloak_ids is None:
        reps = list(kc.iter_users())
    else:
        for keycloak_id in dict.fromkeys(keycloak_ids):
            try:
                reps.append(kc.get_user(keycloak_id))
            except KeycloakIntrouvable:
                rapport.ignores.append(LigneIgnoree(None, str(keycloak_id), KEYCLOAK_INTROUVABLE))
    lues: list[_EntreeLue] = []
    for rep in reps:
        nom = str(rep.get("username") or rep.get("id") or "")
        try:
            keycloak_id = UUID(str(rep.get("id")))
        except ValueError:
            rapport.ignores.append(LigneIgnoree(None, nom, ANNUAIRE_ID_INVALIDE))
            continue
        try:
            roles = kc.effective_realm_roles(keycloak_id)
        except KeycloakIntrouvable:
            rapport.ignores.append(LigneIgnoree(None, nom, KEYCLOAK_INTROUVABLE))
            continue
        lues.append(
            _EntreeLue(
                claims=claims_depuis_keycloak(rep, roles),
                desactive=rep.get("enabled") is False,
                service=bool(rep.get("serviceAccountClientId"))
                or nom.startswith("service-account-"),
            )
        )
    return lues


def _importer_entree(backend: OneaOIDCBackend, entree: _EntreeLue, rapport: RapportImport) -> None:
    claims = entree.claims
    username = claims["preferred_username"]
    if entree.service:
        rapport.ignores.append(LigneIgnoree(None, username, ANNUAIRE_COMPTE_SERVICE))
        return
    existant = backend.filter_users_by_claims(claims).first()
    if existant is not None:
        ancien_role = existant.role
        backend.update_user(existant, claims)
        libelle = existant.username
        if existant.role != ancien_role:
            libelle += f" (rôle {ancien_role} → {existant.role})"
        rapport.mis_a_jour.append(libelle)
        return
    if entree.desactive:
        rapport.ignores.append(LigneIgnoree(None, username, ANNUAIRE_COMPTE_DESACTIVE))
        return
    if not username:
        rapport.ignores.append(LigneIgnoree(None, claims["sub"], ANNUAIRE_IDENTIFIANT_MANQUANT))
        return
    if User.objects.filter(username__iexact=username).exists():
        rapport.ignores.append(LigneIgnoree(None, username, IDENTIFIANT_PRIS))
        return
    user = User(
        username=username[:150],
        origine=OrigineCompte.ANNUAIRE,
        is_active=True,
        **backend._claim_values(claims),
    )
    user.set_unusable_password()
    try:
        with transaction.atomic():
            user.save()
    except IntegrityError:
        rapport.ignores.append(LigneIgnoree(None, username, IDENTIFIANT_PRIS))
        return
    rapport.crees.append(user.username)


def importer_depuis_annuaire(
    keycloak_ids: list[UUID] | None, *, by: User | None, dry_run: bool
) -> RapportImport:
    """Import the selected directory users (`None` = the whole directory).

    `KeycloakIndisponible` / `KeycloakNonConfigure` propagate; nothing is written then.
    """
    rapport = RapportImport(dry_run=dry_run)
    entrees = _lire_annuaire(keycloak_ids, rapport)
    backend = OneaOIDCBackend()
    with transaction.atomic(), actor_scope(by):
        for entree in entrees:
            _importer_entree(backend, entree, rapport)
        if dry_run:
            transaction.set_rollback(True)
    return rapport


# ------------------------------------------------------------------------------- CSV


def _lire_csv(contenu: bytes) -> tuple[list[str], list[tuple[int, list[str]]]]:
    if len(contenu) > CSV_MAX_BYTES:
        raise FichierImportInvalide("Le fichier dépasse 1 Mo.")
    try:
        texte = contenu.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise FichierImportInvalide("Le fichier doit être encodé en UTF-8.") from None
    premiere = texte.split("\n", 1)[0]
    delimiteur = ";" if premiere.count(";") >= premiere.count(",") else ","
    reader = csv.reader(io.StringIO(texte, newline=""), delimiter=delimiteur)
    try:
        entete = next(reader, [])
        colonnes = [c.strip().lower() for c in entete]
        if "identifiant" not in colonnes:
            raise FichierImportInvalide("En-tête invalide : colonne « identifiant » manquante.")
        lignes: list[tuple[int, list[str]]] = []
        for row in reader:
            if not any(cell.strip() for cell in row):
                continue
            if len(lignes) >= CSV_MAX_ROWS:
                raise FichierImportInvalide("Le fichier dépasse 1 000 lignes.")
            lignes.append((reader.line_num, row))
    except csv.Error:
        raise FichierImportInvalide("Le fichier n'est pas un CSV valide.") from None
    return colonnes, lignes


def _valider_ligne(valeurs: dict[str, str]) -> str | None:
    """Return the reason why a row is rejected, or None."""
    for colonne, limite in _CSV_LIMITES.items():
        if len(valeurs[colonne]) > limite:
            return CSV_VALEUR_TROP_LONGUE.format(colonne=colonne, limite=limite)
    for colonne in _TEXTE_LIBRE:
        valeur = valeurs[colonne]
        if _CONTROLE.search(valeur) or _FORMULE.match(valeur):
            return CSV_CARACTERES_INTERDITS.format(colonne=colonne)
    try:
        _username_validator(valeurs["identifiant"])
    except ValidationError:
        return CSV_IDENTIFIANT_INVALIDE
    if valeurs["email"]:
        try:
            validate_email(valeurs["email"])
        except ValidationError:
            return CSV_EMAIL_INVALIDE
    if valeurs["role"] == Role.ADMIN.value:
        return CSV_ROLE_ADMIN
    if valeurs["role"] not in CSV_ROLES:
        return CSV_ROLE_INCONNU
    if valeurs["direction"] and not direction_existe(valeurs["direction"]):
        return DIRECTION_INCONNUE
    return None


def importer_csv(contenu: bytes, *, by: User | None, dry_run: bool) -> RapportImport:
    colonnes, lignes = _lire_csv(contenu)
    rapport = RapportImport(dry_run=dry_run)
    noms = ("identifiant", "email", "prenom", "nom", "matricule", "direction", "fonction", "role")
    vus: set[str] = set()
    matricules: set[str] = set()
    with transaction.atomic(), actor_scope(by):
        for numero, row in lignes:
            cellules = {c: (row[i].strip() if i < len(row) else "") for i, c in enumerate(colonnes)}
            valeurs = {n: cellules.get(n, "") for n in noms}
            valeurs["role"] = valeurs["role"].upper() or Role.AUDITE.value
            identifiant = valeurs["identifiant"]
            motif = (
                _motif_refus(valeurs, vus, matricules) if identifiant else CSV_IDENTIFIANT_MANQUANT
            )
            if motif is None:
                motif = _creer_compte(valeurs, rapport)
            if motif is not None:
                rapport.ignores.append(LigneIgnoree(numero, identifiant, motif))
                continue
            vus.add(identifiant.lower())
            if valeurs["email"]:
                vus.add(valeurs["email"].lower())
            if valeurs["matricule"]:
                matricules.add(valeurs["matricule"])
        if dry_run:
            transaction.set_rollback(True)
    return rapport


def _motif_refus(valeurs: dict[str, str], vus: set[str], matricules: set[str]) -> str | None:
    motif = _valider_ligne(valeurs)
    if motif is not None:
        return motif
    identifiant, email, matricule = valeurs["identifiant"], valeurs["email"], valeurs["matricule"]
    if identifiant.lower() in vus or (email and email.lower() in vus):
        return CSV_DOUBLON_FICHIER
    if User.objects.filter(username__iexact=identifiant).exists() or (
        email and User.objects.filter(email__iexact=email).exists()
    ):
        return CSV_COMPTE_EXISTANT
    if matricule and (matricule in matricules or User.objects.filter(matricule=matricule).exists()):
        return MATRICULE_PRIS
    return None


def _creer_compte(valeurs: dict[str, str], rapport: RapportImport) -> str | None:
    """Create the account; returns a rejection reason if a concurrent write won."""
    if valeurs["role"] not in CSV_ROLES:  # defence in depth: never grant ADMIN from a file
        raise ValueError("Unsupported CSV role")
    user = User(
        username=valeurs["identifiant"],
        email=valeurs["email"],
        first_name=valeurs["prenom"],
        last_name=valeurs["nom"],
        matricule=valeurs["matricule"],
        direction_code=valeurs["direction"],
        fonction=valeurs["fonction"],
        role=valeurs["role"],
        origine=OrigineCompte.CSV,
        role_provisoire=True,
        profil_gere_localement=bool(valeurs["direction"] or valeurs["fonction"]),
        is_active=True,
        is_staff=False,
        is_superuser=False,
    )
    user.set_unusable_password()
    try:
        with transaction.atomic():
            user.save()
    except IntegrityError:
        pris = valeurs["matricule"] and User.objects.filter(matricule=valeurs["matricule"]).exists()
        return MATRICULE_PRIS if pris else CSV_COMPTE_EXISTANT
    rapport.crees.append(user.username)
    return None
