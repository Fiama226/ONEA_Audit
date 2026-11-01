# Déploiement en production

Ce document décrit l'installation de la plateforme sur un serveur Linux avec Docker Compose
(`docker/compose.prod.yml`). Seul `nginx` publie des ports (80 et 443).

Exploitation courante (incidents, mises à jour, restauration, rotation) : [`docs/exploitation/runbook.md`](exploitation/runbook.md). Liste de contrôle de mise en service : [`docs/exploitation/mise-en-production.md`](exploitation/mise-en-production.md).

Réseaux Docker :

| Réseau | Type | Services |
|---|---|---|
| `edge` | standard | nginx (ports 80/443) |
| `web` | `internal`, sous-réseau fixe `ONEA_SUBNET_WEB` (défaut `172.30.10.0/28`) | nginx (adresse fixe `ONEA_NGINX_IP`, alias `${SSO_HOST}`), web, worker |
| `front` | `internal` | nginx, frontend |
| `sso` | `internal` | nginx, keycloak |
| `kc-out` | standard | keycloak seul (sortie LDAP) |
| `mail-out` | standard | worker seul (sortie SMTP) |
| `backend` | `internal` | web, worker, beat, migrate, db, redis, meilisearch, gotenberg |
| `av` | `internal` | clamav, web, worker (clamd, port 3310, joignable de ces trois services seulement) |
| `av-out` | standard | clamav seul (mise à jour des signatures par freshclam) |
| `kc` | `internal` | keycloak, keycloak-db |

`nginx` porte l'alias réseau `${SSO_HOST}` sur `web` : `web` et `worker` joignent le SSO à
travers `nginx`, sans passer par l'adresse publique. Les ports 8080 et 9000 de Keycloak ne
sont joignables que depuis `nginx` (réseau `sso`). `web` n'a aucune sortie : tout courriel
part du `worker` (tâche Celery) via `mail-out`. `gotenberg` n'a aucune route sortante.
ClamAV (SEC-04) est un conteneur séparé : `web` et `worker` l'interrogent sur `av` (protocole
INSTREAM) ; sa seule route sortante est la mise à jour des signatures (`av-out`, aucun autre
service). Premier démarrage : téléchargement d'environ 300 Mo de signatures puis chargement en
mémoire (1 à 3 minutes, `start_period` de 300 s) ; tant que `docker compose ps` n'indique pas
`clamav` « healthy », les téléversements sont refusés (échec fermé). Le pare-feu de l'hôte doit
autoriser la sortie HTTPS du conteneur vers `database.clamav.net` (ou un miroir interne à
renseigner dans `FRESHCLAM_CONF_DatabaseMirror`). Procédures : `docs/exploitation/runbook.md` §11.
Redis (Valkey) exige un mot de passe (fichier de secret `redis_password`, §3).

Variables de la périphérie :

- `ONEA_IP_RANGE_WEB` (défaut `172.30.10.8/29`) : plage dynamique du réseau `web`, à l'intérieur du sous-réseau et **sans** `ONEA_NGINX_IP` (sinon `web`/`worker` prennent `.2` avant nginx et il ne démarre pas). Vérifier l'absence de chevauchement du sous-réseau avec `docker network inspect`.
- `ONEA_SUBNET_WEB` / `ONEA_NGINX_IP` : sous-réseau du réseau `web` et adresse fixe de `nginx`
  (doit appartenir au sous-réseau). À changer si le sous-réseau entre en conflit avec le réseau
  de l'établissement. `TRUSTED_PROXY_CIDRS` (Django) et `FORWARDED_ALLOW_IPS` (gunicorn)
  valent `ONEA_NGINX_IP` : `nginx` est le seul pair cru.
- `TRUSTED_UPSTREAM_CIDRS` : répartiteurs ou proxys placés devant `nginx` (CIDR, séparés par
  des virgules). Vide (défaut) : `nginx` prend le pair TCP comme adresse du client. Renseigné :
  `X-Forwarded-For` n'est cru que si le pair appartient à ces plages (`realip`), et l'adresse
  du client — utilisée pour les limites de débit, le journal d'accès et la piste d'audit —
  est celle derrière ce proxy.

## 1. Prérequis

- Serveur Linux avec Docker Engine 26+ et le plugin Compose v2 (`docker compose version`).
- Deux noms DNS pointant vers le serveur, par exemple `audit.onea.bf` (application) et
  `sso.onea.bf` (Keycloak).
- Un certificat TLS couvrant les deux noms (SAN ou certificat générique), délivré par
  l'autorité de l'ONEA ou une autorité publique.
- 4 Go de RAM minimum (Keycloak, PostgreSQL x2, Meilisearch, Gotenberg), 20 Go de disque.
- Ports 80 et 443 ouverts ; aucun autre port n'est nécessaire.

## 2. Certificats

Deux voies, au choix de l'ONEA (décision U2). Dans les deux cas, `nginx` lit
`fullchain.pem` (certificat + chaîne) et `privkey.pem` (clé privée) dans le répertoire
`TLS_CERT_DIR`, monté en lecture seule. Le certificat doit couvrir `PUBLIC_HOST` **et**
`SSO_HOST` (deux noms alternatifs ou un joker).

```
/etc/onea/certs/fullchain.pem   # certificat + chaîne intermédiaire (0644)
/etc/onea/certs/privkey.pem     # clé privée (chmod 600, propriétaire root)
```

### 2.1 Voie A : autorité de certification interne de l'ONEA

Aucun accès à Internet n'est requis (convient à un serveur sur site).

1. Générer une clé et une demande de signature (CSR) avec les deux noms :
   ```
   openssl req -new -newkey rsa:3072 -nodes -keyout privkey.pem -out onea.csr \
     -subj "/CN=audit.onea.bf" \
     -addext "subjectAltName=DNS:audit.onea.bf,DNS:sso.onea.bf"
   ```
2. Transmettre `onea.csr` à la DSI (l'AC signe ; la clé ne quitte jamais le serveur).
3. Assembler la chaîne reçue : `cat certificat.pem intermediaire.pem > fullchain.pem`.
4. Déposer les deux fichiers dans `TLS_CERT_DIR` (clé en 0600, propriétaire root).
5. Faire confiance à l'AC côté backend (§ « Autorité de certification interne » plus bas :
   `certs/ca-bundle.pem`, `SSO_CA_BUNDLE_PATH`), et distribuer l'AC aux postes de travail.
6. Démarrer ou recharger : `docker compose --env-file .env.prod -f docker/compose.prod.yml exec nginx nginx -s reload`.
7. Renouvellement : refaire les étapes 2 à 4 (ou réutiliser le CSR) **avant l'échéance**, puis
   recharger comme à l'étape 6. Noter l'échéance dans le calendrier de la DSI.

### 2.2 Voie B : Let's Encrypt (défi ACME http-01)

Prérequis, **tous obligatoires** :
- les deux noms (`PUBLIC_HOST`, `SSO_HOST`) existent dans le DNS **public** et pointent vers ce serveur ;
- le port **80** est joignable depuis Internet (pare-feu, NAT) : le défi passe par
  `http://<nom>/.well-known/acme-challenge/` ; `nginx` le sert avant la redirection vers HTTPS ;
- l'hôte dispose de Docker (l'outil `certbot` s'exécute dans une image épinglée) ;
- dans `.env.prod` : `ACME_WEBROOT` (défaut `/var/www/onea-acme`, monté en lecture seule dans
  `nginx`) et `LETSENCRYPT_EMAIL` (adresse recevant les alertes d'expiration). `ACME_WEBROOT`
  doit exister **avant** le démarrage de la pile.

Étapes :
1. Premier démarrage avec un certificat provisoire (auto-signé) dans `TLS_CERT_DIR`, pour que
   `nginx` démarre et serve le défi sur le port 80.
2. Essai à blanc (serveur de test de Let's Encrypt, **rien n'est écrit**) :
   `sh scripts/tls/certbot.sh --dry-run`
3. Facultatif : certificat de test réel (non reconnu des navigateurs, quotas larges) :
   `sh scripts/tls/certbot.sh --staging`
4. Émission réelle : `sh scripts/tls/certbot.sh --production`. Le script copie le certificat
   dans `TLS_CERT_DIR` (remplacement atomique) et recharge `nginx`. Les quotas de Let's
   Encrypt limitent les émissions répétées : ne lancer le mode réel qu'après un essai réussi.
5. Renouvellement automatique (certbot ne renouvelle qu'à moins de 30 jours de l'échéance) :
   ```
   sudo cp docker/ops/onea-certificat.service docker/ops/onea-certificat.timer /etc/systemd/system/
   sudo systemctl daemon-reload && sudo systemctl enable --now onea-certificat.timer
   systemctl list-timers onea-certificat.timer
   ```
   Les unités supposent le dépôt dans `/opt/onea` ; adapter `WorkingDirectory` et `ExecStart`
   sinon. Contrôle : `journalctl -u onea-certificat.service`.
6. Vérification : `openssl s_client -connect <PUBLIC_HOST>:443 -servername <PUBLIC_HOST> </dev/null | openssl x509 -noout -dates -issuer`.

Dépannage : « Timeout during connect » = port 80 fermé ou DNS erroné ; « 404 » sur le défi =
`ACME_WEBROOT` différent entre le script et `.env.prod`. Dans tous les cas, ne pas relancer
`--production` en boucle (limite de 5 échecs par heure et par nom).

### 2.3 Courrier sortant (SMTP)

L'application refuse de démarrer sans `EMAIL_URL`. Renseigner dans `.env.prod` :

| Mode du relais | `EMAIL_URL` |
|---|---|
| STARTTLS (port 587) | `smtp+tls://compte@smtp.onea.bf:587` |
| TLS implicite (port 465) | `smtps://compte@smtp.onea.bf:465` |
| relais interne en clair (réseau de confiance seulement) | `smtp://smtp.onea.bf:25` |

- Le mot de passe n'est **jamais** dans l'URL : il est dans le fichier de secret `email_password`
  (§3.1). Les caractères spéciaux du compte s'encodent en pourcentage.
- L'expéditeur est `audit-interne@onea.bf`. La DSI publie les enregistrements **SPF** (autoriser
  l'adresse du relais pour le domaine `onea.bf`) et **DKIM** (clé du relais) ; sans eux, les
  messages risquent d'être classés indésirables.
- Test, depuis la pile démarrée (n'envoie qu'un message, au destinataire indiqué) :
  ```
  docker compose --env-file .env.prod -f docker/compose.prod.yml exec web \
    python manage.py envoyer_courriel_test destinataire@onea.bf
  ```
  La commande affiche le relais, le port et le mode de chiffrement (jamais le mot de passe) ; en
  cas d'échec, elle donne le type d'erreur sans détail sensible. Contrôler ensuite la réception
  (et l'en-tête `Authentication-Results` pour SPF/DKIM).

## 3. Secrets et fichier d'environnement

Les secrets ne sont **jamais** des variables d'environnement (sauf les deux de Keycloak, voir
plus bas) : ce sont des **fichiers** générés une fois sur le serveur, montés dans les conteneurs
par les `secrets:` de Compose sous `/run/secrets/`. `docker inspect` n'en montre que les
chemins.

### 3.1 Générer les fichiers de secrets

```
sudo install -d -m 0700 /etc/onea/secrets            # dossier de root, 0700, hors dépôt
sudo sh scripts/generer-secrets.sh --dossier /etc/onea/secrets
sudo sh scripts/generer-secrets.sh --verifier --dossier /etc/onea/secrets
```

Le script crée un fichier par secret, en `0600` dès la création, avec des valeurs aléatoires
(`/dev/urandom`), sans jamais afficher une valeur et **sans jamais écraser un fichier
existant** (relancé, il ne fait que créer ce qui manque). Lancé en root, il donne les fichiers
à `10001:10001` (utilisateur des conteneurs applicatifs) : Compose monte les fichiers tels
quels et ne sait ni changer leur propriétaire ni leur mode. `db`, `redis` et `meilisearch`
tournent en root avec la capacité `DAC_OVERRIDE` pour les lire. Hors root : `--proprietaire
UID:GID` (ou `chown 10001:10001` ensuite). `--verifier` contrôle les droits (dossier `0700`,
fichiers `0600`), l'absence de fichier vide et de valeur `CHANGE_ME`.

| Fichier | Lu par | Contenu |
|---|---|---|
| `secret_key` | web, worker, beat, migrate | clé secrète Django (96 caractères hexadécimaux) |
| `secret_key_fallbacks` | web, worker, beat, migrate | anciennes clés acceptées pendant une rotation, une par ligne ; **vide** au départ |
| `postgres_password` | db, migrate | mot de passe du propriétaire `POSTGRES_USER` |
| `postgres_app_password` | db (création du rôle), web, worker, beat | mot de passe du rôle applicatif `POSTGRES_APP_USER` |
| `redis_password` | redis, web, worker, beat, migrate | mot de passe Valkey |
| `oidc_client_secret` | web, worker, beat, migrate | secret du client `onea-backend` (voir §5, étape 6) |
| `keycloak_sync_secret` | web, worker, beat, migrate | secret du compte de service `onea-admin-sync` (§5, étape 7bis) ; lu par Django via `KEYCLOAK_ADMIN_API_CLIENT_SECRET_FILE` (variable `KEYCLOAK_ADMIN_API_CLIENT_SECRET` en développement) |
| `meili_master_key` | meilisearch, web, worker, beat, migrate | clé maître Meilisearch |
| `metrics_token` | web | jeton `Authorization: Bearer` de `/api/v1/metrics/` |
| `email_password` | worker | mot de passe SMTP ; **vide** si le relais n'en exige pas (le mot de passe de `EMAIL_URL` s'applique alors, s'il y en a un) |

**Installation existante (secrets jusqu'ici dans `.env.prod`).** Ne pas laisser le script
inventer des valeurs que la base, Keycloak ou Meilisearch ne connaissent pas : **avant** de le
lancer, écrire les valeurs actuelles dans les fichiers (`printf '%s\n' "$VALEUR" | sudo tee
/etc/onea/secrets/postgres_password >/dev/null`, puis `chmod 0600` et `chown 10001:10001`) pour
`secret_key`, `postgres_password`, `redis_password`, `oidc_client_secret`,
`keycloak_sync_secret` et `meili_master_key` ; le script ne crée alors que les fichiers
manquants (`postgres_app_password`, `metrics_token`…). Retirer ensuite ces variables de
`.env.prod`, puis `docker compose … up -d`.

Côté Django, `<NOM>_FILE` (chemin du fichier) est **prioritaire** sur `<NOM>` ; seuls les sauts
de ligne finaux sont retirés ; un fichier absent ou illisible arrête le démarrage en nommant la
variable. `DATABASE_URL` et `REDIS_URL` sont donnés **sans mot de passe** ; il vient de
`DATABASE_PASSWORD_FILE` et `REDIS_PASSWORD_FILE` (encodé par l'application : aucune contrainte
sur les caractères). En production, toute valeur `CHANGE_ME*` ou de développement est refusée.

### 3.2 Fichier d'environnement

```
cp .env.prod.example .env.prod
chmod 600 .env.prod
```

Renseigner les noms DNS, `ONEA_SECRETS_DIR` (le dossier ci-dessus), `EMAIL_URL` **sans mot de
passe** (`smtp+tls://compte@smtp.onea.bf:587` ; le mot de passe va dans `email_password`) et
remplacer les deux `CHANGE_ME` restants (`KEYCLOAK_ADMIN_PASSWORD`, `KEYCLOAK_DB_PASSWORD` :
valeurs aléatoires sans `@ : / ? # %`, par exemple `openssl rand -hex 32`) : **Keycloak ne lit
pas de fichier de secret**, ces deux-là restent des variables, visibles de qui lit `.env.prod`
ou fait `docker inspect keycloak keycloak-db`. `APP_VERSION` est l'étiquette des images (ex.
`1.0.0`). Le fichier n'est jamais commité (`.gitignore`). Vérification :

```
docker compose --env-file .env.prod -f docker/compose.prod.yml config -q
```

Sans `ONEA_SECRETS_DIR` ou sans une variable obligatoire, la commande échoue en la nommant.
Sauvegarder le dossier des secrets (`/etc/onea/secrets`) et `.env.prod` dans un coffre, pas dans
le dépôt ; une sauvegarde de base **sans** les secrets correspondants ne suffit pas à
reconstruire le service.

Les secrets restent lisibles de toute personne pouvant exécuter `docker exec` (groupe `docker`,
donc équivalent root sur le serveur) : limiter strictement l'accès à ce groupe et au dossier
des secrets. La détection de fuite dans le dépôt est décrite en §3.4.

### 3.3 Rotation des secrets

Principes : un secret à la fois ; sauvegarder d'abord (`scripts/backup.sh`) ; **écrire le
nouveau fichier sur place** (`... > fichier`, jamais un `mv` ni un éditeur qui renomme : le
fichier monté dans `db` doit montrer la nouvelle valeur) ; conserver propriétaire et mode ;
recréer ensuite les conteneurs concernés (`up -d --force-recreate <services>`) car chaque
secret n'est lu qu'au démarrage. Abréviation : `dc` =
`docker compose --env-file .env.prod -f docker/compose.prod.yml`. Une nouvelle valeur :
`od -An -tx1 -N32 /dev/urandom | tr -d ' \n'` (48 octets pour `secret_key`).

| Secret | Procédure | Interruption |
|---|---|---|
| `SECRET_KEY` | 1. `cat /etc/onea/secrets/secret_key >> /etc/onea/secrets/secret_key_fallbacks` (l'ancienne reste acceptée). 2. Écrire une nouvelle valeur dans `secret_key`. 3. `dc up -d --force-recreate web worker beat`. 4. Après la durée de vie des sessions (8 h) et des jetons signés, vider le fichier des anciennes clés (`: > .../secret_key_fallbacks`) puis recréer `web worker beat`. | aucune (les signatures de l'ancienne clé restent valides pendant la transition) |
| Mot de passe du rôle applicatif | 1. `dc stop web worker beat`. 2. Écrire la nouvelle valeur dans `postgres_app_password`. 3. Appliquer avec l'encadré « ALTER ROLE » ci-dessous (la valeur est lue dans le conteneur, jamais passée en argument). 4. `dc up -d --force-recreate web worker beat`. | courte (web, worker, beat) |
| Mot de passe du propriétaire | Idem avec `postgres_password` et `POSTGRES_USER` dans l'encadré, puis `dc up -d --force-recreate db migrate`. `POSTGRES_PASSWORD_FILE` n'agit qu'à l'initialisation du volume : l'`ALTER ROLE` est indispensable. Les sauvegardes passent par le socket du conteneur, sans mot de passe. | `migrate` seulement |
| Redis (Valkey) | 1. Écrire la nouvelle valeur dans `redis_password`. 2. `dc up -d --force-recreate redis web worker beat migrate`. Les tâches en attente sont conservées (`appendonly`). | courte |
| Secret client OIDC (`onea-backend`) | 1. Écrire la nouvelle valeur dans `oidc_client_secret`. 2. Dans Keycloak (console, realm `onea`, client `onea-backend`, *Credentials*) : *Regenerate*, puis copier la valeur affichée dans le fichier (voir « Secret d'un client Keycloak » plus bas). 3. `dc up -d --force-recreate web worker beat`. Ce secret ne sert pas à valider les jetons (userinfo + JWKS) : aucune connexion n'est coupée. | aucune |
| Compte de service `onea-admin-sync` | Idem avec `keycloak_sync_secret` et le client `onea-admin-sync`. Tant que les deux valeurs diffèrent, la synchronisation des comptes échoue (reprise automatique, toutes les 15 min). | aucune pour les utilisateurs |
| Meilisearch | 1. Écrire la nouvelle valeur dans `meili_master_key`. 2. `dc up -d --force-recreate meilisearch web worker beat migrate`. 3. `dc exec web python manage.py configurer_recherche` puis `dc exec web python manage.py reindexer`. | recherche indisponible quelques minutes |
| Jeton de métriques | Écrire la nouvelle valeur dans `metrics_token`, `dc up -d --force-recreate web`, puis mettre à jour la supervision de l'ONEA (en-tête `Authorization: Bearer`). | aucune |
| Mot de passe SMTP | Écrire la nouvelle valeur dans `email_password`, `dc up -d --force-recreate worker`. | aucune |

**Encadré « ALTER ROLE »** (remplacer `postgres_app_password` et `POSTGRES_APP_USER` par
`postgres_password` et `POSTGRES_USER` pour le propriétaire) : le mot de passe est lu dans le
conteneur par `psql` lui-même ; il n'apparaît ni dans la ligne de commande ni dans l'historique
du shell.

```
dc exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
\set role `echo "$POSTGRES_APP_USER"`
\set pw `cat /run/secrets/postgres_app_password`
SELECT format('ALTER ROLE %I PASSWORD %L', :'role', :'pw') \gexec
SQL
```

**Secret d'un client Keycloak.** Voie recommandée : console d'administration, *Clients >
`onea-backend` (ou `onea-admin-sync`) > Credentials > Regenerate*, puis copier la valeur affichée
dans le fichier de secret (`printf '%s\n' '<valeur>' | sudo tee /etc/onea/secrets/oidc_client_secret
>/dev/null`) sans la consigner ailleurs, et recréer `web worker beat`. Contrôle : le journal de
`worker` ne montre plus d'échec « Keycloak admin » après la synchronisation suivante.

**Secrets propres à Keycloak** (variables de `.env.prod`) :

- `KEYCLOAK_ADMIN_PASSWORD` n'est lu qu'à la création du compte d'amorçage : le changer dans la
  console (le compte nominatif remplace l'amorçage, §5) puis mettre `.env.prod` en cohérence.
- `KEYCLOAK_DB_PASSWORD` : saisir le nouveau mot de passe dans une session `psql` interactive
  (`dc exec keycloak-db psql -U keycloak -d keycloak` puis `\password keycloak`), écrire la même
  valeur dans `.env.prod`, enfin `dc up -d --force-recreate keycloak`.

**Fuite avérée** (secret publié, poste perdu) : rotation immédiate de **tous** les secrets
concernés, déconnexion de toutes les sessions Keycloak (*Sessions*), relecture du journal d'audit
de la période.

### 3.4 Détection de fuite de secrets

`gitleaks` (MIT) analyse les modifications indexées à chaque commit (hook `pre-commit`, voir
`.pre-commit-config.yaml`) et **tout l'historique** en intégration continue (job `secrets-scan`).
Les règles par défaut s'appliquent ; `.gitleaks.toml` ne liste que des valeurs de développement
ou de modèle (publiques, refusées en production) et des faux positifs documentés (références
`${VARIABLE}` de Compose, URL JDBC sans identifiants, chemin `/etc/passwd` d'un test). Installation
locale : `pre-commit install`. Contrôle manuel de l'historique :

```
docker run --rm -v "$PWD:/repo" ghcr.io/gitleaks/gitleaks:v8.30.1 git --redact -c /repo/.gitleaks.toml /repo
```

Un constat réel n'est **pas** ajouté à `.gitleaks.toml` : le secret est changé (§3.3), puis
retiré de l'historique si le dépôt a été publié.

### Autorité de certification interne (facultatif)

Si le certificat du SSO est signé par une autorité interne, le backend doit lui faire
confiance pour joindre Keycloak (validation des jetons). Créer un fichier
`certs/ca-bundle.pem` à la racine du dépôt contenant **les autorités publiques de confiance
puis l'autorité interne** (la variable remplace le magasin par défaut de Python), puis
renseigner dans `.env.prod` : `SSO_CA_BUNDLE_PATH=/etc/onea/ca/ca-bundle.pem`. Le
répertoire `certs/` est monté en lecture seule dans `web` et `worker`
(`REQUESTS_CA_BUNDLE`). Laisser la variable vide pour un certificat d'autorité publique.

## 4. Premier démarrage

```
docker compose --env-file .env.prod -f docker/compose.prod.yml up -d --build
docker compose --env-file .env.prod -f docker/compose.prod.yml ps
```

Le service à usage unique `migrate` (`restart: "no"`) applique les migrations et rassemble
les fichiers statiques dans le volume partagé avec `nginx` ; `web`, `worker` et `beat`
attendent sa fin réussie (`service_completed_successfully`). Si `migrate` échoue, rien
d'autre ne démarre : consulter `docker compose ... logs migrate`.
`https://audit.onea.bf/api/v1/health/` doit répondre `{"status":"ok",...}`. Tant que le
realm Keycloak n'existe pas (section suivante), la connexion à l'application n'est pas
possible.

Les fichiers générés (documents Word et PDF) sont stockés sur le disque du serveur, dans
le dossier `DOCUMENTS_HOST_DIR` monté dans `web` et `worker` : créer ce dossier avant le
premier démarrage et lire [`docs/stockage-fichiers.md`](stockage-fichiers.md).

Le site d'administration Django (`/admin/`) est désactivé ; ne l'activer
(`DJANGO_ADMIN_ENABLED=true`) que temporairement pour une opération précise.

**Listes de référence (facultatif, à la demande du RAI).** La plateforme démarre vide et
aucun chargement n'est automatique. Quand l'ONEA a confirmé les noms des directions et des
processus (`backend/apps/referentiel/data/README.md`), l'exploitant les charge une fois, après
une simulation :

```
docker compose --env-file .env.prod -f docker/compose.prod.yml exec web   python manage.py import_referentiel apps/referentiel/data/referentiel-onea.csv --user <login-rai> --dry-run
docker compose --env-file .env.prod -f docker/compose.prod.yml exec web   python manage.py import_referentiel apps/referentiel/data/referentiel-onea.csv --user <login-rai>
```

La commande est idempotente et tout ou rien ; format et options : `backend/README.md`.

## 5. Amorçage de Keycloak

Keycloak démarre en mode production (`start`), **sans import de realm, sans realm de
développement, sans utilisateur de test**. Le realm de développement
`docker/keycloak/realm-onea.json` ne doit jamais être importé en production (il contient
des mots de passe de test et un client à accès direct par mot de passe).

0. **Accès à la console d'administration.** `nginx` n'expose publiquement que les
   endpoints OIDC (`/realms/<realm>/`, `/resources/`, `/js/`) ; la console (`/admin/`), le
   realm `master`, `/metrics` et `/health` répondent **404** sauf depuis les adresses
   listées dans `ADMIN_ALLOW_CIDR` (IP ou CIDR séparés par des virgules, par exemple
   `10.20.0.0/16,192.0.2.7` ; vide = personne). Renseigner `ADMIN_ALLOW_CIDR` avec le
   réseau d'administration puis recréer `nginx`
   (`docker compose ... up -d nginx`). Alternative sans rien ouvrir : un tunnel SSH vers une
   machine du réseau d'administration autorisé, qui présente l'adresse allouée.
1. Se connecter à `https://sso.onea.bf/admin/` avec `KEYCLOAK_ADMIN` /
   `KEYCLOAK_ADMIN_PASSWORD`. Créer immédiatement un compte administrateur nominatif
   permanent, puis supprimer l'administrateur temporaire d'amorçage.
2. **Créer le realm** `onea` : nom d'affichage « ONEA - Audit interne », langue par défaut
   `fr`, *Login > User registration* désactivé, *SSL required* = `all`.
3. **Rôles de realm** : `ADMIN`, `RAI`, `AUDITEUR`, `AUDITE`, `DG`.
4. **Profil utilisateur** (*Realm settings > User profile*, éditeur JSON) : déclarer les
   attributs `direction` et `fonction`, modifiables par l'administrateur uniquement
   (l'utilisateur peut les voir mais pas les changer, sinon il pourrait s'attribuer une
   direction) :

   ```json
   {
     "name": "direction",
     "displayName": "Direction",
     "permissions": { "view": ["admin", "user"], "edit": ["admin"] }
   }
   ```

   (idem pour `fonction`). Garder `unmanagedAttributePolicy` à sa valeur par défaut
   (désactivée) : aucun attribut non déclaré ne doit être éditable par l'utilisateur.
5. **Client `onea-frontend`** : public, flux « Standard flow » uniquement (pas d'accès direct
   par mot de passe), PKCE `S256` obligatoire (*Advanced > Proof Key for Code Exchange Code
   Challenge Method*). URI de redirection **exactes** (sans joker) :
   `https://audit.onea.bf/callback`, URI de redirection après déconnexion
   `https://audit.onea.bf/`, *Web origins* `https://audit.onea.bf`.
6. **Client `onea-backend`** : confidentiel (*Client authentication* activée), standard flow,
   pas d'accès direct. Le fichier de secret `oidc_client_secret` (§3.1) existe déjà avec une valeur aléatoire : copier dedans le secret affiché par Keycloak (onglet *Credentials*, §3.3) puis `docker compose ... up -d --force-recreate web worker beat`. Le secret n'est pas utilisé pour valider les jetons (userinfo + JWKS) : il est exigé
   uniquement car mozilla-django-oidc le lit à l'initialisation ; le client reste confidentiel
   par prudence. Le backend ne vérifie que des jetons
   porteurs émis pour `onea-frontend` (`OIDC_ALLOWED_AZP`).
7. **Mappers** (identiques au realm de développement) sur **chacun** des deux clients, de
   type *User Realm Role* / *User Attribute*, ajoutés à l'access token, l'ID token et
   userinfo :

   | Nom | Type | Source | Claim |
   |---|---|---|---|
   | `realm-roles` | User Realm Role (multivalué, String) | rôles de realm | `roles` |
   | `direction` | User Attribute (String) | attribut `direction` | `direction` |
   | `fonction` | User Attribute (String) | attribut `fonction` | `fonction` |

7bis. **Client de service `onea-admin-sync`** (synchronisation des comptes depuis la
   plateforme : activation/désactivation, fermeture de session, recherche). Moindre privilège,
   à ne pas élargir :

   - *Clients > Create client* : `onea-admin-sync`, *Client authentication* activée,
     **Service accounts roles** activé, tous les flux décochés (*Standard flow*, *Direct
     access grants*, *Implicit flow*).
   - Onglet *Service accounts roles* > *Assign role* > filtrer sur les clients >
     `realm-management` : **`view-users` et `manage-users` uniquement**. Aucun rôle de realm,
     jamais `realm-admin`.
   - Onglet *Client scopes* > `onea-admin-sync-dedicated` > *Scope* : désactiver
     *Full scope allowed*, puis *Assign role* > `realm-management` > `view-users` et
     `manage-users` (sans ce mapping de portée, Keycloak répond 403 à tous les appels).
   - Ne **jamais** ajouter `onea-admin-sync` à `OIDC_ALLOWED_AZP` : ses jetons ne doivent pas
     ouvrir de session applicative.
   - Onglet *Credentials* : copier le secret (long et aléatoire) dans le fichier `keycloak_sync_secret` (§3.1, §3.3) ; le backend refuse de démarrer si la valeur est vide, l'espace réservé `CHANGE_ME_*` ou le secret de développement ; puis `docker compose ... up -d --force-recreate web worker beat`.

8. **Protection contre la force brute** (*Realm settings > Security defenses > Brute force
   detection*) : activée, verrouillage temporaire après 5 échecs, durée croissante - **sur
   le realm `onea` et aussi sur le realm `master`** (celui des administrateurs).
   Mêmes valeurs que `scripts/recette/realm.sh` : `failureFactor` 5, `waitIncrementSeconds` 60,
   `maxFailureWaitSeconds` 900, pas de verrouillage permanent.
   **Politique de mots de passe** (*Authentication > Policies > Password policy*), sur `onea`
   et sur `master` : `length(12) and notUsername and passwordHistory(5)`. Pour refuser les
   mots de passe compromis (ASVS 2.1.7), ajouter la règle *Not Recently Used* n'y suffit pas :
   déposer une liste de mots interdits (un mot par ligne) dans le dossier
   `data/password-blacklists/` du conteneur Keycloak et ajouter `passwordBlacklist(<fichier>)`.
   La liste à retenir est **à décider par l'ONEA** (non livrée).
   **Second facteur (OTP, décision D19)** : obligatoire pour les comptes qui ont le rôle `ADMIN`
   du realm `onea` et pour tous les administrateurs du realm `master`. Pour chaque compte
   concerné : *Users* > compte > *Required user actions* > **Configure OTP** ; au
   premier passage, Keycloak impose l'enrôlement d'une application TOTP (RFC 6238, par exemple
   FreeOTP ou Aegis, libres). *Authentication > Policies > OTP Policy* : `totp`, 6 chiffres,
   30 s. Contrôle : se connecter avec le compte ADMIN, le code à usage unique est demandé. Les
   comptes `ADMIN` créés plus tard reçoivent la même action requise à leur création. Perte
   du téléphone : voir le runbook, « Compte verrouillé » (réinitialisation de l'OTP).
9. **Annuaire AD/LDAP** (si l'ONEA fédère ses comptes) : *User federation > Add LDAP
   provider*, mode lecture seule, import des utilisateurs, synchronisation périodique ;
   mapper les groupes AD vers les rôles de realm ci-dessus et les attributs `direction` /
   `fonction` vers les champs LDAP correspondants. À valider avec la DSI avant mise en
   production (connexion LDAPS, compte de service en lecture seule).
10. Créer les premiers utilisateurs (ou les importer depuis l'annuaire) et leur attribuer un
    rôle. Contrôle : ouvrir `https://audit.onea.bf/`, se connecter, vérifier que
    `GET /api/v1/me/` retourne le bon rôle.

Cette configuration est sauvegardée avec `keycloak-db` (voir §7) ; exporter aussi le realm
(*Realm settings > Action > Partial export*) après chaque changement important.

## 6. Mises à jour

```
git pull
docker compose --env-file .env.prod -f docker/compose.prod.yml build
docker compose --env-file .env.prod -f docker/compose.prod.yml up -d
```

Le service `migrate` rejoue les migrations puis la collecte des fichiers statiques à
chaque déploiement, avant le redémarrage de `web`/`worker`/`beat` (modifier `APP_VERSION`
pour changer d'étiquette d'images). **Sauvegarder avant** toute mise à jour
(`sh scripts/backup.sh`). Pour revenir en arrière : réinstaller la version précédente du
code, reconstruire, et restaurer la sauvegarde si une migration a modifié le schéma. Les
images portent l'étiquette `APP_VERSION`.

## 7. Sauvegardes et restauration

Objectifs (D8) : perte maximale **24 h** (RPO), remise en service **4 h** (RTO). L'exercice
automatisé du banc (`scripts/recette/tests/restauration.sh`) vise moins de 30 minutes ; il se
refait **chaque trimestre** en production (runbook).

### 7.1 Ce qui est sauvegardé

`scripts/backup.sh` (en root : le dossier des documents appartient à 10001, mode 0750) écrit, pour un
horodatage `AAAAMMJJ-HHMMSS`, dans le dossier de sauvegarde (défaut `./backups`) :

| Fichier | Contenu |
|---|---|
| `onea-<h>.dump`, `keycloak-<h>.dump` | `pg_dump --format=custom` de la base applicative et de celle de Keycloak |
| `fichiers-<h>.tar.gz` | volume Docker `onea-fichiers` (pièces justificatives du lot 6, `FICHIERS_RACINE`) |
| `documents-<h>.tar.gz` | dossier `DOCUMENTS_HOST_DIR` (documents Word/PDF générés) |
| `manifeste-<h>.sha256` | SHA-256 des quatre fichiers ci-dessus, écrit en dernier |

Les bases sont sauvegardées **avant** les fichiers : tout fichier référencé par un dump est dans
l'archive ; un fichier écrit entre les deux est un *orphelin* inoffensif (écriture unique), signalé
par `verifier_documents --orphelins`, jamais supprimé automatiquement. Le volume `meili-data`
(index) est reconstructible : `restore.sh` relance `manage.py reindexer`.

Chaque artefact est **vérifié** : `pg_restore --list` pour les dumps, `tar -tzf` pour les archives,
`sha256sum -c` pour le manifeste. Un jeu sans manifeste est incomplet ; en cas d'échec, les fichiers
du jeu en cours sont retirés. Quatorze jeux sont conservés localement.

```
sudo sh scripts/backup.sh /srv/onea-backups
```

### 7.2 Copie hors serveur chiffrée (restic) — décision U1

Une sauvegarde qui reste sur le serveur ne protège pas de sa perte. La copie hors serveur utilise
[restic](https://restic.net) (chiffrement et déduplication ; `apt install restic`). Rétention :
7 quotidiennes, 4 hebdomadaires, 12 mensuelles (`restic forget --prune`).

`backup.sh --hors-serveur` **refuse de s'exécuter** (avant toute sauvegarde) sans `RESTIC_REPOSITORY`
et `RESTIC_PASSWORD_FILE` (fichier lisible par root seul, 0600, jamais passé en argument).
Destinations acceptées par restic, à choisir à la décision **U1** :

| Destination | `RESTIC_REPOSITORY` |
|---|---|
| second serveur de l'ONEA en SFTP | `sftp:sauvegarde@serveur2:/srv/restic-onea` (clé SSH de root, sans phrase de passe) |
| NAS ou disque externe monté | `/mnt/nas-onea/restic` (chemin local) |
| stockage S3 interne | `s3:https://s3.onea.bf/onea-sauvegardes` (+ `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` dans l'environnement du service) |
| serveur REST restic | `rest:https://utilisateur@hote:8000/onea` |

Le **mot de passe restic** protège toutes les copies : sans lui, elles sont illisibles. Le confier à
**deux personnes** (coffre ou enveloppe scellée) ; le perdre revient à perdre la copie hors serveur.

```
sudo install -m 0600 /dev/null /etc/onea/restic.pass && sudo sh -c 'openssl rand -hex 32 > /etc/onea/restic.pass'
export RESTIC_REPOSITORY=sftp:sauvegarde@serveur2:/srv/restic-onea RESTIC_PASSWORD_FILE=/etc/onea/restic.pass
sudo -E sh scripts/backup.sh /srv/onea-backups --hors-serveur --initialiser-depot   # première fois seulement
sudo -E sh scripts/backup.sh --verifier-hors-serveur                                # restic snapshots + restic check
```

Sans `--initialiser-depot`, un dépôt absent est une erreur (une faute de frappe ne crée pas un nouveau
dépôt en silence). Tant que U1 n'est pas levée : sauvegardes locales seules.

### 7.3 Minuteries systemd

`docker/ops/` contient la sauvegarde nocturne (`onea-sauvegarde.timer`, **02:00** ; Ouagadougou est à
UTC+0), la vérification hebdomadaire de la copie hors serveur (`onea-verification-sauvegarde.timer`,
**dimanche 05:00**) et `onea-alerte@.service`, déclenché par `OnFailure=` : il envoie par courriel
(`scripts/alerte-mail.sh`, curl SMTP, aucun outil supplémentaire) les dernières lignes du journal.

```
sudo cp docker/ops/onea-sauvegarde.* docker/ops/onea-verification-sauvegarde.* docker/ops/onea-alerte@.service /etc/systemd/system/
sudo systemd-analyze verify /etc/systemd/system/onea-sauvegarde.* /etc/systemd/system/onea-verification-sauvegarde.* /etc/systemd/system/onea-alerte@.service
sudo systemctl daemon-reload && sudo systemctl enable --now onea-sauvegarde.timer onea-verification-sauvegarde.timer
```

Les unités supposent le dépôt dans `/opt/onea` (sinon corriger `WorkingDirectory` et `ExecStart`). La
configuration est dans `/etc/onea/sauvegarde.env` (root, 0600, jamais dans Git) :

```
ONEA_SAUVEGARDE_DIR=/srv/onea-backups
ONEA_SAUVEGARDE_OPTIONS=--hors-serveur          # vide : sauvegardes locales seules
RESTIC_REPOSITORY=sftp:sauvegarde@serveur2:/srv/restic-onea
RESTIC_PASSWORD_FILE=/etc/onea/restic.pass
ALERTE_SMTP_URL=smtp://relais.onea.bf:587       # STARTTLS exigé ; smtps://…:465 ; ALERTE_SMTP_CLAIR=1 pour un relais interne en clair
ALERTE_MAIL_DE=sauvegarde@onea.bf
ALERTE_MAIL_A=dsi@onea.bf,rai@onea.bf
ALERTE_SMTP_UTILISATEUR=sauvegarde               # facultatif
ALERTE_SMTP_MOT_DE_PASSE_FILE=/etc/onea/alerte.pass   # facultatif, 0600
```

Essai de l'alerte : `sudo sh -c 'set -a; . /etc/onea/sauvegarde.env; sh scripts/alerte-mail.sh "Essai ONEA" "Texte de l essai"'`.
Un jeu local reste valable même si la copie restic échoue (l'alerte part, le jeu est conservé).

### 7.4 Restauration

```
sudo sh scripts/restore.sh 20261030-020001 --verifier --dossier /srv/onea-backups   # contrôle seul
sudo sh scripts/restore.sh 20261030-020001 --oui --dossier /srv/onea-backups        # DESTRUCTIF
```

Sans `--oui`, rien n'est modifié. Depuis la copie hors serveur : `restic restore latest --target
/srv/onea-restauration`, puis `--dossier /srv/onea-restauration/srv/onea-backups`. `restore.sh` :

1. contrôle le manifeste et les empreintes (**refus au moindre écart**), la lisibilité des dumps et archives ;
2. arrête `web`, `worker`, `beat`, `keycloak` ;
3. restaure la base applicative puis celle de Keycloak (`pg_restore --clean --if-exists --single-transaction`) ;
4. **relance `installer_gardes_sql`** : les déclencheurs de gel et les droits de `onea_app` (§7bis) sont
   rétablis par le code, pas par confiance dans le dump ;
5. déplace le dossier des documents en `<dossier>-avant-restauration-<horodatage>`, extrait l'archive,
   rétablit 10001:10001 et 0750 ;
6. sauvegarde le volume `onea-fichiers` dans `<dossier de sauvegarde>/avant-restauration-fichiers-<horodatage>.tar.gz`,
   puis le remplace par l'archive ;
7. redémarre la pile, réindexe la recherche ;
8. vérifie : `installer_gardes_sql --verifier --exiger-role`, `verifier_documents` (**code 1** si un fichier
   référencé manque ou est altéré), `verifier_documents --orphelins` (informatif), `verifier_pieces`
   (un orphelin seul est informatif ; une pièce absente ou altérée est une erreur).

Sur un serveur neuf : installer la pile (§4 : secrets, `.env.prod`, images), créer le dossier des
documents (§ `docs/stockage-fichiers.md`), puis lancer `restore.sh` (il démarre `db` et `keycloak-db`).
L'ancien dossier des documents et les copies « avant-restauration » sont à supprimer à la main après
contrôle. Restauration d'un seul document : extraire son fichier de `documents-<h>.tar.gz`
(`tar -xzf … -C <dossier> chemin/du/fichier`), puis `verifier_documents`.

## 7bis. Base de données : rôles, gel et maintenance

**Deux rôles PostgreSQL.**

| Rôle | Usage | Droits |
|---|---|---|
| `POSTGRES_USER` (propriétaire, défaut `onea`) | service `migrate`, sauvegardes, maintenance | propriétaire des tables |
| `POSTGRES_APP_USER` (défaut `onea_app`) | `web`, `worker`, `beat` | `LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT`, jamais propriétaire ; `SELECT`, `INSERT`, `UPDATE` sur les tables ; `DELETE` uniquement sur les tables de liaison générées et `django_session` ; ni `TRUNCATE`, ni `TRIGGER`, ni `CREATE` ; `USAGE`, `SELECT` sur les séquences |

Le mot de passe du propriétaire n'est présent que dans le service `migrate` ; `web`, `worker` et `beat`
reçoivent l'URL du rôle applicatif. Les droits sont réappliqués après chaque migration.

**Gel en base.** Des déclencheurs refusent, même par SQL brut, avec le message
`ERREUR ONEA : <règle>` (SQLSTATE `P0001`) :

- toute suppression physique (`DELETE`) sur les tables des modèles métier (suppression logique seulement) ;
- toute modification ou suppression des tables en ajout seul : confirmations de signature, journaux
  d'événements (étapes, fiches, constats, rapports, suivis), journal d'audit (`auditlog_logentry`), journaux
  de consultation, réponses et avis déposés, rapports provisoires, diffusions, instantanés du programme,
  engagements sur le plan d'actions ;
- la modification des colonnes figées : empreintes, tailles et fichiers d'une version de document prête (seul le
  PDF évolue, une fois), gabarits, numéro et rattachement des documents, pièces justificatives et preuves de mise en
  œuvre, copies figées d'un suivi d'action, relances et notifications (seuls leurs champs d'état changent) ;
- toute écriture sur une cartographie validée, ses risques, un programme annuel validé, ses lignes et leurs entités.

Les gels qui dépendent de l'état d'une mission (suspendue, étape close, rapport diffusé…) restent contrôlés
par l'application : ils admettent des exceptions légitimes (reprise, réouverture).

Le rôle applicatif est refusé deux fois : par le privilège (`permission denied for table …`), puis par le
déclencheur. Le message `ERREUR ONEA` s'observe avec la connexion du propriétaire :

```
docker compose --env-file .env.prod -f docker/compose.prod.yml exec -T db \
  sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DELETE FROM missions_mission"'
```

**Vérification (code de sortie 1 au moindre écart : déclencheur absent, désactivé ou modifié, rôle trop puissant).**

```
docker compose --env-file .env.prod -f docker/compose.prod.yml run --rm migrate \
  python manage.py installer_gardes_sql --verifier --exiger-role
docker compose --env-file .env.prod -f docker/compose.prod.yml exec web \
  python manage.py shell -c "from django.db import connection; c=connection.cursor(); c.execute('select current_user'); print(c.fetchone())"
```

La seconde commande doit afficher `onea_app`. À rejouer après une restauration (`pg_restore`) : elle
détecte un gel absent, et `installer_gardes_sql` (sans option) le répare.

**Procédure de maintenance avec contournement.** Seul le propriétaire (ou un superutilisateur) peut lever le
gel, dans une transaction, avec `SET LOCAL onea.maintenance = 'on'` ; le rôle applicatif n'en tire aucun effet.
Arrêter d'abord `web`, `worker` et `beat`, sauvegarder, puis :

```
docker compose --env-file .env.prod -f docker/compose.prod.yml exec -T db \
  sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
BEGIN;
SET LOCAL onea.maintenance = 'on';
-- commandes de correction, une opération documentée à la fois
COMMIT;
SQL
```

Une migration de données Django qui modifie ou supprime des lignes gelées doit s'exécuter dans
`with apps.core.gardes_sql.maintenance():` (connexion du propriétaire, donc du service `migrate`). Ne jamais
désactiver un déclencheur (`ALTER TABLE … DISABLE TRIGGER`) : `--verifier` le signale.

**Migration d'une base existante (création du rôle et des droits par commande).** Le script
`docker/postgres/initdb/10-role-applicatif.sh` ne s'exécute qu'au premier démarrage d'un volume vide.
Pour une base déjà en service :

1. `sh scripts/backup.sh`, puis ajouter `POSTGRES_APP_USER` à `.env.prod` et créer le fichier de secret `postgres_app_password` (`sh scripts/generer-secrets.sh`, §3.1).
2. Recréer `db` pour y monter les secrets (`docker compose … up -d db`), puis créer le rôle :

   ```
   docker compose --env-file .env.prod -f docker/compose.prod.yml exec -T db sh -c \
     'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
        -v app_user="$POSTGRES_APP_USER" -v app_db="$POSTGRES_DB"' <<'SQL'
   \set app_password `cat /run/secrets/postgres_app_password`
   SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD %L',
                 :'app_user', :'app_password') \gexec
   SELECT format('GRANT CONNECT ON DATABASE %I TO %I', :'app_db', :'app_user') \gexec
   SQL
   ```

3. Déployer : `docker compose --env-file .env.prod -f docker/compose.prod.yml up -d`. Le service `migrate`
   (connexion du propriétaire) pose les déclencheurs et les droits (`post_migrate`), puis `web`, `worker` et
   `beat` redémarrent avec le rôle applicatif. Sans redéploiement :
   `docker compose … run --rm migrate python manage.py installer_gardes_sql`.
4. Vérifier comme ci-dessus (`--verifier --exiger-role`, `select current_user`).

Les lignes existantes ne sont pas contrôlées à la pose des déclencheurs : seules les écritures futures le sont.
Retour arrière : `DROP TRIGGER` des déclencheurs préfixés `onea_` et `REVOKE` des droits du rôle, ou
restauration de la sauvegarde.

Limites connues : un superutilisateur contourne les privilèges (pas les déclencheurs, sauf maintenance) ;
la purge du journal d'audit (`auditlogflush`) exige la maintenance ; `TRUNCATE` par le propriétaire n'est pas
intercepté (ce droit n'est pas accordé au rôle applicatif).
## 8. Variables d'environnement (`.env.prod`)

| Variable | Rôle |
|---|---|
| `PUBLIC_HOST` | nom DNS de l'application (ALLOWED_HOSTS, CORS, CSRF, redirections) |
| `SSO_HOST` | nom DNS de Keycloak (`KC_HOSTNAME`, issuer OIDC) |
| `TLS_CERT_DIR` | répertoire hôte contenant `fullchain.pem` et `privkey.pem` |
| `ADMIN_ALLOW_CIDR` | adresses autorisées pour la console Keycloak (vide = aucune) |
| `SSO_CA_BUNDLE_PATH` | bundle d'AC interne dans le conteneur (`/etc/onea/ca/ca-bundle.pem`), facultatif |
| `APP_VERSION` | étiquette des images `onea-backend` / `onea-frontend` (obligatoire) |
| `DJANGO_ADMIN_ENABLED` | `false` par défaut ; `true` expose `/admin/` |
| `ONEA_SECRETS_DIR` | dossier des fichiers de secrets (root, 0700 ; voir §3.1) : obligatoire |
| `EMAIL_URL` | relais SMTP **sans mot de passe**, ex. `smtp+tls://compte@smtp.onea.bf:587` (le mot de passe est le fichier `email_password`) |
| `POSTGRES_DB`, `POSTGRES_USER` | base applicative (mot de passe : fichier `postgres_password`) |
| `POSTGRES_APP_USER` | rôle applicatif sans privilèges de web, worker, beat (voir §7bis) ; mot de passe : fichier `postgres_app_password` |
| `KEYCLOAK_ADMIN`, `KEYCLOAK_ADMIN_PASSWORD` | administrateur d'amorçage Keycloak |
| `KEYCLOAK_DB_PASSWORD` | mot de passe de la base Keycloak (instance dédiée) |
| `KEYCLOAK_ADMIN_API_CLIENT_ID` | client de service `onea-admin-sync` (voir §5, étape 7bis) ; son secret est le fichier `keycloak_sync_secret` |
| Fichiers de secrets | `secret_key`, `secret_key_fallbacks`, `redis_password`, `oidc_client_secret`, `keycloak_sync_secret`, `meili_master_key`, `metrics_token`, `email_password` : voir §3.1 (ils ne sont plus des variables) |
| `DOCUMENTS_HOST_DIR` | dossier de l'hôte (absolu, hors dépôt) où sont stockés les documents ; monté en `/var/lib/onea/documents` dans `web` et `worker` |
| `THROTTLE_RATE_GENERATION` | limite par utilisateur : génération de document (défaut `20/min`) |
| `THROTTLE_RATE_APERCU` | aperçu de gabarit ou de numérotation (défaut `30/min`) |
| `THROTTLE_RATE_TELEVERSEMENT` | dépôt de fichier (défaut `30/hour`) |
| `THROTTLE_RATE_IMPORT` | import (défaut `10/hour`) |
| `THROTTLE_RATE_EXPORT` | export CSV / Excel (défaut `30/min`) |
| `THROTTLE_RATE_ANNUAIRE` | recherche dans l'annuaire Keycloak/LDAP (défaut `60/min`) |
| `THROTTLE_RATE_ANONYME` | appelant non authentifié, par adresse client (défaut `30/min`) |
| `ANTIVIRUS_MOTEUR` | `clamav` (défaut en production) ; `aucun` est **refusé** au démarrage sauf `ANTIVIRUS_AUTORISER_AUCUN=true` |
| `ANTIVIRUS_ECHEC_FERME` | `true` (défaut) : clamd injoignable ou en erreur, téléversement refusé (503, « Analyse antivirus indisponible : réessayez plus tard. ») ; `false` : accepté sans analyse, journalisé en ERROR (déconseillé) |
| `ANTIVIRUS_AUTORISER_AUCUN` | `false` (défaut) ; `true` accepte par écrit l'absence d'analyse |
| `CLAMAV_MEM_LIMIT` | plafond mémoire du conteneur `clamav` (défaut `3g`) |
| `COMPOSE_PROJECT_NAME`, `WEB_CONCURRENCY` | optionnels |

Le backend en production refuse de démarrer si `SECRET_KEY` (ou `SECRET_KEY_FILE`), `DATABASE_URL`, `EMAIL_URL`,
`ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` ou `OIDC_OP_BASE_URL`
(en `https://`) manquent, ou si `OIDC_VERIFY_SSL=false` : aucune valeur par défaut de développement n'est utilisée.

`CORS_ALLOWED_ORIGINS` est **facultatif** (défaut : vide, aucune origine tierce autorisée) : la SPA
et l'API partagent la même origine derrière `nginx`. Ne le renseigner que pour une SPA hébergée
ailleurs. `CACHE_URL` (facultatif) désigne le cache partagé entre processus (défaut : `REDIS_URL`,
base 1 ; la base 0 sert à Celery).

Les `THROTTLE_RATE_*` s'écrivent `N/sec`, `N/min`, `N/hour` ou `N/day` ; une valeur invalide
empêche le démarrage. Les compteurs sont par utilisateur (indépendants du NAT) ; dépassement :
réponse 429 « Trop de requêtes : réessayez dans {n} secondes. » avec `Retry-After`. Si le cache
est indisponible, la limitation est suspendue et un avertissement est journalisé.

## 9. Notes de sécurité

**Antivirus (SEC-04).** Tout téléversement (gabarits Word, preuves du suivi, pièces justificatives,
import CSV des comptes) est envoyé à ClamAV avant écriture. Taille maximale analysée : 50 Mo
(`ANTIVIRUS_TAILLE_MAX_OCTETS`, alignée sur `client_max_body_size 55m` de nginx ; au-delà : 400
« Le fichier est trop volumineux pour être analysé par l'antivirus. » ; `StreamMaxLength` du démon
est réglé à 55 Mo dans `compose.prod.yml`). Détection : 400 « Le fichier a été refusé par l'analyse
antivirus. ». Aucun code GPL dans l'application : ClamAV n'est atteint que par le réseau.

- TLS est terminé par `nginx` ; Django fait confiance à `X-Forwarded-Proto` uniquement parce
  que `nginx` écrase cet en-tête à chaque requête et que `web` ne publie aucun port. Ne
  jamais exposer gunicorn directement.
- Keycloak écoute en HTTP sur les réseaux privés Docker (terminaison TLS à `nginx`,
  `KC_PROXY_HEADERS=xforwarded`) ; il n'est joignable de l'extérieur qu'en HTTPS via
  `nginx`, qui n'expose que les endpoints OIDC (voir étape 5.0).
- Les en-têtes de sécurité (HSTS, CSP, X-Frame-Options, Referrer-Policy...) sont définis
  **uniquement par nginx** ; ceux émis par Django sont masqués. Django garde les réglages
  `SECURE_*` nécessaires à son bon fonctionnement (redirection HTTPS, en-tête proxy, cookies).
- Authentification de l'API : jeton Bearer Keycloak uniquement. Un cookie de session Django
  n'authentifie jamais `/api/v1/`. En production, `/api/docs/` et `/api/schema/` ne sont
  accessibles que par une session `/admin/` d'un utilisateur staff (les utilisateurs OIDC ne
  sont jamais staff) et exigent `DJANGO_ADMIN_ENABLED=true`.
- Cookies : `__Host-onea-session` et `__Host-onea-csrf` (Secure, HttpOnly, `SameSite=Lax`,
  chemin `/`, sans domaine) ; durée de session 8 h. Toute réponse `/api/` sans en-tête
  `Cache-Control` propre reçoit `no-store, private`.
- Limitation de débit : 20 requêtes/s par adresse sur `/api/` (rafale 40), 5/s sur les
  endpoints d'authentification Keycloak (réponse 429).
- Cache de `userinfo` : la réponse de Keycloak est conservée par jeton (clé = SHA-256 du
  jeton, jamais le jeton) pendant `min(OIDC_USERINFO_CACHE_SECONDES = 60 s, expiration du
  jeton)` ; les réponses 401 et 5xx ne sont pas conservées. Un changement de rôle dans
  Keycloak est donc pris en compte en **60 s au plus** ; la désactivation d'un compte local
  est immédiate (`is_active`, 403). `POST /api/v1/session/fin/` (appelé par la SPA avant la
  déconnexion Keycloak) purge l'entrée du jeton présenté.
- Le code des images est en lecture seule pour l'utilisateur applicatif (non root) ;
  seul `/app/staticfiles` est inscriptible. Les conteneurs tournent avec
  `no-new-privileges` et sans capacités Linux superflues.
- Le cache Django est partagé via Valkey (`CACHE_URL`, défaut `REDIS_URL` base 1, préfixe de
  clés `onea`).
- HSTS (1 an, sous-domaines inclus) est actif : ne pas déployer sans certificat valide.
- Adresse IP enregistrée (confirmations, journal de consultation, piste d'audit) :
  `nginx` transmet l'adresse du pair TCP dans `X-Real-IP`, et Django ne la croit que si le
  pair appartient à `TRUSTED_PROXY_CIDRS` (aussi utilisé pour `--forwarded-allow-ips` de
  gunicorn via `FORWARDED_ALLOW_IPS`) ; ces deux valeurs sont réduites à `ONEA_NGINX_IP`.
  `nginx` écrase `X-Real-IP` et `X-Forwarded-For` par sa propre détermination de l'adresse.
  Si `nginx` est derrière un répartiteur, renseigner `TRUSTED_UPSTREAM_CIDRS` ; sinon
  l'adresse enregistrée est celle de ce dernier, pas celle du poste de l'utilisateur.
- Corps de requête : 1 Mo par défaut, 55 Mo sur `/api/` (pièces justificatives). Journal
  d'accès `nginx` en JSON sur la sortie standard (URI sans chaîne de requête, statut, octets,
  durées, identifiant de requête, adresse du client).
