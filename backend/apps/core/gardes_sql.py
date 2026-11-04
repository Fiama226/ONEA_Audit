"""Gel en base (lot 9, T10, décision D6) : fonctions, déclencheurs et droits du rôle applicatif.

Les gardes applicatives (`managers.py`, `gardes.py`) sont contournables par le SQL brut. Ce module
pose en base, de façon idempotente, un second verrou :

* `onea_refuser_suppression()` : `DELETE` refusé sur toute table d'un modèle `BaseModel` ;
* `onea_refuser_modification()` : tables en ajout seul, `UPDATE` et `DELETE` refusés ;
* `onea_colonnes_immuables()` / `onea_colonnes_modifiables()` / `onea_ecriture_unique()` : colonnes
  figées (empreintes, clés de stockage...), éventuellement sous condition d'état (`statut=PRETE`) ;
* `onea_refuser_si_fige()` : ligne d'une cartographie ou d'un programme validé, ou rattachée à une
  telle ligne ; `onea_refuser_entites_figees()` : liaison des entités d'une ligne de programme.

Tous les refus lèvent `ERREUR ONEA : <règle>` (SQLSTATE `P0001`). Contournement de maintenance :
`SET LOCAL onea.maintenance = 'on'`, honoré seulement si l'utilisateur courant est le
propriétaire de la table (ou un superutilisateur) ; le rôle applicatif (`onea_app`) n'en tire
aucun effet.

Les gels qui dépendent de l'état d'une mission (suspendue, étape close, rapport diffusé...) restent
applicatifs : ils admettent des exceptions légitimes (`reprendre`, réouverture...).

L'installateur est appelé par la migration `core.0002_fonctions_gardes` (fonctions), par un
récepteur `post_migrate` (déclencheurs et droits, après chaque migration) et par la commande
`manage.py installer_gardes_sql`.
"""

import hashlib
import os
import re
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from django.apps import apps
from django.db import DEFAULT_DB_ALIAS, connections, transaction
from django.db.backends.base.base import BaseDatabaseWrapper

from .models import BaseModel

ROLE_APPLICATIF_DEFAUT = "onea_app"
PREFIXE = "onea_"
_IDENTIFIANT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ARGUMENT = re.compile(r"^[A-Za-z0-9_=]*$")

# --- Catégories de tables (D6) -------------------------------------------------------------

# (b) Ajout seul : UPDATE et DELETE refusés. Journaux d'événements, preuves, confirmations,
# diffusions, instantanés, réponses et avis déposés des lots 1 à 8.
TABLES_AJOUT_SEUL: frozenset[str] = frozenset(
    {
        "signatures.confirmation",
        "missions.evenementetape",
        "auditlog.logentry",
        "core.consultation",
        "documents.consultationdocument",
        "accomplissement.evenementfiche",
        "accomplissement.instantaneprogramme",
        "analyse.avisaudite",
        "constats.reponseaudite",
        "constats.evenementconstat",
        "communication.rapportprovisoire",
        "communication.reponserapport",
        "communication.diffusion",
        "communication.evenementrapport",
        "recommandations.engagementplanactions",
        "suivi.evenementsuivi",
    }
)

# (c) Données d'identification transitoires (authentification interne) : DELETE accordé au rôle
# applicatif. Codes à usage unique, mots de passe temporaires en attente d'envoi, fichiers de
# mots de passe d'un import : supprimés à l'usage et par la purge quotidienne, par conception.
# Aucune n'est un `BaseModel` (aucun déclencheur de suppression ne les vise : contrôlé par
# `tables_transitoires`).
TABLES_TRANSITOIRES: frozenset[str] = frozenset(
    {"users.codeotp", "users.envoimotdepasse", "users.fichiermotsdepasse"}
)

NOM_SUPPRESSION = "onea_refuser_suppression"
NOM_MODIFICATION = "onea_refuser_modification"
NOM_IMMUABLES = "onea_colonnes_immuables"
NOM_MODIFIABLES = "onea_colonnes_modifiables"
NOM_UNIQUE = "onea_ecriture_unique"
NOM_FIGE = "onea_refuser_si_fige"
NOM_ENTITES = "onea_refuser_entites_figees"

# --- Fonctions PL/pgSQL --------------------------------------------------------------------
# `@S@` : schéma. `search_path = pg_catalog` : un objet homonyme créé dans un autre schéma ne
# peut pas détourner les fonctions. Aucun SECURITY DEFINER : l'utilisateur courant reste celui
# de l'appelant, ce que le contrôle du propriétaire exige.

_MESSAGE = "ERREUR ONEA : "

SQL_FONCTIONS = """
CREATE OR REPLACE FUNCTION @S@.onea_maintenance_autorisee(relid oid) RETURNS boolean
LANGUAGE sql STABLE SET search_path = pg_catalog
AS $f$
  SELECT coalesce(pg_catalog.current_setting('onea.maintenance', true), '') = 'on'
     AND pg_catalog.pg_has_role(
           current_user,
           (SELECT c.relowner FROM pg_catalog.pg_class c WHERE c.oid = relid),
           'USAGE')
$f$;

CREATE OR REPLACE FUNCTION @S@.onea_refuser_suppression() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog
AS $f$
BEGIN
  IF @S@.onea_maintenance_autorisee(TG_RELID) THEN
    RETURN OLD;
  END IF;
  RAISE EXCEPTION '@M@suppression physique interdite sur la table % (suppression logique).',
    TG_TABLE_NAME USING ERRCODE = 'P0001';
END
$f$;

CREATE OR REPLACE FUNCTION @S@.onea_refuser_modification() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog
AS $f$
BEGIN
  IF @S@.onea_maintenance_autorisee(TG_RELID) THEN
    IF TG_OP = 'DELETE' THEN
      RETURN OLD;
    END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION '@M@la table % est en ajout seul : % interdit.',
    TG_TABLE_NAME, TG_OP USING ERRCODE = 'P0001';
END
$f$;

CREATE OR REPLACE FUNCTION @S@.onea_colonnes_immuables() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog
AS $f$
DECLARE
  anc jsonb := pg_catalog.to_jsonb(OLD);
  nou jsonb := pg_catalog.to_jsonb(NEW);
  cond text := TG_ARGV[0];
  cle text;
  val text;
  i integer;
BEGIN
  IF @S@.onea_maintenance_autorisee(TG_RELID) THEN
    RETURN NEW;
  END IF;
  IF cond <> '' THEN
    cle := pg_catalog.split_part(cond, '=', 1);
    val := pg_catalog.substr(cond, pg_catalog.length(cle) + 2);
    IF anc ->> cle IS DISTINCT FROM val THEN
      RETURN NEW;
    END IF;
  END IF;
  FOR i IN 1 .. TG_NARGS - 1 LOOP
    IF anc -> TG_ARGV[i] IS DISTINCT FROM nou -> TG_ARGV[i] THEN
      RAISE EXCEPTION '@M@la colonne % de la table % est immuable.',
        TG_ARGV[i], TG_TABLE_NAME USING ERRCODE = 'P0001';
    END IF;
  END LOOP;
  RETURN NEW;
END
$f$;

CREATE OR REPLACE FUNCTION @S@.onea_colonnes_modifiables() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog
AS $f$
DECLARE
  anc jsonb := pg_catalog.to_jsonb(OLD);
  nou jsonb := pg_catalog.to_jsonb(NEW);
  cond text := TG_ARGV[0];
  cle text;
  val text;
  permis text[];
BEGIN
  IF @S@.onea_maintenance_autorisee(TG_RELID) THEN
    RETURN NEW;
  END IF;
  IF cond <> '' THEN
    cle := pg_catalog.split_part(cond, '=', 1);
    val := pg_catalog.substr(cond, pg_catalog.length(cle) + 2);
    IF anc ->> cle IS DISTINCT FROM val THEN
      RETURN NEW;
    END IF;
  END IF;
  permis := ARRAY(
    SELECT a FROM pg_catalog.unnest(TG_ARGV) WITH ORDINALITY AS t(a, n) WHERE n > 1
  );
  IF (anc - permis) IS DISTINCT FROM (nou - permis) THEN
    RAISE EXCEPTION '@M@seules les colonnes (%) de la table % sont modifiables.',
      pg_catalog.array_to_string(permis, ', '), TG_TABLE_NAME USING ERRCODE = 'P0001';
  END IF;
  RETURN NEW;
END
$f$;

CREATE OR REPLACE FUNCTION @S@.onea_ecriture_unique() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog
AS $f$
DECLARE
  anc jsonb := pg_catalog.to_jsonb(OLD);
  nou jsonb := pg_catalog.to_jsonb(NEW);
  cond text := TG_ARGV[0];
  cle text;
  val text;
  actuel text;
  i integer;
BEGIN
  IF @S@.onea_maintenance_autorisee(TG_RELID) THEN
    RETURN NEW;
  END IF;
  IF cond <> '' THEN
    cle := pg_catalog.split_part(cond, '=', 1);
    val := pg_catalog.substr(cond, pg_catalog.length(cle) + 2);
    IF anc ->> cle IS DISTINCT FROM val THEN
      RETURN NEW;
    END IF;
  END IF;
  FOR i IN 1 .. TG_NARGS - 1 LOOP
    actuel := anc ->> TG_ARGV[i];
    IF actuel IS NOT NULL AND actuel <> ''
       AND anc -> TG_ARGV[i] IS DISTINCT FROM nou -> TG_ARGV[i] THEN
      RAISE EXCEPTION '@M@la colonne % de la table % est en écriture unique.',
        TG_ARGV[i], TG_TABLE_NAME USING ERRCODE = 'P0001';
    END IF;
  END LOOP;
  RETURN NEW;
END
$f$;

CREATE OR REPLACE FUNCTION @S@.onea_parent_fige(
  schema_ text, parent text, pk uuid, col text, gele text
) RETURNS boolean
LANGUAGE plpgsql STABLE SET search_path = pg_catalog
AS $f$
DECLARE
  etat text;
BEGIN
  IF pk IS NULL THEN
    RETURN false;
  END IF;
  EXECUTE pg_catalog.format('SELECT %I::text FROM %I.%I WHERE id = $1', col, schema_, parent)
    INTO etat USING pk;
  RETURN etat IS NOT DISTINCT FROM gele;
END
$f$;

CREATE OR REPLACE FUNCTION @S@.onea_refuser_si_fige() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog
AS $f$
DECLARE
  parent text := TG_ARGV[0];
  fk text := TG_ARGV[1];
  col text := TG_ARGV[2];
  gele text := TG_ARGV[3];
BEGIN
  IF @S@.onea_maintenance_autorisee(TG_RELID) THEN
    RETURN NEW;
  END IF;
  IF parent = 'self' THEN
    IF TG_OP = 'UPDATE' AND pg_catalog.to_jsonb(OLD) ->> col = gele THEN
      RAISE EXCEPTION '@M@ligne figée (état %) de la table %.',
        gele, TG_TABLE_NAME USING ERRCODE = 'P0001';
    END IF;
    RETURN NEW;
  END IF;
  IF (TG_OP = 'UPDATE' AND @S@.onea_parent_fige(
        TG_TABLE_SCHEMA, parent, (pg_catalog.to_jsonb(OLD) ->> fk)::uuid, col, gele))
     OR @S@.onea_parent_fige(
        TG_TABLE_SCHEMA, parent, (pg_catalog.to_jsonb(NEW) ->> fk)::uuid, col, gele) THEN
    RAISE EXCEPTION '@M@la table % est figée : son parent est à l''état %.',
      TG_TABLE_NAME, gele USING ERRCODE = 'P0001';
  END IF;
  RETURN NEW;
END
$f$;

CREATE OR REPLACE FUNCTION @S@.onea_ligne_programme_figee(ligne uuid) RETURNS boolean
LANGUAGE plpgsql STABLE SET search_path = pg_catalog
AS $f$
DECLARE
  figee boolean;
BEGIN
  SELECT coalesce(bool_or(p.statut = 'VALIDE'), false) INTO figee
    FROM @S@.programmation_ligneprogramme l
    JOIN @S@.programmation_programmeannuel p ON p.id = l.programme_id
   WHERE l.id = ligne;
  RETURN figee;
END
$f$;

CREATE OR REPLACE FUNCTION @S@.onea_refuser_entites_figees() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog
AS $f$
BEGIN
  IF @S@.onea_maintenance_autorisee(TG_RELID) THEN
    IF TG_OP = 'DELETE' THEN
      RETURN OLD;
    END IF;
    RETURN NEW;
  END IF;
  IF (TG_OP IN ('UPDATE', 'DELETE') AND @S@.onea_ligne_programme_figee(OLD.ligneprogramme_id))
     OR (TG_OP IN ('INSERT', 'UPDATE') AND @S@.onea_ligne_programme_figee(NEW.ligneprogramme_id))
  THEN
    RAISE EXCEPTION '@M@les entités d''une ligne de programme validé sont figées.'
      USING ERRCODE = 'P0001';
  END IF;
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END
$f$;
""".replace("@M@", _MESSAGE)

FONCTIONS = (
    "onea_maintenance_autorisee(oid)",
    f"{NOM_SUPPRESSION}()",
    f"{NOM_MODIFICATION}()",
    f"{NOM_IMMUABLES}()",
    f"{NOM_MODIFIABLES}()",
    f"{NOM_UNIQUE}()",
    "onea_parent_fige(text, text, uuid, text, text)",
    f"{NOM_FIGE}()",
    "onea_ligne_programme_figee(uuid)",
    f"{NOM_ENTITES}()",
)
_MARQUE = "onea-gardes:"
NOM_TABLE_REFERENCE = "django_migrations"  # propriétaire de référence : celui des migrations


# --- Déclencheurs --------------------------------------------------------------------------


@dataclass(frozen=True)
class Declencheur:
    table: str
    fonction: str  # le déclencheur porte le nom de sa fonction
    moment: str  # « DELETE », « UPDATE », « UPDATE OR DELETE », « INSERT OR UPDATE »
    arguments: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for argument in self.arguments:
            if not _ARGUMENT.match(argument):
                raise ValueError(f"Argument de déclencheur invalide : {argument!r}")

    @property
    def cle(self) -> tuple[str, str]:
        return (self.table, self.fonction)

    def sql(self, schema: str) -> str:
        args = ", ".join(f"'{a}'" for a in self.arguments)
        return (
            f'CREATE TRIGGER {self.fonction} BEFORE {self.moment} ON "{schema}"."{self.table}" '
            f'FOR EACH ROW EXECUTE FUNCTION "{schema}".{self.fonction}({args})'
        )


def _attnames(modele: Any, noms: Iterable[str]) -> list[str]:
    """Noms de colonnes d'après des noms de champs ou de colonnes (échec franc si inconnu)."""
    sortie: list[str] = []
    for nom in sorted(set(noms)):
        champ = None
        for f in modele._meta.concrete_fields:
            if nom in (f.name, f.attname):
                champ = f
                break
        if champ is None:
            raise LookupError(f"Colonne inconnue {nom!r} pour {modele._meta.label}.")
        sortie.append(champ.attname)
    return sortie


def _colonnes_immuables() -> dict[str, tuple[str, set[str]]]:
    """Modèle -> (condition, champs) : colonnes figées d'après les gardes de chaque application."""
    from apps.accomplissement.gardes import CHAMPS_FICHIER
    from apps.documents.managers import CHAMPS_DOCUMENT_FIGES, CHAMPS_GABARIT_FIGES
    from apps.suivi.models import PreuveMiseEnOeuvre, SuiviAction

    return {
        "documents.gabaritdocument": ("", set(CHAMPS_GABARIT_FIGES)),
        "documents.document": ("", set(CHAMPS_DOCUMENT_FIGES)),
        "accomplissement.piecejustificative": ("", set(CHAMPS_FICHIER)),
        "suivi.suiviaction": ("", set(SuiviAction.champs_figes())),
        "suivi.preuvemiseenoeuvre": ("", set(PreuveMiseEnOeuvre.champs_figes())),
    }


def _colonnes_modifiables() -> dict[str, tuple[str, set[str]]]:
    """Modèle -> (condition, champs) : seules ces colonnes peuvent changer."""
    from apps.documents.managers import CHAMPS_VERSION_MODIFIABLES
    from apps.notifications.managers import CHAMPS_MODIFIABLES
    from apps.suivi.models import Relance

    return {
        "documents.documentversion": ("statut=PRETE", set(CHAMPS_VERSION_MODIFIABLES)),
        "notifications.notification": ("", set(CHAMPS_MODIFIABLES)),
        "suivi.relance": ("", set(Relance.MODIFIABLES)),
        # Acceptation du risque : immuable, sauf suppression logique (D8 du lot 7).
        "recommandations.acceptationrisque": ("", {"deleted_at", "updated_at", "updated_by"}),
    }


def _ecritures_uniques() -> dict[str, tuple[str, set[str]]]:
    from apps.documents.managers import CHAMPS_VERSION_UNE_FOIS

    return {"documents.documentversion": ("statut=PRETE", set(CHAMPS_VERSION_UNE_FOIS))}


def _figes() -> list[tuple[str, tuple[str, ...]]]:
    """(modèle, arguments) de `onea_refuser_si_fige` : (parent|self, clé, colonne d'état, état)."""
    from apps.programmation.models import CHAMPS_EXECUTION

    if CHAMPS_EXECUTION:
        # Le gel applicatif tolère ces champs sur un programme validé : le déclencheur doit les
        # tolérer aussi. Étendre `onea_refuser_si_fige` avant d'en déclarer.
        raise RuntimeError(
            "CHAMPS_EXECUTION n'est plus vide : adapter le déclencheur des lignes de programme."
        )
    return [
        ("referentiel.cartographieversion", ("self", "", "statut", "VALIDEE")),
        (
            "referentiel.risque",
            ("referentiel_cartographieversion", "version_id", "statut", "VALIDEE"),
        ),
        ("programmation.programmeannuel", ("self", "", "statut", "VALIDE")),
        (
            "programmation.ligneprogramme",
            ("programmation_programmeannuel", "programme_id", "statut", "VALIDE"),
        ),
    ]


def _modeles() -> dict[str, Any]:
    return {
        m._meta.label_lower: m
        for m in apps.get_models()
        if m._meta.managed and not m._meta.proxy and not m._meta.abstract
    }


def declencheurs_attendus() -> list[Declencheur]:
    """Tous les déclencheurs attendus, dérivés des modèles et des catégories D6."""
    modeles = _modeles()
    liste: list[Declencheur] = []

    def _modele(label: str) -> Any:
        if label not in modeles:
            raise LookupError(f"Modèle {label} introuvable pour un déclencheur de gel.")
        return modeles[label]

    for label in sorted(TABLES_AJOUT_SEUL):
        liste.append(
            Declencheur(_modele(label)._meta.db_table, NOM_MODIFICATION, "UPDATE OR DELETE")
        )
    for label, modele in sorted(modeles.items()):
        if issubclass(modele, BaseModel) and label not in TABLES_AJOUT_SEUL:
            liste.append(Declencheur(modele._meta.db_table, NOM_SUPPRESSION, "DELETE"))
    for fonction, categorie in (
        (NOM_IMMUABLES, _colonnes_immuables()),
        (NOM_MODIFIABLES, _colonnes_modifiables()),
        (NOM_UNIQUE, _ecritures_uniques()),
    ):
        for label, (condition, champs) in sorted(categorie.items()):
            modele = _modele(label)
            liste.append(
                Declencheur(
                    modele._meta.db_table,
                    fonction,
                    "UPDATE",
                    (condition, *_attnames(modele, champs)),
                )
            )
    for label, arguments in _figes():
        modele = _modele(label)
        moment = "UPDATE" if arguments[0] == "self" else "INSERT OR UPDATE"
        liste.append(Declencheur(modele._meta.db_table, NOM_FIGE, moment, arguments))
    entites = (
        _modele("programmation.ligneprogramme")._meta.get_field("entites").remote_field.through
    )
    liste.append(Declencheur(entites._meta.db_table, NOM_ENTITES, "INSERT OR UPDATE OR DELETE"))
    cles = [d.cle for d in liste]
    doublons = {c for c in cles if cles.count(c) > 1}
    if doublons:
        raise RuntimeError(f"Déclencheurs de gel en double : {sorted(doublons)}")
    return liste


def tables_m2m() -> list[str]:
    """Tables de liaison générées (DELETE autorisé : les changements de liens y passent)."""
    return sorted(
        {
            m._meta.db_table
            for m in apps.get_models(include_auto_created=True)
            if m._meta.auto_created and m._meta.managed
        }
    )


def tables_transitoires() -> list[str]:
    """Tables des données d'identification transitoires (DELETE autorisé, catégorie c)."""
    modeles = _modeles()
    tables: list[str] = []
    for label in sorted(TABLES_TRANSITOIRES):
        modele = modeles.get(label)
        if modele is None:
            raise LookupError(f"Modèle {label} introuvable pour les tables transitoires.")
        if issubclass(modele, BaseModel) or label in TABLES_AJOUT_SEUL:
            raise ValueError(f"{label} est gelé en base : il ne peut pas être transitoire.")
        tables.append(modele._meta.db_table)
    return tables


def tables_avec_delete() -> list[str]:
    """Tables où le rôle applicatif a le droit DELETE : liaisons, sessions, transitoires."""
    return sorted({*tables_m2m(), "django_session", *tables_transitoires()})


# --- Installation --------------------------------------------------------------------------


def _schema(connexion: BaseDatabaseWrapper) -> str:
    with connexion.cursor() as c:
        c.execute("SELECT current_schema()")
        schema = str(c.fetchone()[0])
    if not _IDENTIFIANT.match(schema):
        raise ValueError(f"Schéma inattendu : {schema!r}")
    return schema


def role_applicatif(role: str | None = None) -> str:
    nom = role or os.environ.get("POSTGRES_APP_USER") or ROLE_APPLICATIF_DEFAUT
    if not _IDENTIFIANT.match(nom):
        raise ValueError(f"Nom de rôle invalide : {nom!r}")
    return nom


def sql_fonctions(schema: str) -> str:
    return SQL_FONCTIONS.replace("@S@", f'"{schema}"')


def _empreinte(schema: str, declencheurs: Iterable[Declencheur]) -> str:
    texte = sql_fonctions(schema) + "\n".join(sorted(d.sql(schema) for d in declencheurs))
    return hashlib.sha256(texte.encode()).hexdigest()


def installer_fonctions(connexion: BaseDatabaseWrapper | None = None) -> None:
    """Crée ou remplace les fonctions (appelé par la migration `core.0002`)."""
    connexion = connexion or connections[DEFAULT_DB_ALIAS]
    schema = _schema(connexion)
    with connexion.cursor() as c:
        c.execute(sql_fonctions(schema))


def _existants(
    connexion: BaseDatabaseWrapper, schema: str
) -> dict[tuple[str, str], tuple[bytes, str]]:
    with connexion.cursor() as c:
        c.execute(
            "SELECT cl.relname, t.tgname, t.tgargs, t.tgenabled "
            "FROM pg_catalog.pg_trigger t "
            "JOIN pg_catalog.pg_class cl ON cl.oid = t.tgrelid "
            "JOIN pg_catalog.pg_namespace n ON n.oid = cl.relnamespace "
            "WHERE n.nspname = %s AND NOT t.tgisinternal AND left(t.tgname, 5) = 'onea_'",
            [schema],
        )
        return {(r[0], r[1]): (bytes(r[2]), r[3]) for r in c.fetchall()}


def _tables_presentes(connexion: BaseDatabaseWrapper, schema: str) -> set[str]:
    with connexion.cursor() as c:
        c.execute(
            "SELECT relname FROM pg_catalog.pg_class cl "
            "JOIN pg_catalog.pg_namespace n ON n.oid = cl.relnamespace "
            "WHERE n.nspname = %s AND cl.relkind IN ('r', 'p')",
            [schema],
        )
        return {r[0] for r in c.fetchall()}


def _marque_installee(connexion: BaseDatabaseWrapper, schema: str) -> str:
    with connexion.cursor() as c:
        c.execute(
            "SELECT pg_catalog.obj_description(p.oid, 'pg_proc') FROM pg_catalog.pg_proc p "
            "JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = %s AND p.proname = %s",
            [schema, NOM_SUPPRESSION],
        )
        ligne = c.fetchone()
    return str(ligne[0] or "") if ligne else ""


def _args_octets(arguments: tuple[str, ...]) -> bytes:
    return b"".join(a.encode() + b"\x00" for a in arguments)


def _installer_declencheurs(connexion: BaseDatabaseWrapper, schema: str) -> int:
    attendus = declencheurs_attendus()
    presentes = _tables_presentes(connexion, schema)
    cibles = [d for d in attendus if d.table in presentes]
    existants = _existants(connexion, schema)
    empreinte = _empreinte(schema, attendus)
    manquants = [d for d in cibles if d.cle not in existants]
    inutiles = set(existants) - {d.cle for d in cibles}
    if (
        _marque_installee(connexion, schema) == _MARQUE + empreinte
        and not manquants
        and not inutiles
    ):
        return 0
    with connexion.cursor() as c:
        c.execute(sql_fonctions(schema))
        for table, nom in sorted(inutiles):
            c.execute(f'DROP TRIGGER IF EXISTS {nom} ON "{schema}"."{table}"')
        for d in cibles:
            c.execute(f'DROP TRIGGER IF EXISTS {d.fonction} ON "{schema}"."{d.table}"')
            c.execute(d.sql(schema))
        c.execute(f"COMMENT ON FUNCTION \"{schema}\".{NOM_SUPPRESSION}() IS '{_MARQUE}{empreinte}'")
    return len(cibles)


def _installer_droits(connexion: BaseDatabaseWrapper, schema: str, role: str) -> bool:
    """Droits du rôle applicatif ; sans effet (False) si le rôle n'existe pas."""
    with connexion.cursor() as c:
        c.execute("SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = %s", [role])
        if c.fetchone() is None:
            return False
        q = connexion.ops.quote_name
        s, r = q(schema), q(role)
        c.execute(f"GRANT USAGE ON SCHEMA {s} TO {r}")
        c.execute(f"REVOKE CREATE ON SCHEMA {s} FROM {r}")
        c.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA {s} FROM {r}")
        c.execute(f"GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA {s} TO {r}")
        presentes = _tables_presentes(connexion, schema)
        avec_delete = [t for t in tables_avec_delete() if t in presentes]
        if avec_delete:
            tables = ", ".join(f"{s}.{q(t)}" for t in avec_delete)
            c.execute(f"GRANT DELETE ON {tables} TO {r}")
        c.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {s} TO {r}")
        c.execute(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {s} GRANT SELECT, INSERT, UPDATE ON TABLES TO {r}"
        )
        c.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {s} GRANT USAGE, SELECT ON SEQUENCES TO {r}")
    return True


def installer(
    connexion: BaseDatabaseWrapper | None = None, *, role: str | None = None
) -> dict[str, Any]:
    """Installe fonctions, déclencheurs et droits ; idempotent, une seule transaction."""
    connexion = connexion or connections[DEFAULT_DB_ALIAS]
    if connexion.vendor != "postgresql":
        return {"declencheurs": 0, "droits": False}
    schema = _schema(connexion)
    with transaction.atomic(using=connexion.alias):
        nombre = _installer_declencheurs(connexion, schema)
        droits = _installer_droits(connexion, schema, role_applicatif(role))
    return {"declencheurs": nombre, "droits": droits}


# --- Vérification --------------------------------------------------------------------------


def verifier(
    connexion: BaseDatabaseWrapper | None = None,
    *,
    role: str | None = None,
    exiger_role: bool = False,
) -> list[str]:
    """Liste des écarts (vide = conforme) : déclencheurs, état, arguments, rôle applicatif."""
    connexion = connexion or connections[DEFAULT_DB_ALIAS]
    schema = _schema(connexion)
    problemes: list[str] = []
    existants = _existants(connexion, schema)
    attendus = {d.cle: d for d in declencheurs_attendus()}
    presentes = _tables_presentes(connexion, schema)
    for cle, d in sorted(attendus.items()):
        if d.table not in presentes:
            problemes.append(f"table absente : {d.table}")
        elif cle not in existants:
            problemes.append(f"déclencheur manquant : {d.fonction} sur {d.table}")
        else:
            args, etat = existants[cle]
            if etat != "O":
                problemes.append(f"déclencheur désactivé : {d.fonction} sur {d.table}")
            if args != _args_octets(d.arguments):
                problemes.append(f"arguments différents : {d.fonction} sur {d.table}")
    for table, nom in sorted(set(existants) - set(attendus)):
        problemes.append(f"déclencheur inattendu : {nom} sur {table}")
    if not problemes and _marque_installee(connexion, schema) == "":
        problemes.append("fonctions de garde non installées")
    problemes.extend(_verifier_role(connexion, schema, role_applicatif(role), exiger_role))
    return problemes


def _verifier_role(
    connexion: BaseDatabaseWrapper, schema: str, role: str, exiger_role: bool
) -> list[str]:
    """Le rôle applicatif, s'il existe : ni superutilisateur, ni propriétaire, ni membre."""
    problemes: list[str] = []
    with connexion.cursor() as c:
        c.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolinherit, rolreplication, rolbypassrls "
            "FROM pg_catalog.pg_roles WHERE rolname = %s",
            [role],
        )
        ligne = c.fetchone()
        if ligne is None:
            return [f"rôle applicatif absent : {role}"] if exiger_role else []
        for nom, valeur in zip(
            ("SUPERUSER", "CREATEDB", "CREATEROLE", "INHERIT", "REPLICATION", "BYPASSRLS"),
            ligne,
            strict=True,
        ):
            if valeur:
                problemes.append(f"rôle {role} : attribut {nom} interdit")
        c.execute(
            "SELECT count(*) FROM pg_catalog.pg_class cl "
            "JOIN pg_catalog.pg_namespace n ON n.oid = cl.relnamespace "
            "WHERE n.nspname = %s AND pg_catalog.pg_get_userbyid(cl.relowner) = %s",
            [schema, role],
        )
        if c.fetchone()[0]:
            problemes.append(f"rôle {role} : propriétaire d'objets du schéma")
        c.execute(
            "SELECT pg_catalog.pg_get_userbyid(cl.relowner) FROM pg_catalog.pg_class cl "
            "WHERE cl.oid = %s::regclass",
            [f'"{schema}"."{NOM_TABLE_REFERENCE}"'],
        )
        proprietaire = c.fetchone()
        if proprietaire and proprietaire[0] != role:
            c.execute("SELECT pg_catalog.pg_has_role(%s, %s, 'MEMBER')", [role, proprietaire[0]])
            if c.fetchone()[0]:
                problemes.append(f"rôle {role} : membre du rôle propriétaire {proprietaire[0]}")
        c.execute("SELECT pg_catalog.has_schema_privilege(%s, %s, 'CREATE')", [role, schema])
        if c.fetchone()[0]:
            problemes.append(f"rôle {role} : droit CREATE sur le schéma {schema}")
        c.execute(
            "SELECT count(*) FROM pg_catalog.pg_class cl "
            "JOIN pg_catalog.pg_namespace n ON n.oid = cl.relnamespace "
            "WHERE n.nspname = %s AND cl.relkind IN ('r', 'p') "
            "AND (pg_catalog.has_table_privilege(%s, cl.oid, 'TRUNCATE') "
            "  OR pg_catalog.has_table_privilege(%s, cl.oid, 'TRIGGER'))",
            [schema, role, role],
        )
        if c.fetchone()[0]:
            problemes.append(f"rôle {role} : droit TRUNCATE ou TRIGGER sur des tables")
        autorises = set(tables_avec_delete())
        c.execute(
            "SELECT cl.relname FROM pg_catalog.pg_class cl "
            "JOIN pg_catalog.pg_namespace n ON n.oid = cl.relnamespace "
            "WHERE n.nspname = %s AND cl.relkind IN ('r', 'p') "
            "AND pg_catalog.has_table_privilege(%s, cl.oid, 'DELETE')",
            [schema, role],
        )
        for (table,) in c.fetchall():
            if table not in autorises:
                problemes.append(f"rôle {role} : droit DELETE sur {table}")
    return problemes


# --- Maintenance ---------------------------------------------------------------------------


@contextmanager
def maintenance(using: str = DEFAULT_DB_ALIAS) -> Iterator[None]:
    """`SET LOCAL onea.maintenance = 'on'` le temps du bloc (transaction du propriétaire).

    Sans effet pour le rôle applicatif : les déclencheurs refusent quand même. Réservé aux
    migrations de données, aux tests et à la procédure de maintenance documentée.
    """
    connexion = connections[using]
    with transaction.atomic(using=using):
        with connexion.cursor() as c:
            c.execute("SELECT set_config('onea.maintenance', 'on', true)")
        yield
        with connexion.cursor() as c:
            c.execute("SELECT set_config('onea.maintenance', '', true)")
