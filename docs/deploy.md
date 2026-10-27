# Déploiement en production

Ce document décrit l'installation de la plateforme sur un serveur Linux avec Docker Compose
(`docker/compose.prod.yml`). Seul `nginx` publie des ports (80 et 443) ; tous les autres
services vivent sur le réseau privé Docker.

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
`@ : / ? # %`), par exemple `openssl rand -hex 32`. Le fichier n'est jamais commité
(`.gitignore`). Vérification :

```
docker compose --env-file .env.prod -f docker/compose.prod.yml config -q
```

Sans fichier d'environnement complet, la commande échoue en nommant la variable manquante.
Le fichier contient des secrets : le sauvegarder dans un coffre, pas dans le dépôt.

## 4. Premier démarrage

```
docker compose --env-file .env.prod -f docker/compose.prod.yml up -d --build
docker compose --env-file .env.prod -f docker/compose.prod.yml ps
```

Le service `web` applique les migrations et rassemble les fichiers statiques au démarrage.
`https://audit.onea.bf/api/v1/health/` doit répondre `{"status":"ok",...}`. Tant que le
realm Keycloak n'existe pas (section suivante), la connexion à l'application n'est pas
possible.

Le stockage objet (`minio`) est derrière le profil `storage` et **n'est pas démarré** : le
choix de l'image est en attente de décision du maître d'ouvrage, voir
[`docs/infra-minio.md`](infra-minio.md). Une fois l'image choisie (`MINIO_IMAGE` dans
`.env.prod`) : `docker compose ... --profile storage up -d`.

Le site d'administration Django (`/admin/`) est désactivé ; ne l'activer
(`DJANGO_ADMIN_ENABLED=true`) que temporairement pour une opération précise.

## 5. Amorçage de Keycloak

Keycloak démarre en mode production (`start`), **sans import de realm, sans realm de
développement, sans utilisateur de test**. Le realm de développement
`docker/keycloak/realm-onea.json` ne doit jamais être importé en production (il contient
des mots de passe de test et un client à accès direct par mot de passe).

1. Se connecter à `https://sso.onea.bf/` (console d'administration) avec `KEYCLOAK_ADMIN` /
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
   pas d'accès direct. Copier son secret dans `OIDC_RP_CLIENT_SECRET` de `.env.prod` puis
   `docker compose ... up -d web worker beat`. Le backend ne vérifie que des jetons
   porteurs émis pour `onea-frontend` (`OIDC_ALLOWED_AZP`).
7. **Mappers** (identiques au realm de développement) sur **chacun** des deux clients, de
   type *User Realm Role* / *User Attribute*, ajoutés à l'access token, l'ID token et
   userinfo :

   | Nom | Type | Source | Claim |
   |---|---|---|---|
   | `realm-roles` | User Realm Role (multivalué, String) | rôles de realm | `roles` |
   | `direction` | User Attribute (String) | attribut `direction` | `direction` |
   | `fonction` | User Attribute (String) | attribut `fonction` | `fonction` |

8. **Protection contre la force brute** (*Realm settings > Security defenses > Brute force
   detection*) : activée, verrouillage temporaire après 5 échecs, durée croissante.
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

`web` applique les migrations au démarrage. **Sauvegarder avant** toute mise à jour
(`sh scripts/backup.sh`). Pour revenir en arrière : réinstaller la version précédente du
code, reconstruire, et restaurer la sauvegarde si une migration a modifié le schéma. Les
images portent l'étiquette `ONEA_VERSION` (par défaut `latest`).

## 7. Sauvegardes et restauration

`scripts/backup.sh` produit deux dumps PostgreSQL au format custom (application et
Keycloak) dans `./backups` (14 derniers conservés) :

```
sh scripts/backup.sh /srv/onea-backups
```

À planifier chaque nuit (cron) et à copier hors du serveur. Les volumes `meili-data` (index,
reconstructible) et, une fois choisi, le stockage objet des documents sont à sauvegarder
selon la solution retenue.

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

## 8. Variables d'environnement (`.env.prod`)

| Variable | Rôle |
|---|---|
| `PUBLIC_HOST` | nom DNS de l'application (ALLOWED_HOSTS, CORS, CSRF, redirections) |
| `SSO_HOST` | nom DNS de Keycloak (`KC_HOSTNAME`, issuer OIDC) |
| `TLS_CERT_DIR` | répertoire hôte contenant `fullchain.pem` et `privkey.pem` |
| `SECRET_KEY` | clé secrète Django (≥ 50 caractères aléatoires) |
| `DJANGO_ADMIN_ENABLED` | `false` par défaut ; `true` expose `/admin/` |
| `EMAIL_URL` | relais SMTP, ex. `smtp://user:mdp@smtp.onea.bf:587` |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | base applicative |
| `KEYCLOAK_ADMIN`, `KEYCLOAK_ADMIN_PASSWORD` | administrateur d'amorçage Keycloak |
| `KEYCLOAK_DB_PASSWORD` | mot de passe de la base Keycloak (instance dédiée) |
| `OIDC_RP_CLIENT_SECRET` | secret du client confidentiel `onea-backend` |
| `MEILI_MASTER_KEY` | clé maître Meilisearch |
| `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET` | stockage objet (profil `storage`, en attente) |
| `MINIO_IMAGE`, `MINIO_MC_IMAGE` | images du stockage objet, à fixer après décision |
| `COMPOSE_PROJECT_NAME`, `ONEA_VERSION`, `WEB_CONCURRENCY` | optionnels |

Le backend en production refuse de démarrer si `SECRET_KEY`, `DATABASE_URL`, `EMAIL_URL`,
`ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` ou `OIDC_OP_BASE_URL`
(en `https://`) manquent : aucune valeur par défaut de développement n'est utilisée.

## 9. Notes de sécurité

- TLS est terminé par `nginx` ; Django fait confiance à `X-Forwarded-Proto` uniquement parce
  que `nginx` écrase cet en-tête à chaque requête et que `web` ne publie aucun port. Ne
  jamais exposer gunicorn directement.
- Keycloak écoute en HTTP sur le réseau privé Docker (terminaison TLS à `nginx`,
  `KC_PROXY_HEADERS=xforwarded`) ; il n'est joignable de l'extérieur qu'en HTTPS via
  `nginx`. Pour restreindre la console d'administration Keycloak (`/admin/`) à un réseau
  interne, ajouter un `location /admin/ { allow ...; deny all; }` dans le bloc `SSO_HOST` de
  `docker/nginx/prod.conf`.
- HSTS (1 an, sous-domaines inclus) est actif : ne pas déployer sans certificat valide.
