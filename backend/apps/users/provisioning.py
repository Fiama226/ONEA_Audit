"""Pre-provisioning of accounts from a CSV file (D12).

The import runs in ONE transaction under the audit actor and can be rolled back (`dry_run`):
the dry run executes the very same checks, so its report is identical to the real one.

Every created account is a local one, with a temporary password (72 h, to be
changed at the first login), validated like the creation form (`services`: role required,
no "@" in the username, neither the username nor the email may shadow another account's).
Every password is first stored, encrypted, in a `FichierMotsDePasse` in the transaction
that creates the accounts; after the commit each one goes out in a welcome email when
sending is on, and the file keeps only the ones no email carried. Only the importer may
download it, once, within 24 h. A dry run creates, sends and stores nothing. A CSV never
creates an `ADMIN` (create the account, then change its role) nor `is_staff` /
`is_superuser` accounts. A password never reaches the audit trail or the logs.
"""

import base64
import csv
import io
import logging
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import Http404
from django.utils import timezone
from django.utils.crypto import salted_hmac

from apps.core.audit import actor_scope
from apps.core.exceptions import RegleMetierError

from .auth_services import (
    envoi_courriel_actif,
    generer_mot_de_passe_temporaire,
    logger_securite,
)
from .courriels import envoyer_bienvenue
from .delegation import DROIT_REFUSE, exiger_administrateur
from .models import FichierMotsDePasse, OrigineCompte, Role, User
from .services import (
    ACTION_CREATION,
    MATRICULE_PRIS,
    _action_auditee,
    _poser_mot_de_passe_temporaire,
    _valeurs_creation,
    _verifier_disponibilite,
)

logger = logging.getLogger(__name__)

CSV_ROLE_ADMIN = (
    "Le rôle ADMIN ne s'attribue pas par import : créez le compte, puis changez son rôle."
)
CSV_DOUBLON_FICHIER = "Identifiant ou e-mail en doublon dans le fichier."
CSV_COMPTE_EXISTANT = "Un compte existe déjà avec cet identifiant ou cet e-mail."
CSV_IDENTIFIANT_INVALIDE = "Identifiant invalide : lettres, chiffres et . + - _ uniquement."
CSV_IDENTIFIANT_MANQUANT = "Identifiant manquant."
CSV_EMAIL_INVALIDE = "Adresse e-mail invalide."
CSV_ROLE_INCONNU = "Rôle inconnu : valeurs admises AUDITE, AUDITEUR, RAI, DG."
CSV_VALEUR_TROP_LONGUE = "Valeur trop longue pour la colonne « {colonne} » (maximum {limite})."
CSV_CARACTERES_INTERDITS = "Caractères non autorisés dans la colonne « {colonne} »."
FICHIER_AUTRE_AUTEUR = "Seul l'auteur de l'import peut télécharger ce fichier."

CSV_MAX_BYTES = 1024 * 1024
# Bounded so that hashing (about 60 ms per password) and the emails (time budget
# `DUREE_MAX_ENVOIS`) fit well within the 120 s request timeout (see `importer_csv`).
CSV_MAX_ROWS = 300
CSV_TROP_DE_LIGNES = (
    f"Le fichier dépasse {CSV_MAX_ROWS} lignes : découpez-le en plusieurs fichiers."
)
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
    ligne: int
    identifiant: str
    motif: str

    def __post_init__(self) -> None:
        self.identifiant = _affichable(self.identifiant)


@dataclass
class RapportImport:
    dry_run: bool
    crees: list[str] = field(default_factory=list)
    ignores: list[LigneIgnoree] = field(default_factory=list)
    # The one-time file of the passwords no email carried (CSV import, real run only).
    fichier_mots_de_passe_id: UUID | None = None


# ------------------------------------------------------------------------------- CSV

# CSV column -> account field, as validated by the creation service.
_CHAMP_COMPTE = {
    "identifiant": "username",
    "email": "email",
    "prenom": "first_name",
    "nom": "last_name",
    "matricule": "matricule",
    "direction": "direction_code",
    "fonction": "fonction",
    "role": "role",
}
CSV_COLONNES = tuple(_CHAMP_COMPTE)
DUREE_FICHIER_MOTS_DE_PASSE = timedelta(hours=24)
# Time budget for the welcome emails of one import; the rest go to the password file.
DUREE_MAX_ENVOIS = timedelta(seconds=60)
_SEL_FICHIER = "apps.users.provisioning.FichierMotsDePasse"
# Spreadsheet formula triggers (CSV injection): in the password file such a cell is
# prefixed with a single quote ON PURPOSE, so that a spreadsheet shows it as text and
# never evaluates it. The quote is not part of the identifier or the address.
_DEBUT_FORMULE = ("=", "+", "-", "@", "\t", "\r")


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
                raise FichierImportInvalide(CSV_TROP_DE_LIGNES)
            lignes.append((reader.line_num, row))
    except csv.Error:
        raise FichierImportInvalide("Le fichier n'est pas un CSV valide.") from None
    return colonnes, lignes


def _valider_ligne(valeurs: dict[str, str]) -> str | None:
    """File-level checks (sizes, characters, formats, roles a file may grant), or None."""
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
    if valeurs["role"] and valeurs["role"] not in CSV_ROLES:
        return CSV_ROLE_INCONNU
    return None


def _motif(exc: RegleMetierError) -> str:
    """The rejection reason of a row, from the creation service's field errors."""
    messages = [m for erreurs in exc.errors.values() for m in erreurs]
    return " ".join(messages) or exc.message


def _preparer(valeurs: dict[str, str], vus: set[str], matricules: set[str]) -> dict[str, str] | str:
    """The account fields of a valid row, or the reason why the row is rejected.

    Same rules as the creation form (`services`): role required, no "@" in the username,
    the username and the email must not be any account's username or email (login resolves
    both), matricule unique, direction known.
    """
    if not valeurs["identifiant"]:
        return CSV_IDENTIFIANT_MANQUANT
    motif = _valider_ligne(valeurs)
    if motif is not None:
        return motif
    try:
        donnees = _valeurs_creation({_CHAMP_COMPTE[c]: v for c, v in valeurs.items() if v})
    except RegleMetierError as exc:
        return _motif(exc)
    email, matricule = donnees.get("email", ""), donnees.get("matricule", "")
    if donnees["username"].lower() in vus or (email and email.lower() in vus):
        return CSV_DOUBLON_FICHIER
    if matricule and matricule in matricules:
        return MATRICULE_PRIS
    try:
        _verifier_disponibilite(donnees)
    except RegleMetierError as exc:
        return _motif(exc)
    return donnees


def _creer_compte(
    donnees: Mapping[str, str], *, dry_run: bool, maintenant: datetime
) -> tuple[User, str] | str:
    """Create the account; returns it with its temporary password, or the rejection reason
    when a concurrent write won. The dry run (rolled back) skips the costly hashing."""
    if donnees["role"] not in CSV_ROLES:  # defence in depth: never grant ADMIN from a file
        raise ValueError("Unsupported CSV role")
    user = User(
        **donnees,
        origine=OrigineCompte.CSV,
        profil_gere_localement=bool(donnees.get("direction_code") or donnees.get("fonction")),
        is_active=True,
        is_staff=False,
        is_superuser=False,
    )
    mot_de_passe = ""
    if dry_run:
        user.set_unusable_password()
    else:
        mot_de_passe = generer_mot_de_passe_temporaire()
        _poser_mot_de_passe_temporaire(user, mot_de_passe, maintenant)
    with _action_auditee(user, ACTION_CREATION):
        try:
            with transaction.atomic():
                user.save()
        except IntegrityError:
            matricule = donnees.get("matricule", "")
            pris = matricule and User.objects.filter(matricule=matricule).exists()
            return MATRICULE_PRIS if pris else CSV_COMPTE_EXISTANT
    return user, mot_de_passe


def _verifier_importateur(by: User) -> None:
    """Re-check the importer's right under a lock on its row (like `creer_compte`): an
    active ADMIN, or a command's system actor (`delegation.acteur_systeme`)."""
    list(User.objects.select_for_update(no_key=True).filter(pk=by.pk))
    exiger_administrateur(by, DROIT_REFUSE)


def _envoyer_courriels(crees: list[tuple[User, str]], envoyer: bool) -> set[int]:
    """Send the welcome emails; returns the pks of the accounts actually emailed.

    Stops at the first failed send (SMTP down: every later one would wait for its timeout
    too) and once the time budget is spent: the remaining passwords stay in the file.
    """
    envoyes: set[int] = set()
    if not envoyer or not envoi_courriel_actif():
        return envoyes
    limite = time.monotonic() + DUREE_MAX_ENVOIS.total_seconds()
    for user, mot_de_passe in crees:
        if not user.email:
            continue
        if time.monotonic() >= limite:
            logger_securite.warning(
                "Import CSV : courriels de bienvenue arrêtés (durée maximale atteinte)."
            )
            break
        if not envoyer_bienvenue(user, mot_de_passe):
            logger_securite.warning(
                "Import CSV : courriels de bienvenue arrêtés au premier échec d'envoi."
            )
            break
        envoyes.add(user.pk)
    return envoyes


def importer_csv(
    contenu: bytes, *, by: User | None, dry_run: bool, envoyer_courriel: bool
) -> RapportImport:
    """Create the valid rows as local accounts; each rejected row is reported, the others
    are still created. ``by`` is required for a real run (audit actor, file owner) and must
    be an active ADMIN (or the system actor of a command).

    No password can be lost: every one goes, encrypted, into the one-time file in the very
    transaction that creates the accounts. The welcome emails go out after the commit; the
    file is then cut down to the passwords no email carried (deleted when none remain). A
    crash, a timeout or an SMTP failure while emailing leaves the full file behind.
    """
    if by is None and not dry_run:
        raise ValueError("A real CSV import needs an actor")
    colonnes, lignes = _lire_csv(contenu)
    rapport = RapportImport(dry_run=dry_run)
    vus: set[str] = set()
    matricules: set[str] = set()
    crees: list[tuple[User, str]] = []
    fichier_id: UUID | None = None
    maintenant = timezone.now()
    with transaction.atomic(), actor_scope(by):
        if by is not None:
            _verifier_importateur(by)
        for numero, row in lignes:
            cellules = {c: (row[i].strip() if i < len(row) else "") for i, c in enumerate(colonnes)}
            valeurs = {n: cellules.get(n, "") for n in CSV_COLONNES}
            valeurs["role"] = valeurs["role"].upper()
            donnees = _preparer(valeurs, vus, matricules)
            cree = (
                _creer_compte(donnees, dry_run=dry_run, maintenant=maintenant)
                if isinstance(donnees, dict)
                else donnees
            )
            if isinstance(cree, str):
                rapport.ignores.append(LigneIgnoree(numero, valeurs["identifiant"], cree))
                continue
            user, mot_de_passe = cree
            crees.append((user, mot_de_passe))
            rapport.crees.append(user.username)
            vus.add(user.username.lower())
            if user.email:
                vus.add(user.email.lower())
            if user.matricule:
                matricules.add(user.matricule)
        if dry_run:
            transaction.set_rollback(True)
        elif by is not None and crees:
            fichier_id = _stocker_fichier(crees, par=by)
    if dry_run or by is None:
        return rapport
    if fichier_id is not None:
        # Before any email: the id lets an operator find the file if the request dies.
        logger_securite.info(
            "Import CSV : fichier de mots de passe enregistré : fichier=%s par=%s comptes=%s",
            fichier_id,
            by.pk,
            len(crees),
        )
    envoyes = _envoyer_courriels(crees, envoyer_courriel)
    restants = [(user, mdp) for user, mdp in crees if user.pk not in envoyes]
    if fichier_id is not None:
        rapport.fichier_mots_de_passe_id = (
            _reduire_fichier(fichier_id, restants) if envoyes else fichier_id
        )
    logger_securite.info(
        "Import CSV de comptes : par=%s comptes_crees=%s courriels_envoyes=%s fichier=%s",
        by.pk,
        len(crees),
        len(envoyes),
        rapport.fichier_mots_de_passe_id,
    )
    return rapport


# --------------------------------------------------------- one-time password file


def _fernet() -> Fernet:
    """Key derived from SECRET_KEY: a database dump alone never reveals a password."""
    cle = salted_hmac(_SEL_FICHIER, "fichier-mots-de-passe", algorithm="sha256").digest()
    return Fernet(base64.urlsafe_b64encode(cle))


def _cellule(valeur: str) -> str:
    return f"'{valeur}" if valeur.startswith(_DEBUT_FORMULE) else valeur


def _contenu_chiffre(comptes: list[tuple[User, str]]) -> bytes:
    sortie = io.StringIO()
    ecrivain = csv.writer(sortie, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow(["identifiant", "courriel", "mot_de_passe_temporaire", "valable_jusqu_au"])
    for user, mot_de_passe in comptes:
        expire = user.mot_de_passe_expire_le
        ecrivain.writerow(
            [
                # Leading quote on a formula-like cell: intentional (CSV injection).
                _cellule(user.username),
                _cellule(user.email),
                mot_de_passe,
                timezone.localtime(expire).strftime("%d/%m/%Y %H:%M") if expire else "",
            ]
        )
    # BOM: spreadsheet software then reads the file as UTF-8.
    texte = "\ufeff" + sortie.getvalue()
    return _fernet().encrypt(texte.encode("utf-8"))


def _stocker_fichier(comptes: list[tuple[User, str]], *, par: User) -> UUID:
    fichier = FichierMotsDePasse.objects.create(
        contenu=_contenu_chiffre(comptes),
        nombre_comptes=len(comptes),
        cree_par=par,
        expire_le=timezone.now() + DUREE_FICHIER_MOTS_DE_PASSE,
    )
    return fichier.pk


def _reduire_fichier(fichier_id: UUID, restants: list[tuple[User, str]]) -> UUID | None:
    """Keep only the passwords no email carried; delete the file when none remain."""
    with transaction.atomic():
        fichier = FichierMotsDePasse.objects.select_for_update().filter(pk=fichier_id).first()
        if fichier is None:
            return None
        if not restants:
            fichier.delete()
            return None
        fichier.contenu = _contenu_chiffre(restants)
        fichier.nombre_comptes = len(restants)
        fichier.save(update_fields=["contenu", "nombre_comptes"])
    return fichier_id


def lire_fichier_mots_de_passe(fichier_id: UUID, *, par: User) -> str:
    """Return the CSV text of the file and destroy it: one read only, by its importer.

    ``Http404`` when it does not exist (any more) or has expired (then destroyed too);
    ``PermissionDenied`` for anybody else than the importer (the file is kept).
    """
    with transaction.atomic():
        fichier = FichierMotsDePasse.objects.select_for_update().filter(pk=fichier_id).first()
        if fichier is None:
            raise Http404
        if fichier.cree_par_id != par.pk:
            raise PermissionDenied(FICHIER_AUTRE_AUTEUR)
        nombre = fichier.nombre_comptes
        expire = fichier.expire_le <= timezone.now()
        chiffre = bytes(fichier.contenu)
        fichier.delete()
    if expire:
        raise Http404
    try:
        texte = _fernet().decrypt(chiffre).decode("utf-8")
    except InvalidToken:  # SECRET_KEY changed since the import: unreadable, destroyed anyway
        logger_securite.warning("Fichier de mots de passe illisible : fichier=%s", fichier_id)
        raise Http404 from None
    logger_securite.info(
        "Fichier de mots de passe temporaires téléchargé : fichier=%s par=%s comptes=%s",
        fichier_id,
        par.pk,
        nombre,
    )
    return texte


def purger_fichiers_mots_de_passe() -> int:
    """Delete the expired password files nobody downloaded. Returns the number deleted."""
    supprimes, _ = FichierMotsDePasse.objects.filter(expire_le__lte=timezone.now()).delete()
    return supprimes
