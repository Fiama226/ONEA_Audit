# Déploiement en production

Ce document décrit l'installation de la plateforme sur un serveur Linux avec Docker Compose
(`docker/compose.prod.yml`). Seul `nginx` publie des ports (80 et 443).

Exploitation courante (incidents, mises à jour, restauration, rotation) : [`docs/exploitation/runbook.md`](exploitation/runbook.md). Liste de contrôle de mise en service : [`docs/exploitation/mise-en-production.md`](exploitation/mise-en-production.md).

Réseaux Docker :

| Réseau | Type | Services |
|---|---|---|
| `edge` | standard | nginx (ports 80/443) |
| `web` | `internal`, sous-réseau fixe `ONEA_SUBNET_WEB` (défaut `172.30.10.0/28`) | nginx (adresse fixe `ONEA_NGINX_IP`), web, worker (pas `worker-auth`) |
| `front` | `internal` | nginx, frontend |
| `mail-out` | standard | `worker` et `worker-auth` seuls (sortie SMTP) |
| `backend` | `internal` | web, worker, worker-auth, beat, migrate, db, redis, meilisearch, gotenberg |
| `av` | `internal` | clamav, web, worker (clamd, port 3310, joignable de ces trois services seulement) |
| `av-out` | standard | clamav seul (mise à jour des signatures par freshclam) |

L'authentification est celle de l'application elle-même (sessions Django) : il n'y a plus de
serveur d'identité ni de second nom DNS. `web` n'a aucune sortie : tout courriel part du `worker`.
Chemin d'un courriel d'authentification (code de connexion, code « mot de passe oublié », courriel de
bienvenue, nouveau mot de passe temporaire) : `web` met une tâche en file dans `redis` (réseau
`backend`), le `worker-auth` la prend, émet le code ou relit le mot de passe temporaire (chiffré en base,
1 h au plus) et l'envoie au relais SMTP par `mail-out`. Aucun code ni mot de passe ne passe par
`redis`. Ces trois tâches (`users.envoyer_code_connexion`, `users.envoyer_code_reinitialisation`,
`users.envoyer_mot_de_passe_temporaire`) sont routées vers une file dédiée, **`auth`**
(`CELERY_TASK_ROUTES`), pour ne pas attendre derrière une conversion de document qui peut occuper le
`worker` 8 minutes alors qu'un code de connexion vit 10 minutes. Le service **`worker-auth`**
(`celery -A config worker -n auth@%h -Q auth --concurrency 1 -O fair --prefetch-multiplier 1`, réseaux
`backend` et `mail-out` seulement, secrets `secret_key`, `secret_key_fallbacks`,
`postgres_app_password`, `redis_password`, `meili_master_key`, `email_password`) ne lit que cette file.
Le `worker` principal lance `-Q celery,auth -O fair --prefetch-multiplier 1` : il sert `auth` en
secours. Il peut encore réserver un message `auth` pendant une longue conversion (un par processus) ;
`worker-auth` le prend normalement avant lui. **Un worker lancé à la main doit recevoir
`-Q celery,auth`** : sans `-Q`, il n'envoie aucun courriel d'authentification. Conséquence : **sans
`worker-auth` ni `worker` en marche, aucun courriel d'authentification ne part** (voir §5.5). `gotenberg` n'a aucune route sortante.
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
  valent `ONEA_NGINX_IP` : `nginx` est le seul pair cru. La production refuse de démarrer si
  `TRUSTED_PROXY_CIDRS` est vide ou contient autre chose que des adresses ou réseaux CIDR
  (`ImproperlyConfigured` dans les journaux de `migrate` et `web`) : sans lui, toutes les
  limites par adresse de l'authentification deviendraient un seul compteur pour tout
  l'établissement. Si `ONEA_NGINX_IP` change, recréer tous les services du backend
  (`dc up -d --force-recreate migrate web worker worker-auth beat nginx`).
- `TRUSTED_UPSTREAM_CIDRS` : répartiteurs ou proxys placés devant `nginx` (CIDR, séparés par
  des virgules). Vide (défaut) : `nginx` prend le pair TCP comme adresse du client. Renseigné :
  `X-Forwarded-For` n'est cru que si le pair appartient à ces plages (`realip`), et l'adresse
  du client — utilisée pour les limites de débit, le journal d'accès et la piste d'audit —
  est celle derrière ce proxy.

## 1. Prérequis

- Serveur Linux avec Docker Engine 26+ et le plugin Compose v2 (`docker compose version`).
- Un nom DNS pointant vers le serveur, par exemple `audit.onea.bf` : l'application et son API
  (`/api/`) sont servies sous cette **seule origine**.
- Un certificat TLS couvrant ce nom, délivré par l'autorité de l'ONEA ou une autorité publique.
- Un relais SMTP pour les codes à usage unique et les courriels de bienvenue (§2.3). Sans lui,
  l'application fonctionne en mode dégradé (voir §5).
- 4 Go de RAM minimum (PostgreSQL, Meilisearch, Gotenberg, ClamAV), 20 Go de disque.
- Ports 80 et 443 ouverts ; aucun autre port n'est nécessaire.

## 2. Certificats

Deux voies, au choix de l'ONEA (décision U2). Dans les deux cas, `nginx` lit
`fullchain.pem` (certificat + chaîne) et `privkey.pem` (clé privée) dans le répertoire
`TLS_CERT_DIR`, monté en lecture seule. Le certificat doit couvrir `PUBLIC_HOST`.

```
/etc/onea/certs/fullchain.pem   # certificat + chaîne intermédiaire (0644)
/etc/onea/certs/privkey.pem     # clé privée (chmod 600, propriétaire root)
```

### 2.1 Voie A : autorité de certification interne de l'ONEA

Aucun accès à Internet n'est requis (convient à un serveur sur site).

1. Générer une clé et une demande de signature (CSR) avec le nom de l'application :
   ```
   openssl req -new -newkey rsa:3072 -nodes -keyout privkey.pem -out onea.csr \
     -subj "/CN=audit.onea.bf" \
     -addext "subjectAltName=DNS:audit.onea.bf"
   ```
2. Transmettre `onea.csr` à la DSI (l'AC signe ; la clé ne quitte jamais le serveur).
3. Assembler la chaîne reçue : `cat certificat.pem intermediaire.pem > fullchain.pem`.
4. Déposer les deux fichiers dans `TLS_CERT_DIR` (clé en 0600, propriétaire root).
5. Faire confiance à l'AC côté backend (§ « Autorité de certification interne » plus bas :
   `certs/ca-bundle.pem`, `CA_BUNDLE_PATH`), et distribuer l'AC aux postes de travail.
6. Démarrer ou recharger : `docker compose --env-file .env.prod -f docker/compose.prod.yml exec nginx nginx -s reload`.
7. Renouvellement : refaire les étapes 2 à 4 (ou réutiliser le CSR) **avant l'échéance**, puis
   recharger comme à l'étape 6. Noter l'échéance dans le calendrier de la DSI.

### 2.2 Voie B : Let's Encrypt (défi ACME http-01)

Prérequis, **tous obligatoires** :
- le nom `PUBLIC_HOST` existe dans le DNS **public** et pointe vers ce serveur ;
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

L'application refuse de démarrer sans `EMAIL_URL`, et n'accepte en production que les formes
ci-dessous (toute autre, par exemple `consolemail://`, `filemail://` ou `memorymail://`, est
refusée au démarrage : ces modes écriraient les codes et les mots de passe temporaires dans les
journaux ou sur le disque). Renseigner dans `.env.prod` :

| Mode du relais | `EMAIL_URL` |
|---|---|
| STARTTLS (port 587) | `smtp+tls://compte@smtp.onea.bf:587` |
| TLS implicite (port 465) | `smtps://compte@smtp.onea.bf:465` |
| relais interne en clair (réseau de confiance seulement ; codes et mots de passe temporaires en clair sur le réseau) | `smtp://smtp.onea.bf:25` |
| **pas encore de relais** : aucun courriel n'est envoyé | `dummymail://` |

- Le mot de passe n'est **jamais** dans l'URL : il est dans le fichier de secret `email_password`
  (§3.1). Les caractères spéciaux du compte s'encodent en pourcentage.
- Avec `dummymail://`, l'application fonctionne **sans courriel** : le code de connexion ne peut
  pas être activé, « mot de passe oublié » n'envoie rien (même réponse à l'écran), et les mots de
  passe temporaires (création, réinitialisation, import) s'affichent une fois à l'opérateur (§5.5).
- L'expéditeur est `audit-interne@onea.bf`. La DSI publie les enregistrements **SPF** (autoriser
  l'adresse du relais pour le domaine `onea.bf`) et **DKIM** (clé du relais) ; sans eux, les
  messages risquent d'être classés indésirables.
- Test, depuis la pile démarrée (n'envoie qu'un message, au destinataire indiqué). La commande
  est lancée **dans le `worker`**, seul conteneur qui joint le relais et reçoit le secret
  `email_password` (depuis `web`, elle échouerait toujours) :
  ```
  docker compose --env-file .env.prod -f docker/compose.prod.yml exec worker \
    python manage.py envoyer_courriel_test destinataire@onea.bf
  ```
  La commande affiche le relais, le port et le mode de chiffrement (jamais le mot de passe) ; en
  cas d'échec, elle donne le type d'erreur sans détail sensible. Contrôler ensuite la réception
  (et l'en-tête `Authentication-Results` pour SPF/DKIM).

## 3. Secrets et fichier d'environnement

Les secrets ne sont **jamais** des variables d'environnement : ce sont des **fichiers** générés une fois sur le serveur, montés dans les conteneurs
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
| `secret_key` | web, worker, worker-auth, beat, migrate | clé secrète Django (96 caractères hexadécimaux) |
| `secret_key_fallbacks` | web, worker, worker-auth, beat, migrate | anciennes clés acceptées pendant une rotation, une par ligne ; **vide** au départ |
| `postgres_password` | db, migrate | mot de passe du propriétaire `POSTGRES_USER` |
| `postgres_app_password` | db (création du rôle), web, worker, worker-auth, beat | mot de passe du rôle applicatif `POSTGRES_APP_USER` |
| `redis_password` | redis, web, worker, worker-auth, beat, migrate | mot de passe Valkey |
| `meili_master_key` | meilisearch, web, worker, worker-auth, beat, migrate | clé maître Meilisearch |
| `metrics_token` | web | jeton `Authorization: Bearer` de `/api/v1/metrics/` |
| `email_password` | worker, worker-auth | mot de passe SMTP ; **vide** si le relais n'en exige pas (le mot de passe de `EMAIL_URL` s'applique alors, s'il y en a un) |

**Installation existante (secrets jusqu'ici dans `.env.prod`).** Ne pas laisser le script
inventer des valeurs que la base ou Meilisearch ne connaissent pas : **avant** de le
lancer, écrire les valeurs actuelles dans les fichiers (`printf '%s\n' "$VALEUR" | sudo tee
/etc/onea/secrets/postgres_password >/dev/null`, puis `chmod 0600` et `chown 10001:10001`) pour
`secret_key`, `postgres_password`, `redis_password` et `meili_master_key` ; le script ne crée alors que les fichiers
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

Renseigner le nom DNS (`PUBLIC_HOST`), `ONEA_SECRETS_DIR` (le dossier ci-dessus) et `EMAIL_URL`
**sans mot de passe** (`smtp+tls://compte@smtp.onea.bf:587` ; le mot de passe va dans
`email_password`). `APP_VERSION` est l'étiquette des images (ex. `1.0.0`). Le fichier n'est jamais commité (`.gitignore`). Vérification :

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
| `SECRET_KEY` | 1. `cat /etc/onea/secrets/secret_key >> /etc/onea/secrets/secret_key_fallbacks` (l'ancienne reste acceptée). 2. Écrire une nouvelle valeur dans `secret_key`. 3. `dc up -d --force-recreate web worker worker-auth beat`. 4. Après la durée de vie des sessions (8 h) et des jetons signés, vider le fichier des anciennes clés (`: > .../secret_key_fallbacks`) puis recréer `web worker worker-auth beat`. | aucune (les signatures de l'ancienne clé restent valides pendant la transition) |
| Mot de passe du rôle applicatif | 1. `dc stop web worker worker-auth beat`. 2. Écrire la nouvelle valeur dans `postgres_app_password`. 3. Appliquer avec l'encadré « ALTER ROLE » ci-dessous (la valeur est lue dans le conteneur, jamais passée en argument). 4. `dc up -d --force-recreate web worker worker-auth beat`. | courte (web, worker, worker-auth, beat) |
| Mot de passe du propriétaire | Idem avec `postgres_password` et `POSTGRES_USER` dans l'encadré, puis `dc up -d --force-recreate db migrate`. `POSTGRES_PASSWORD_FILE` n'agit qu'à l'initialisation du volume : l'`ALTER ROLE` est indispensable. Les sauvegardes passent par le socket du conteneur, sans mot de passe. | `migrate` seulement |
| Redis (Valkey) | 1. Écrire la nouvelle valeur dans `redis_password`. 2. `dc up -d --force-recreate redis web worker worker-auth beat migrate`. Les tâches en attente sont conservées (`appendonly`). | courte |
| Meilisearch | 1. Écrire la nouvelle valeur dans `meili_master_key`. 2. `dc up -d --force-recreate meilisearch web worker worker-auth beat migrate`. 3. `dc exec web python manage.py configurer_recherche` puis `dc exec web python manage.py reindexer`. | recherche indisponible quelques minutes |
| Jeton de métriques | Écrire la nouvelle valeur dans `metrics_token`, `dc up -d --force-recreate web`, puis mettre à jour la supervision de l'ONEA (en-tête `Authorization: Bearer`). | aucune |
| Mot de passe SMTP | Écrire la nouvelle valeur dans `email_password`, `dc up -d --force-recreate worker worker-auth`. | aucune |

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

**Fuite avérée** (secret publié, poste perdu) : rotation immédiate de **tous** les secrets
concernés, réinitialisation des mots de passe des comptes concernés (chaque réinitialisation
ferme toutes les sessions du compte, §5), relecture du journal d'audit de la période.

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

Si le certificat du relais SMTP est signé par une autorité interne, le backend doit lui faire
confiance pour joindre le relais en TLS (`smtp+tls://` ou `smtps://`). Créer un fichier
`certs/ca-bundle.pem` à la racine du dépôt contenant **les autorités publiques de confiance
puis l'autorité interne** (la variable remplace le magasin par défaut de Python), puis
renseigner dans `.env.prod` : `CA_BUNDLE_PATH=/etc/onea/ca/ca-bundle.pem`. Le
répertoire `certs/` est monté en lecture seule dans `web` et `worker`
(`SSL_CERT_FILE` pour le relais SMTP, `REQUESTS_CA_BUNDLE` pour les appels HTTPS sortants).
Laisser la variable vide pour un certificat d'autorité publique ou un relais en clair.

## 4. Premier démarrage

```
docker compose --env-file .env.prod -f docker/compose.prod.yml up -d --build
docker compose --env-file .env.prod -f docker/compose.prod.yml ps
```

Le service à usage unique `migrate` (`restart: "no"`) applique les migrations et rassemble
les fichiers statiques dans le volume partagé avec `nginx` ; `web`, `worker` et `beat`
attendent sa fin réussie (`service_completed_successfully`). Si `migrate` échoue, rien
d'autre ne démarre : consulter `docker compose ... logs migrate`.
`https://audit.onea.bf/api/v1/health/` doit répondre `{"status":"ok",...}`. Tant qu'aucun
administrateur n'existe (section suivante), la connexion à l'application n'est pas possible.

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

## 5. Amorçage de l'authentification et gestion des comptes

L'application gère elle-même les identités : sessions Django (cookie `HttpOnly`, `SameSite=Lax`),
mots de passe hachés en Argon2id, comptes créés par un administrateur, code à usage unique
(OTP) envoyé par courriel. Il n'y a **aucun service d'identité à configurer** : ni realm, ni
client, ni secret de synchronisation, ni second nom DNS. Les rôles (ADMIN, RAI, AUDITEUR, AUDITE,
DG) sont attribués dans l'application.

### 5.1 Créer le premier administrateur

La base démarre sans compte. Une fois la pile démarrée (§4), créer l'administrateur initial
depuis le serveur (`dc` = `docker compose --env-file .env.prod -f docker/compose.prod.yml`) :

```
dc exec web python manage.py creer_administrateur --identifiant <identifiant> --courriel <adresse>
```

- La commande affiche **une seule fois** un mot de passe temporaire (16 caractères, valable
  72 h). Il n'est ni journalisé ni enregistré : le noter immédiatement, ne pas le rediriger vers
  un fichier ni le coller dans une messagerie.
- À la première connexion sur `https://<PUBLIC_HOST>/`, l'application impose le choix d'un nouveau
  mot de passe (12 caractères au minimum, mots de passe courants et numériques refusés).
- Relancée sur un administrateur **existant**, la même commande lui donne un nouveau mot de passe
  temporaire, le déverrouille, supprime ses codes en attente et ferme toutes ses sessions. Elle
  refuse un compte qui n'est pas ADMIN (elle ne change jamais un rôle), un compte désactivé
  (le réactiver d'abord dans l'application) et un identifiant qui correspond à plusieurs comptes.
- Créer ensuite un **second administrateur nominatif** (écran *Utilisateurs* > *Nouvel agent*,
  puis changement de rôle) : c'est la voie de secours si le premier perd son accès. Pas de compte
  partagé.
- Contrôle : après connexion, `GET /api/v1/auth/session/` renvoie le rôle ; le journal d'audit
  des comptes garde la trace de l'action (`amorcage_administrateur`).

### 5.2 Créer les comptes des agents

Trois voies, toutes tracées dans la piste d'audit :

1. **Écran *Utilisateurs* > *Nouvel agent*** (administrateur ou délégué ayant le droit de créer
   des comptes) : le rôle est obligatoire ; le compte reçoit un mot de passe temporaire (72 h,
   changement obligatoire à la première connexion). Le **courriel de bienvenue** est mis en file
   d'envoi par défaut (le `worker` l'envoie dans les instants qui suivent) ; si l'envoi est
   décoché, non configuré (`dummymail://`), si le compte n'a pas d'adresse ou si la file
   (`redis`) est injoignable, le mot de passe s'affiche **une seule fois** à l'écran. « Mis en
   file » ne garantit pas la remise : si le `worker` échoue ensuite, voir §5.5.
2. **Import CSV** (écran *Utilisateurs* > *Importer un fichier CSV*, vérification à blanc puis
   import) : colonnes `identifiant`, `email`, `prenom`, `nom`, `role`, `direction`, `fonction`,
   `matricule` (`identifiant` et `role` obligatoires ; 300 lignes et 1 Mo au plus ; le rôle ADMIN
   n'est jamais attribué par import ; l'import est réservé aux administrateurs). Les mots de passe
   qui n'ont pas été mis en file d'envoi sont réunis dans un fichier (chiffré en base) que
   **l'importateur télécharge une seule fois**, dans les 24 h ; il est ensuite détruit (une tâche
   quotidienne purge aussi les fichiers non retirés). Un courriel mis en file puis non remis par le
   `worker` n'est **pas** dans ce fichier : réinitialiser le compte concerné (§5.5).
3. **Ligne de commande** (exploitation), équivalente à l'import CSV :

   ```
   dc exec web python manage.py import_accounts --csv /chemin/comptes.csv                       # vérification à blanc
   dc exec web python manage.py import_accounts --csv /chemin/comptes.csv --apply --by <admin>  # import
   ```

   Options : `--sans-courriel` (aucun courriel de bienvenue) et `--fichier-mots-de-passe CHEMIN`
   (écrit les mots de passe non envoyés dans un **nouveau** fichier local, droits 600, au lieu du
   téléchargement unique). Le fichier CSV doit être lisible dans le conteneur `web`.

### 5.3 Déléguer la gestion des comptes

L'administrateur peut confier à un agent, individuellement et de façon révocable à tout moment,
quatre droits : créer des comptes, réinitialiser les mots de passe (et désactiver le code de
connexion), changer les rôles et la direction, désactiver et réactiver des comptes (fiche de
l'agent, section *Délégation de la gestion des comptes*). Les droits sont relus en base à chaque
requête : un retrait est immédiat. Un délégué ne gère que les comptes **AUDITEUR et AUDITE** :
il n'agit jamais sur un administrateur, un RAI, un DG, un autre délégué ni sur son propre compte,
n'attribue que les rôles Auditeur et Audité (« Seul un administrateur peut attribuer les rôles
Administrateur, Responsable de l'audit interne et Direction générale. »), ne délègue pas et
n'importe pas de CSV. Les comptes RAI et DG (validations, signatures) ne sont gérés que par un
administrateur. **Attention** : un délégué qui peut créer des comptes ou réinitialiser des mots de
passe peut voir des mots de passe temporaires (envoi décoché), donc prendre la main sur un compte
AUDITEUR ou AUDITE ; ne déléguer qu'à des agents de confiance.

### 5.4 Reprise depuis l'ancienne version (comptes existants sans mot de passe)

Les comptes qui s'authentifiaient auparavant par un serveur d'identité externe n'ont pas de mot de
passe local. Après la mise à jour (§6), leur donner un mot de passe temporaire :

```
dc exec web python manage.py donner_mots_de_passe_temporaires --a-blanc     # liste, sans rien modifier
dc exec web python manage.py donner_mots_de_passe_temporaires               # donne et affiche une fois
```

La sortie standard est une liste `identifiant<TABULATION>mot de passe` (à transmettre par un
canal sûr, puis à effacer) ; les mots de passe sont valables 72 h et à changer à la première
connexion. Les comptes qui ont déjà un mot de passe ne sont pas touchés ; les comptes
`is_staff` / `is_superuser` sont seulement signalés (sortie d'erreur) : leur donner un mot de
passe avec `creer_administrateur` ou `changepassword`.

### 5.5 Sans serveur SMTP, ou administrateur bloqué

Tant que le relais SMTP n'est pas fourni (`EMAIL_URL=dummymail://`, §2.3, quel que soit l'hôte indiqué :
ce mode n'est jamais compté comme un envoi), que `worker-auth` et le `worker` sont arrêtés ou que
l'envoi échoue, tout fonctionne sans courriel :

- *mot de passe oublié* : aucun code ne peut partir ; l'agent s'adresse à un administrateur ou
  à un délégué (pour un compte AUDITEUR ou AUDITE ; un administrateur pour un RAI ou un DG) qui
  **réinitialise** son mot de passe en décochant l'envoi (nouveau mot de passe temporaire affiché
  une fois, compte déverrouillé, sessions fermées) ;
- **courriel mis en file mais jamais remis** : `web` ne sait que si le courriel a été confié à la
  file. Si le `worker` échoue ensuite (relais injoignable, adresse refusée), il écrit dans le
  journal de sécurité (`onea.securite`) une ligne `ERROR` « Mot de passe temporaire perdu (<raison>) : compte=<id> envoi=<id>. Réinitialisez le mot de passe avec affichage. » La raison est l'une de : file
  indisponible, identifiant invalide, en attente introuvable, expiré avant l'envoi, compte désactivé,
  illisible après un changement de `SECRET_KEY`, envoi SMTP en échec. **C'est la ligne à surveiller** :
  le mot de passe de ce courriel est perdu (le journal ne le contient jamais ; aucun nouvel essai
  automatique) : l'administrateur refait une **réinitialisation, envoi
  décoché**, et transmet le mot de passe affiché. Même conduite si le `worker` est resté arrêté
  plus d'une heure : les mots de passe en attente ont expiré (même ligne `ERROR`, raison « expiré avant
  l'envoi »). Si la file `redis` est injoignable au moment de la réinitialisation hors transaction, le mot
  de passe est affiché à l'écran ; quand l'appel se fait dans une transaction de l'application, la mise en
  file est différée à sa validation, l'écran répond « mis en file » aussitôt et un échec ultérieur laisse la
  même ligne `ERROR` (raison « file indisponible ») ;
- **`worker-auth` arrêté** : le `worker` principal sert la file `auth` en secours (avec le retard d'une
  conversion éventuellement en cours). Si les deux sont arrêtés, les demandes restent en file dans
  `redis` et sont traitées au redémarrage.
- **`worker` arrêté** : les demandes restent en file dans `redis` et sont traitées à son
  redémarrage (pour l'authentification, par `worker-auth`). Un code est émis au moment où le `worker` traite la demande ; mais une connexion en
  attente de son code expire 10 minutes après la saisie du mot de passe : l'agent recommence alors
  sa connexion. Contrôle : `dc ps worker worker-auth` doit indiquer « healthy » pour les deux ;
- *plafond de la réinitialisation par code* : après 15 codes faux en 24 h sur un compte
  (`AUTH_REINITIALISATION_ECHECS_MAX`), « mot de passe oublié » n'émet plus de code et refuse tout
  code jusqu'à la fin de la fenêtre (journal `ERROR` « Réinitialisation par code bloquée 24 h ») ;
  la réinitialisation par un administrateur ou un délégué reste possible ;
- le **code de connexion par courriel** ne peut être activé que si l'envoi est configuré ; si un
  agent s'est trouvé bloqué après l'avoir activé, un administrateur (ou, pour un compte AUDITEUR
  ou AUDITE, un délégué avec le droit de réinitialiser les mots de passe) le **désactive** depuis
  la fiche du compte (action
  journalisée) ; seul le titulaire peut le réactiver, depuis *Mon compte* ;
- **administrateur bloqué** (code de connexion actif, SMTP en panne, mot de passe perdu) et aucun
  autre administrateur disponible :

  ```
  dc exec web python manage.py creer_administrateur --identifiant <identifiant> --desactiver-otp
  ```

  Nouveau mot de passe temporaire affiché une fois ; le code de connexion est aussi désactivé
  (d'office, même sans l'option, quand l'envoi de courriels n'est pas configuré). Vérifier
  l'identité de la personne avant, et consigner la demande.

### 5.6 Limites de sécurité en vigueur

| Réglage | Valeur |
|---|---|
| Session | 8 h au plus (durée absolue), 30 min d'inactivité ; les requêtes automatiques marquées `X-Onea-Arriere-Plan: 1` (rafraîchissement d'un onglet ouvert) ne comptent pas comme activité ; stockée en base ; à un changement de mot de passe les autres sessions du compte sont fermées, à une réinitialisation toutes |
| Verrouillage d'un compte | 5 échecs consécutifs : 15 min ; réponse identique que le compte existe ou non ; levé par une réinitialisation du mot de passe |
| Code à usage unique (OTP) | 6 chiffres, haché en base, 10 min, 5 essais, usage unique ; codes expirés purgés après 24 h. Code de connexion : au plus `AUTH_CODES_CONNEXION_MAX` (10) codes envoyés par compte et par 15 min (compteur en base, sous verrou de ligne) ; au-delà, aucun nouveau code n'est émis (journal `WARNING`) et le dernier code envoyé reste valable. Un code remplacé par un plus récent est refusé s'il est ressaisi, mais **ne compte pas comme un échec** (ni essai, ni verrouillage, ni plafonds par compte ou par adresse) |
| Réinitialisation par code (« mot de passe oublié ») | au plus 10 codes émis par compte et par 24 h ; au plus 15 codes faux par compte et par 24 h (`AUTH_REINITIALISATION_ECHECS_MAX`), puis plus aucun code émis ni accepté jusqu'à la fin de la fenêtre ; compteurs en base (une panne du cache ne les lève pas) |
| Mot de passe temporaire | 16 caractères aléatoires, 72 h, changement obligatoire à la première connexion ; en attente d'envoi, chiffré en base 1 h au plus |
| Limites de débit par adresse (IPv6 : par /64) | connexion 60/min, code de connexion 30/min, demande de code 20/min, réinitialisation 20/min ; **échecs** : 30 mots de passe ou codes faux (ou comptes inconnus) par 15 min et 30 réinitialisations refusées par heure (code faux, aucun code en cours, compte inconnu), tous comptes confondus, en compteurs atomiques par tranches (réponse 429 avant tout contrôle du mot de passe). Un refus sur un compte verrouillé, désactivé, à mot de passe temporaire expiré ou à réinitialisation bloquée ne compte **qu'une fois par adresse, compte et fenêtre**, que le secret soit bon ou non (le compteur ne révèle donc pas le bon mot de passe) ; un identifiant inconnu compte au plus 5 fois ; un code remplacé ne compte pas : les agents d'un siège derrière un NAT ne se bloquent pas entre eux ; `/admin/login/` soumis aux mêmes limites |
| Limites par identifiant ou par utilisateur | 5 demandes de code par heure et par identifiant saisi ; changement de mot de passe et retrait du code de connexion 10/min par utilisateur ; gestion des comptes 30/h par utilisateur (§8) |
| CSRF | exigé sur toute écriture, y compris la connexion, et vérifié **avant** les limites de débit (une page tierce ne peut pas épuiser le quota d'une adresse) |
| Cookies | `__Host-onea-session` et `__Host-onea-csrf`, `Secure` ; `SESSION_COOKIE_SECURE=true` exigé en production |

Conception et correspondance contrôle / fichier : [`docs/securite/auth-interne-modele.md`](securite/auth-interne-modele.md).

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

**Passage depuis une version qui utilisait Keycloak** (première mise à jour vers l'authentification
interne) :

1. Sauvegarder (`scripts/backup.sh`) : la migration `users.0008_suppression_champs_keycloak`
   supprime les champs de rattachement à l'ancien serveur d'identité.
2. Retirer de `.env.prod` les anciennes variables (`SSO_HOST`, `ADMIN_ALLOW_CIDR`, `KEYCLOAK_*`,
   `OIDC_*`, `CORS_ALLOWED_ORIGINS`, `THROTTLE_RATE_ANNUAIRE`) et renommer `SSO_CA_BUNDLE_PATH` en
   `CA_BUNDLE_PATH` ; supprimer les fichiers de secrets `oidc_client_secret` et
   `keycloak_sync_secret`. Après `up -d --remove-orphans`, les conteneurs `keycloak` et
   `keycloak-db` et leur volume peuvent être supprimés à la main une fois la sauvegarde vérifiée.
3. Les tâches `users.synchroniser_comptes_keycloak` qui seraient encore dans la file Celery au moment
   du déploiement n'existent plus dans le code : le `worker` les rejette (message « unregistered
   task » dans son journal). C'est sans conséquence : elles sont abandonnées et il n'y a rien à
   vider dans Redis.
4. Donner un mot de passe temporaire aux comptes existants : §5.4.

**Mise à jour depuis une version de l'authentification antérieure au second tour de corrections**
(commit `7f6b9dc`) :

1. La migration `users.0011_codes_connexion_et_remplaces` ajoute `User.codes_connexion_emis`,
   `User.codes_connexion_depuis` (compteur des codes de connexion envoyés, hors piste d'audit) et
   `CodeOtp.remplace_le` ; elle passe avec `migrate` au déploiement, comme les autres.
2. La composition de production a un nouveau service, `worker-auth` (§1) : `dc up -d` le crée. Tout
   worker lancé à la main doit recevoir `-Q celery,auth`.
3. `AUTH_REINITIALISATION_ECHECS_MAX` et `AUTH_CODES_CONNEXION_MAX` sont transmis par la composition
   et listés dans `.env.prod.example` (valeurs par défaut `15` et `10`).

## 7. Sauvegardes et restauration

Objectifs (D8) : perte maximale **24 h** (RPO), remise en service **4 h** (RTO). L'exercice
automatisé du banc (`scripts/recette/tests/restauration.sh`) vise moins de 30 minutes ; il se
refait **chaque trimestre** en production (runbook).

### 7.1 Ce qui est sauvegardé

`scripts/backup.sh` (en root : le dossier des documents appartient à 10001, mode 0750) écrit, pour un
horodatage `AAAAMMJJ-HHMMSS`, dans le dossier de sauvegarde (défaut `./backups`) :

| Fichier | Contenu |
|---|---|
| `onea-<h>.dump` | `pg_dump --format=custom` de la base applicative (comptes, empreintes de mots de passe, sessions, journal d'audit) |
| `fichiers-<h>.tar.gz` | volume Docker `onea-fichiers` (pièces justificatives du lot 6, `FICHIERS_RACINE`) |
| `documents-<h>.tar.gz` | dossier `DOCUMENTS_HOST_DIR` (documents Word/PDF générés) |
| `manifeste-<h>.sha256` | SHA-256 des trois fichiers ci-dessus, écrit en dernier |

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
2. arrête `web`, `worker`, `worker-auth`, `beat` ;
3. restaure la base applicative (`pg_restore --clean --if-exists --single-transaction`) ;
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
documents (§ `docs/stockage-fichiers.md`), puis lancer `restore.sh` (il démarre `db`).
L'ancien dossier des documents et les copies « avant-restauration » sont à supprimer à la main après
contrôle. Restauration d'un seul document : extraire son fichier de `documents-<h>.tar.gz`
(`tar -xzf … -C <dossier> chemin/du/fichier`), puis `verifier_documents`.

## 7bis. Base de données : rôles, gel et maintenance

**Deux rôles PostgreSQL.**

| Rôle | Usage | Droits |
|---|---|---|
| `POSTGRES_USER` (propriétaire, défaut `onea`) | service `migrate`, sauvegardes, maintenance | propriétaire des tables |
| `POSTGRES_APP_USER` (défaut `onea_app`) | `web`, `worker`, `worker-auth`, `beat` | `LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT`, jamais propriétaire ; `SELECT`, `INSERT`, `UPDATE` sur les tables ; `DELETE` uniquement sur les tables de liaison générées, `django_session` et les trois tables des données d'identification transitoires (`users_codeotp`, `users_envoimotdepasse`, `users_fichiermotsdepasse` : codes à usage unique, mots de passe temporaires en attente d'envoi, fichiers de mots de passe d'un import, détruits à l'usage et par la purge quotidienne) ; ni `TRUNCATE`, ni `TRIGGER`, ni `CREATE` ; `USAGE`, `SELECT` sur les séquences |

Le mot de passe du propriétaire n'est présent que dans le service `migrate` ; `web`, `worker`, `worker-auth` et `beat`
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
Arrêter d'abord `web`, `worker`, `worker-auth` et `beat`, sauvegarder, puis :

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
   (connexion du propriétaire) pose les déclencheurs et les droits (`post_migrate`), puis `web`, `worker`, `worker-auth` et
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
| `PUBLIC_HOST` | nom DNS de l'application, **seule origine** (SPA et `/api/`) : `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` (`https://<PUBLIC_HOST>`), certificat TLS |
| `TLS_CERT_DIR` | répertoire hôte contenant `fullchain.pem` et `privkey.pem` |
| `CA_BUNDLE_PATH` | bundle d'AC interne dans le conteneur (`/etc/onea/ca/ca-bundle.pem`), facultatif : sert au relais SMTP en TLS (voir « Autorité de certification interne ») |
| `APP_VERSION` | étiquette des images `onea-backend` / `onea-frontend` (obligatoire) |
| `DJANGO_ADMIN_ENABLED` | `false` par défaut ; `true` expose `/admin/` |
| `ONEA_SECRETS_DIR` | dossier des fichiers de secrets (root, 0700 ; voir §3.1) : obligatoire |
| `EMAIL_URL` | relais SMTP **sans mot de passe** : `smtp+tls://` (STARTTLS), `smtps://` (TLS implicite) ou `smtp://` (clair, relais interne), ex. `smtp+tls://compte@smtp.onea.bf:587` (le mot de passe est le fichier `email_password`, lu par le `worker` seul) ; ou `dummymail://` pour fonctionner sans courriel ; **toute autre forme est refusée au démarrage** (§2.3). Sert aux codes à usage unique, aux courriels de bienvenue et aux mots de passe temporaires, tous envoyés par le `worker` ; délai d'attente de 10 s par envoi (`EMAIL_TIMEOUT`, fixé par `config/settings/prod.py`, non configurable par l'environnement) |
| `SESSION_COOKIE_SECURE` | `true` : posé par `docker/compose.prod.yml` ; la production refuse de démarrer si la variable est absente ou fausse |
| `CSRF_TRUSTED_ORIGINS` | posé par `docker/compose.prod.yml` à `https://${PUBLIC_HOST}` ; obligatoire pour le backend de production |
| `POSTGRES_DB`, `POSTGRES_USER` | base applicative (mot de passe : fichier `postgres_password`) |
| `POSTGRES_APP_USER` | rôle applicatif sans privilèges de web, worker, beat (voir §7bis) ; mot de passe : fichier `postgres_app_password` |
| Fichiers de secrets | `secret_key`, `secret_key_fallbacks`, `redis_password`, `meili_master_key`, `metrics_token`, `email_password` : voir §3.1 (ils ne sont plus des variables) |
| `DOCUMENTS_HOST_DIR` | dossier de l'hôte (absolu, hors dépôt) où sont stockés les documents ; monté en `/var/lib/onea/documents` dans `web` et `worker` |
| `THROTTLE_RATE_GENERATION` | limite par utilisateur : génération de document (défaut `20/min`) |
| `THROTTLE_RATE_APERCU` | aperçu de gabarit ou de numérotation (défaut `30/min`) |
| `THROTTLE_RATE_TELEVERSEMENT` | dépôt de fichier (défaut `30/hour`) |
| `THROTTLE_RATE_IMPORT` | import (défaut `10/hour`) |
| `THROTTLE_RATE_EXPORT` | export CSV / Excel (défaut `30/min`) |
| `THROTTLE_RATE_ANONYME` | appelant non authentifié, par adresse client (défaut `30/min`) |
| `THROTTLE_RATE_CONNEXION` | connexion (`POST /api/v1/auth/login/` et `/admin/login/`), par adresse client (défaut `60/min`, dimensionné pour un siège derrière une seule adresse NAT) ; le verrouillage du compte (5 échecs, 15 min) s'y ajoute |
| `THROTTLE_RATE_CONNEXION_CODE` | saisie du code de connexion, par adresse client (défaut `30/min`) |
| `THROTTLE_RATE_MOT_DE_PASSE_OUBLIE_IP` | demandes de code « mot de passe oublié », par adresse client (défaut `20/min`) |
| `THROTTLE_RATE_REINITIALISATION` | réinitialisation avec le code reçu, par adresse client (défaut `20/min`) |
| `THROTTLE_RATE_ECHECS_CONNEXION` | **échecs** de connexion (mot de passe ou code de connexion faux : chaque refus ; identifiant inconnu : au plus 5 par identifiant ; compte verrouillé, désactivé ou à mot de passe temporaire expiré : une seule unité par compte, bon ou mauvais secret) par adresse client, tous comptes confondus (défaut `30/15min`) ; au-delà, la connexion depuis cette adresse répond 429 jusqu'à la fin de la fenêtre, sans verrouiller de compte. Derrière un NAT, tout le site partage ce budget : l'augmenter (par exemple `60/15min`) si des agents sont gênés |
| `THROTTLE_RATE_ECHECS_REINITIALISATION` | réinitialisations refusées par adresse client, tous comptes confondus (défaut `30/hour`) ; chaque refus (code faux, aucun code en cours, compte inconnu, désactivé ou bloqué) compte **de la même façon, au plus 5 fois par identifiant saisi**, adresse et fenêtre : le compteur ne dit rien de l'identifiant ; un code remplacé ne compte pas |
| `THROTTLE_RATE_ECHECS_TOUS` | **tous les refus**, de toute nature et quel que soit le secret (connexion, code de connexion, réinitialisation, `/admin/login/`), par adresse client (défaut `120/15min`) : borne le travail de hachage Argon2 qu'une adresse peut provoquer sans être authentifiée, en laissant de la marge à un siège derrière un NAT. Indépendant du secret, il ne révèle aucun mot de passe |
| `THROTTLE_RATE_CHANGEMENT_MOT_DE_PASSE` | changement de son mot de passe et retrait de son code de connexion, **par utilisateur** (défaut `10/min`) |
| `THROTTLE_RATE_MOT_DE_PASSE_OUBLIE` | demandes de code « mot de passe oublié », par identifiant saisi (défaut `5/hour`) ; en plus, au plus 10 codes par compte et par 24 h, comptés en base, sans effet visible sur la réponse |
| `AUTH_REINITIALISATION_ECHECS_MAX` | codes de réinitialisation faux acceptés par compte et par 24 h (défaut `15`) ; au-delà, plus aucun code émis ni accepté pour ce compte jusqu'à la fin de la fenêtre. Entier strictement positif exigé : `0`, `-1` ou `abc` arrêtent le démarrage (`ImproperlyConfigured`). Transmis aux conteneurs par `x-backend-env` de `docker/compose.prod.yml` et listé (commenté) dans `.env.prod.example` |
| `AUTH_CODES_CONNEXION_MAX` | codes de connexion envoyés par compte et par 15 min (défaut `10`) ; entier strictement positif exigé (même refus au démarrage) ; transmis par `x-backend-env`, listé dans `.env.prod.example` |
| `THROTTLE_RATE_GESTION_COMPTES` | création de compte, réinitialisation de mot de passe et désactivation du code de connexion, par l'administrateur ou un délégué, par utilisateur (défaut `30/hour`) |
| `ANTIVIRUS_MOTEUR` | `clamav` (défaut en production) ; `aucun` est **refusé** au démarrage sauf `ANTIVIRUS_AUTORISER_AUCUN=true` |
| `ANTIVIRUS_ECHEC_FERME` | `true` (défaut) : clamd injoignable ou en erreur, téléversement refusé (503, « Analyse antivirus indisponible : réessayez plus tard. ») ; `false` : accepté sans analyse, journalisé en ERROR (déconseillé) |
| `ANTIVIRUS_AUTORISER_AUCUN` | `false` (défaut) ; `true` accepte par écrit l'absence d'analyse |
| `CLAMAV_MEM_LIMIT` | plafond mémoire du conteneur `clamav` (défaut `3g`) |
| `COMPOSE_PROJECT_NAME`, `WEB_CONCURRENCY` | optionnels |

Le backend en production refuse de démarrer si `SECRET_KEY` (ou `SECRET_KEY_FILE`), `DATABASE_URL`, `EMAIL_URL`,
`ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` ou `SESSION_COOKIE_SECURE` manquent, ou si `SESSION_COOKIE_SECURE`
n'est pas vrai : aucune valeur par défaut de développement n'est utilisée.

La SPA et l'API partagent la **même origine** derrière `nginx` : il n'y a pas de CORS avec
identifiants (aucune variable `CORS_*`). `CACHE_URL` (facultatif) désigne le cache partagé entre processus (défaut : `REDIS_URL`,
base 1 ; la base 0 sert à Celery).

Les `THROTTLE_RATE_*` s'écrivent `N/sec`, `N/min`, `N/hour` ou `N/day` ; ceux de
l'authentification acceptent aussi un multiple de la période (`30/15min`). Une valeur invalide
empêche le démarrage. Les compteurs métier (génération, export, gestion des comptes…) sont par
utilisateur (indépendants du NAT) ; ceux de l'authentification sont par adresse client (IPv6 :
par /64), sauf `MOT_DE_PASSE_OUBLIE` (par identifiant saisi) et `CHANGEMENT_MOT_DE_PASSE` (par
utilisateur). Dépassement : réponse 429 « Trop de requêtes : réessayez dans {n} secondes. » avec
`Retry-After`. Si le cache est indisponible, la limitation est suspendue et un avertissement est
journalisé ; le verrouillage des comptes et les plafonds de la réinitialisation, en base, restent
appliqués.

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
- Les en-têtes de sécurité (HSTS, CSP, X-Frame-Options, Referrer-Policy...) sont définis
  **uniquement par nginx** ; ceux émis par Django sont masqués. Django garde les réglages
  `SECURE_*` nécessaires à son bon fonctionnement (redirection HTTPS, en-tête proxy, cookies).
- Authentification de l'API : session ouverte par `POST /api/v1/auth/login/` (cookie de
  session `HttpOnly`, protection CSRF sur les écritures) ; un en-tête `Authorization: Bearer`
  n'authentifie rien. En production, `/api/docs/` et `/api/schema/` ne sont accessibles qu'à une
  session ouverte de la même façon par un compte `is_staff` (les comptes créés par
  l'application ne le sont pas).
- Cookies : `__Host-onea-session` et `__Host-onea-csrf` (Secure, HttpOnly, `SameSite=Lax`,
  chemin `/`, sans domaine) ; session de 8 h au plus et 30 min d'inactivité. Toute réponse `/api/` sans en-tête
  `Cache-Control` propre reçoit `no-store, private`.
- Limitation de débit : 50 requêtes/s par adresse sur `/api/` (rafale 100, zone `onea_api` de
  `docker/nginx/prod.conf`, réponse 429), puis, dans l'application, les `THROTTLE_RATE_*`
  (un compteur par point d'entrée de l'authentification, plafonds d'échecs par adresse, gestion
  des comptes), le verrouillage des comptes et les plafonds de la réinitialisation par code (§5.6).
- `/admin/` (si `DJANGO_ADMIN_ENABLED=true`) : connexion soumise aux limites de la connexion de
  l'API ; `/admin/password_change/` répond 404 (un mot de passe se change dans l'application) ;
  une session admin n'a pas de délai d'inactivité de 30 minutes (constat AUTH-09, ouvert) :
  laisser l'admin désactivé en production sauf besoin ponctuel.
- Rôle, désactivation et délégation d'un compte sont relus en base à **chaque requête** (aucun
  cache d'identité) : une désactivation, un changement de rôle ou un retrait de délégation
  prennent effet à la requête suivante.
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
