# Déploiement en production

Ce document décrit l'installation de la plateforme sur un serveur Linux avec Docker Compose
(`docker/compose.prod.yml`). Seul `nginx` publie des ports (80 et 443).

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
| `kc` | `internal` | keycloak, keycloak-db |

`nginx` porte l'alias réseau `${SSO_HOST}` sur `web` : `web` et `worker` joignent le SSO à
travers `nginx`, sans passer par l'adresse publique. Les ports 8080 et 9000 de Keycloak ne
sont joignables que depuis `nginx` (réseau `sso`). `web` n'a aucune sortie : tout courriel
part du `worker` (tâche Celery) via `mail-out`. `gotenberg` n'a aucune route sortante.
Redis (Valkey) exige un mot de passe (`REDIS_PASSWORD`).

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

Créer un répertoire protégé contenant exactement deux fichiers :

```
/etc/onea/certs/fullchain.pem   # certificat + chaîne intermédiaire
/etc/onea/certs/privkey.pem     # clé privée (chmod 600, propriétaire root)
```

Le répertoire est monté en lecture seule dans `nginx` (variable `TLS_CERT_DIR`). Au
renouvellement, remplacer les fichiers puis recharger :
`docker compose --env-file .env.prod -f docker/compose.prod.yml exec nginx nginx -s reload`.

## 3. Fichier d'environnement

```
cp .env.prod.example .env.prod
chmod 600 .env.prod
```

Remplacer **toutes** les valeurs `CHANGE_ME` par des secrets aléatoires (URL-safe, sans
`@ : / ? # %`), par exemple `openssl rand -hex 32`. Exceptions : `OIDC_RP_CLIENT_SECRET`
reste un **espace réservé** (n'importe quelle valeur non vide) jusqu'à l'étape 5.6, où le
vrai secret du client `onea-backend` est collé ; `APP_VERSION` est l'étiquette des images
(ex. `1.0.0`). Le fichier n'est jamais commité (`.gitignore`). Vérification :

```
docker compose --env-file .env.prod -f docker/compose.prod.yml config -q
```

Sans fichier d'environnement complet, la commande échoue en nommant la variable manquante.
Le fichier contient des secrets : le sauvegarder dans un coffre, pas dans le dépôt.

Note : les secrets sont transmis aux conteneurs par variables d'environnement. Toute
personne pouvant exécuter `docker inspect` (groupe `docker`, donc équivalent root sur le
serveur) les lit : limiter strictement l'accès au groupe `docker` et à `.env.prod`.

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
   pas d'accès direct. Copier son secret (onglet *Credentials*) dans `OIDC_RP_CLIENT_SECRET`
   de `.env.prod` (en remplacement de l'espace réservé) puis
   `docker compose ... up -d web worker beat`. Le secret n'est pas utilisé pour valider les jetons (userinfo + JWKS) : il est exigé
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
   - Onglet *Credentials* : copier le secret (long et aléatoire) dans
     `KEYCLOAK_ADMIN_API_CLIENT_SECRET` de `.env.prod` (le backend refuse de démarrer si la
     valeur est vide, l'espace réservé `CHANGE_ME_*` ou le secret de développement), puis
     `docker compose ... up -d web worker beat`.

8. **Protection contre la force brute** (*Realm settings > Security defenses > Brute force
   detection*) : activée, verrouillage temporaire après 5 échecs, durée croissante - **sur
   le realm `onea` et aussi sur le realm `master`** (celui des administrateurs).
   Politique de mots de passe : longueur minimale 12.
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

`scripts/backup.sh` produit deux dumps PostgreSQL au format custom (application et
Keycloak) dans `./backups` (14 derniers conservés) :

```
sh scripts/backup.sh /srv/onea-backups
```

À planifier chaque nuit (cron) et à copier hors du serveur. Le script archive aussi le
dossier des documents (`documents-AAAAMMJJ-HHMMSS.tar.gz`, après les bases). Le volume
`meili-data` (index) est reconstructible et n'est pas sauvegardé. Procédure de
restauration complète : [`docs/stockage-fichiers.md`](stockage-fichiers.md).

Restauration de la base applicative :

```
docker compose --env-file .env.prod -f docker/compose.prod.yml stop web worker beat
docker compose --env-file .env.prod -f docker/compose.prod.yml exec -T db \
  sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' \
  < /srv/onea-backups/onea-AAAAMMJJ-HHMMSS.dump
docker compose --env-file .env.prod -f docker/compose.prod.yml start web worker beat
```

Même procédure pour Keycloak avec le service `keycloak-db` (arrêter `keycloak` pendant la
restauration). Tester la restauration régulièrement sur un serveur de recette.

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

1. `sh scripts/backup.sh`, puis ajouter `POSTGRES_APP_USER` et `POSTGRES_APP_PASSWORD` (sans caractères
   spéciaux) à `.env.prod`.
2. Créer le rôle :

   ```
   docker compose --env-file .env.prod -f docker/compose.prod.yml exec -T db sh -c \
     'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
        -v app_user="$POSTGRES_APP_USER" -v app_password="$POSTGRES_APP_PASSWORD" -v app_db="$POSTGRES_DB"' <<'SQL'
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
| `REDIS_PASSWORD` | mot de passe Valkey (intégré dans `REDIS_URL` : sans caractères spéciaux) |
| `SECRET_KEY` | clé secrète Django (≥ 50 caractères aléatoires) |
| `DJANGO_ADMIN_ENABLED` | `false` par défaut ; `true` expose `/admin/` |
| `EMAIL_URL` | relais SMTP, ex. `smtp+tls://user:mdp@smtp.onea.bf:587` |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | base applicative |
| `POSTGRES_APP_USER`, `POSTGRES_APP_PASSWORD` | rôle applicatif sans privilèges de web, worker, eat (voir §7bis) ; obligatoires |
| `KEYCLOAK_ADMIN`, `KEYCLOAK_ADMIN_PASSWORD` | administrateur d'amorçage Keycloak |
| `KEYCLOAK_DB_PASSWORD` | mot de passe de la base Keycloak (instance dédiée) |
| `OIDC_RP_CLIENT_SECRET` | secret du client confidentiel `onea-backend` ; non utilisé par le chemin Bearer, requis seulement car mozilla-django-oidc le lit à l'initialisation |
| `KEYCLOAK_ADMIN_API_CLIENT_ID`, `KEYCLOAK_ADMIN_API_CLIENT_SECRET` | client de service `onea-admin-sync` (voir §5, étape 7bis) ; secret obligatoire |
| `MEILI_MASTER_KEY` | clé maître Meilisearch |
| `DOCUMENTS_HOST_DIR` | dossier de l'hôte (absolu, hors dépôt) où sont stockés les documents ; monté en `/var/lib/onea/documents` dans `web` et `worker` |
| `THROTTLE_RATE_GENERATION` | limite par utilisateur : génération de document (défaut `20/min`) |
| `THROTTLE_RATE_APERCU` | aperçu de gabarit ou de numérotation (défaut `30/min`) |
| `THROTTLE_RATE_TELEVERSEMENT` | dépôt de fichier (défaut `30/hour`) |
| `THROTTLE_RATE_IMPORT` | import (défaut `10/hour`) |
| `THROTTLE_RATE_EXPORT` | export CSV / Excel (défaut `30/min`) |
| `THROTTLE_RATE_ANNUAIRE` | recherche dans l'annuaire Keycloak/LDAP (défaut `60/min`) |
| `THROTTLE_RATE_ANONYME` | appelant non authentifié, par adresse client (défaut `30/min`) |
| `COMPOSE_PROJECT_NAME`, `WEB_CONCURRENCY` | optionnels |

Le backend en production refuse de démarrer si `SECRET_KEY`, `DATABASE_URL`, `EMAIL_URL`,
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
