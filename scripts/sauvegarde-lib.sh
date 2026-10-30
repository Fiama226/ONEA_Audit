#!/bin/sh
# Fonctions communes à scripts/backup.sh et scripts/restore.sh (lot 9, T18). À sourcer, jamais à lancer.
# Variables attendues avant l'appel : ROOT (racine du dépôt), ENV_FILE (fichier d'environnement).
# Variable facultative : ONEA_COMPOSE_FICHIERS = fichiers Compose supplémentaires (séparés par des
# espaces), utilisés par la recette (surcouche) ; vide en production.

# compose <args...> : docker compose de la production (le fichier .env sert à Compose, jamais sourcé).
# compose.prod.yml DOIT rester le premier fichier : Compose prend son dossier comme dossier du projet
# (chemins relatifs des montages). Les surcouches s'ajoutent après lui, par COMPOSE_FILE.
compose() {
  _fichiers="$ROOT/docker/compose.prod.yml"
  for _extra in ${ONEA_COMPOSE_FICHIERS:-}; do
    _fichiers="$_fichiers:$_extra"
  done
  COMPOSE_FILE="$_fichiers" docker compose --env-file "$ENV_FILE" "$@"
}

# lire_env <NOM> : valeur d'une variable du fichier d'environnement (lue, jamais sourcée).
lire_env() {
  sed -n "s/^$1=//p" "$ENV_FILE" | tail -n 1 | tr -d '\r' | tr -d "\"'"
}

# dossier_documents : DOCUMENTS_HOST_DIR validé, imprimé sous forme canonique (chemin absolu, hors
# dépôt et hors dossiers système).
dossier_documents() {
  _docs=$(lire_env DOCUMENTS_HOST_DIR)
  [ -n "$_docs" ] && [ -d "$_docs" ] || {
    echo "ERREUR : DOCUMENTS_HOST_DIR absent de $ENV_FILE ou dossier introuvable." >&2
    return 1
  }
  case "$_docs" in
    /*) ;;
    *) echo "ERREUR : DOCUMENTS_HOST_DIR doit être un chemin absolu." >&2; return 1 ;;
  esac
  _reel=$(cd "$_docs" && pwd -P)
  case "$_reel/" in
    # La pile de recette (git-ignorée, jamais en production) garde ses documents dans .recette/.
    "$ROOT"/.recette/*) ;;
    "$ROOT"/*|/|/app/*|/etc/*|/proc/*|/sys/*|/dev/*)
      echo "ERREUR : DOCUMENTS_HOST_DIR ne doit pas être dans le dépôt ni un dossier système." >&2
      return 1 ;;
  esac
  printf '%s\n' "$_reel"
}

# tar_tolerant <code> : un fichier temporaire qui disparaît pendant la lecture (code 1 de GNU tar)
# n'est pas une erreur ; tout code supérieur l'est.
tar_tolerant() {
  [ "$1" -le 1 ]
}

# attendre_postgres <service> : attend le serveur DÉFINITIF. Au premier démarrage d'un volume vide,
# l'image postgres lance d'abord un serveur temporaire (socket Unix seulement) pour les scripts d'initdb
# (dont la création du rôle applicatif) : le contrôle de santé du service peut déjà réussir à ce moment.
# Seul le serveur définitif écoute en TCP : on interroge donc 127.0.0.1.
attendre_postgres() {
  _essais=0
  until compose exec -T "$1" sh -c 'pg_isready -q -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
    >/dev/null 2>&1; do
    _essais=$((_essais + 1))
    [ "$_essais" -le 60 ] || { echo "ERREUR : $1 ne répond pas en TCP (attente de 2 min)." >&2; return 1; }
    sleep 2
  done
}
