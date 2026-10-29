# Pile de recette (proche de la production)

Pile locale qui exécute `docker/compose.prod.yml` **sans modification**, avec une surcouche
réservée à la recette (`scripts/recette/compose.override.yml`) : `pg_stat_statements`,
Mailpit (courrier de recette) et ports de diagnostic sur `127.0.0.1` uniquement.

Prérequis : Docker Compose v2, `openssl`, `curl`, un shell POSIX (Linux, WSL ou CI) ;
ports **80 et 443 libres** sur la machine. Les hôtes `audit.recette.test` et
`sso.recette.test` sont résolus par `curl --resolve` : aucun DNS ni fichier `hosts`.

## Lancement

```
sh scripts/recette/up.sh          # AC + certificat, .recette/.env.recette, docker compose up
sh scripts/recette/realm.sh       # realm onea, clients, comptes de test
sh scripts/recette/tests/edge.sh  # banc d'essai de la périphérie (nginx)
```

`up.sh` génère dans `.recette/` (ignoré par git) l'AC et le certificat, des secrets
aléatoires et le dossier des documents (10001:10001, 0750). Il dépose aussi l'AC dans
`certs/recette-ca.pem` pour que le backend fasse confiance au SSO de recette.

## Comptes

`realm.sh` écrit les identifiants (utilisateur, mot de passe aléatoire, rôle) dans
`.recette/comptes.txt` : `rai`, `auditeur1`, `auditeur2`, `audite1`, `dg`, `admin`.
Les comptes des tâches T4 et T26 s'ajoutent à la fin de `realm.sh`.
Le courrier envoyé par l'application se consulte sur http://127.0.0.1:18025 (Mailpit).

## Arrêt

```
sh scripts/recette/down.sh
```

Supprime conteneurs, volumes, `.recette/` et `certs/recette-ca.pem`.

## Rappel D20

Le client `onea-charge` (accès direct par mot de passe, pour les essais de charge) et
`OIDC_ALLOWED_AZP=onea-frontend,onea-charge` n'existent **qu'en recette**. Ils ne doivent
jamais figurer dans `docs/deploy.md`, `.env.prod.example` ni dans un realm de production
(`edge.sh` le vérifie).
