# Pile de recette (proche de la production)

Pile locale qui exécute `docker/compose.prod.yml` **sans modification**, avec une surcouche
réservée à la recette (`scripts/recette/compose.override.yml`) : `pg_stat_statements`,
Mailpit (courrier de recette) et ports de diagnostic sur `127.0.0.1` uniquement.

Prérequis : Docker Compose v2, `openssl`, `curl`, un shell POSIX (Linux, WSL ou CI) ;
ports **80 et 443 libres** sur la machine. L'hôte `audit.recette.test`
est résolu par `curl --resolve` : aucun DNS ni fichier `hosts`.

## Lancement

```
sh scripts/recette/up.sh          # AC + certificat, .recette/.env.recette, docker compose up
sh scripts/recette/tests/edge.sh  # banc d'essai de la périphérie (nginx)
```

`up.sh` génère dans `.recette/` (ignoré par git) l'AC et le certificat, des secrets
aléatoires et le dossier des documents (10001:10001, 0750). Il dépose aussi l'AC dans
`certs/recette-ca.pem` (`CA_BUNDLE_PATH`) pour que le backend fasse confiance au certificat de recette.

## Comptes

Le compte d'écriture `admin` se prépare avec les outils de l'application, comme en production
(`docs/deploy.md` §5) : `sh scripts/recette/comptes.sh [identifiant]` lance `creer_administrateur`
dans `web` (mot de passe temporaire lu sur la sortie de `exec`), se connecte par l'API, remplace le
mot de passe temporaire par un mot de passe aléatoire (`/auth/password/change/`) et l'écrit dans
`.recette/comptes.txt` (0600, ignoré par git, une ligne `identifiant:mot_de_passe`). Relancé, il
réinitialise le compte. La CI le lance après `up.sh` (job `recette`) ; `tests/reseaux.sh` et
`tests/restauration.sh` (qui le lance lui-même après `peupler_demo`, donc sur une pile neuve :
`peupler_demo` refuse une base qui contient déjà `admin`) en ont besoin. Les autres
comptes (dont les comptes de charge `chargeNN` de `scripts/recette/charge.sh`) se créent par l'écran
*Utilisateurs* ou l'import CSV ; chacun change son mot de passe temporaire, puis sa ligne est
ajoutée au fichier à la main, avec le mot de passe **définitif** (sans code de connexion par courriel).
Le courrier envoyé par l'application se consulte sur http://127.0.0.1:18025 (Mailpit).

## Arrêt

```
sh scripts/recette/down.sh
```

Supprime conteneurs, volumes, `.recette/` et `certs/recette-ca.pem`.

## Rappel D20

Les comptes de charge (`chargeNN`) et leur fichier `.recette/comptes.txt` n'existent **qu'en
recette**. Aucun mot de passe de test ne doit figurer dans `docs/deploy.md` ni dans
`.env.prod.example`.
