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

Aucun script ne crée de comptes avec un mot de passe connu : la recette suit la procédure de
production (`docs/deploy.md` §5). Créer l'administrateur par
`docker compose -p onea-recette --env-file .recette/.env.recette -f docker/compose.prod.yml -f scripts/recette/compose.override.yml exec web python manage.py creer_administrateur --identifiant admin --courriel admin@example.org`,
se connecter (changement de mot de passe imposé), puis créer les autres comptes (écran *Utilisateurs*
ou import CSV). Les scripts `scripts/recette/charge.sh` et `scripts/recette/lib.sh` lisent les
identifiants dans `.recette/comptes.txt` (ignoré par git, une ligne `identifiant:mot_de_passe`),
tenu à la main avec les mots de passe **définitifs** (sans code de connexion par courriel).
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
