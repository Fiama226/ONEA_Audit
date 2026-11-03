# Backend

Django 5 / DRF. Settings are split in `config/settings/{base,dev,test,prod}.py`.

## Environment

Variables are read from the repository-root `.env` (shared with docker compose),
or from the process environment:

| Variable | Notes |
|---|---|
| `SECRET_KEY` | required in prod |
| `ALLOWED_HOSTS` | comma-separated |
| `CORS_ALLOWED_ORIGINS` | comma-separated |
| `DATABASE_URL` | e.g. `postgres://onea:onea@localhost:5432/onea` (tests need PostgreSQL) |
| `REDIS_URL` | e.g. `redis://localhost:6379/0` (Celery broker and result backend) |
| `EMAIL_URL` | default `smtp://mailpit:1025` (compose network); `smtp://localhost:1025` on the host |
| `OIDC_OP_BASE_URL` | Keycloak realm URL, default `http://localhost:8080/realms/onea`; auth/token/userinfo/JWKS endpoints derive from it |
| `OIDC_RP_CLIENT_ID` | default `onea-backend` |
| `OIDC_ALLOWED_AZP` | comma-separated Keycloak clients whose tokens are accepted (`azp`), default `onea-frontend` (`onea-dev-cli` added in dev/test) |
| `OIDC_RP_CLIENT_SECRET` | unused by the Bearer path (userinfo + JWKS); only required because mozilla-django-oidc reads it at init (empty default in dev/test, mandatory in prod) |
| `OIDC_VERIFY_SSL` | default `true`; prod refuses `false` |

In prod, `OIDC_OP_BASE_URL` is required and must start with `https://`.

If Keycloak is unreachable or answers 5xx, protected endpoints answer 503 (not 401), so
clients do not drop their session during an outage.

The API accepts `Authorization: Bearer <Keycloak access token>` (verified via the userinfo
endpoint). The local role comes only from the `roles` claim (ADMIN > RAI > AUDITEUR > DG >
AUDITE, default AUDITE) and is re-synced on every request.

API schema and docs (`/api/schema/`, `/api/docs/`) are anonymous in dev/test and admin-only in prod.

## Celery and email

`send_mail_task.delay(...)` raises `kombu.exceptions.OperationalError` to the caller when
the broker (Redis) is down. Callers (services) must catch it and decide: fail the business
action or log and continue. Plain-text email parts are rendered without HTML escaping; HTML
parts stay autoescaped.

## Référentiel : chargement initial

La plateforme démarre **à vide** : aucune migration de données, aucun seed automatique, aucun
écran d'import. Les directions, départements et processus de l'ONEA se chargent uniquement par
la commande explicite `import_referentiel`, lancée par l'exploitant à la demande du RAI.
**Aucun risque n'est importé** : la cartographie des risques est saisie à l'écran par le RAI.

```
python manage.py import_referentiel <fichier.csv> --user <login> [--dry-run]
```

- `--user` (obligatoire) : identifiant d'un utilisateur actif de rôle RAI ou ADMIN ; il signe
  la piste d'audit (`/api/v1/audit-log/`). Le compte doit déjà exister : il est créé à la
  première connexion de la personne via Keycloak ; la commande ne crée aucun utilisateur.
- `--dry-run` : valide le fichier et affiche ce qui serait créé ou mis à jour, sans rien écrire.
- **Idempotente** : upsert par code, jamais de suppression. Une seconde exécution du même
  fichier ne change rien (tout est compté « inchangé »). **Tout ou rien** : à la moindre erreur
  de validation, rien n'est écrit et les erreurs sont listées en français, ligne par ligne.
- Limites : 5 000 lignes et 5 Mio au plus. Comptez environ 35 à 40 ms par ligne, soit près de
  3 minutes pour 5 000 lignes.

Format : UTF-8 (BOM toléré), séparateur `;`, en-tête exact
`type;code;libelle;famille;ordre;parent;directions`. Les directions et départements sont lus
avant les processus. `type` vaut `DIRECTION`, `DEPARTEMENT` (colonne `parent` = code de sa
direction) ou `PROCESSUS` (`famille` = `PILOTAGE`, `REALISATION` ou `SUPPORT`, `directions` =
codes séparés par des virgules).

```
type;code;libelle;famille;ordre;parent;directions
DIRECTION;DAI;Département Audit Interne;;;;
DEPARTEMENT;DAI-QUAL;Cellule qualité de l'audit;;;DAI;
PROCESSUS;EST;Élaborer et mettre en œuvre la stratégie;PILOTAGE;1;;DAI
```

Fichier de référence livré : `apps/referentiel/data/referentiel-onea.csv` (17 directions et
11 processus). Les noms de directions y sont des développements des sigles du document source
et **doivent être confirmés par l'ONEA** avant la mise en production
(voir `apps/referentiel/data/README.md`). Exemple, sur une base vide :

```
python manage.py import_referentiel apps/referentiel/data/referentiel-onea.csv --user rai --dry-run
python manage.py import_referentiel apps/referentiel/data/referentiel-onea.csv --user rai
```

## Référentiel : export et droits

`GET /api/v1/risk-maps/{id}/export/?type=csv|xlsx` télécharge la cartographie (le paramètre est
`type`, pas `format`, réservé par DRF). CSV : UTF-8 avec BOM, séparateur `;`, ouverture directe
dans Excel ; XLSX : feuilles « Risques » et « Matrice ». Les cellules commençant par `=`, `+`,
`-` ou `@` sont neutralisées. Les boutons « Exporter en CSV / Excel » de l'écran d'une
cartographie appellent cette route.

Le gel d'une cartographie validée porte sur ses risques ; les libellés des processus et des
objets auditables restent ceux du référentiel vivant. L'export d'une cartographie validée
affiche donc les libellés actuels (l'historique des renommages est dans la piste d'audit). Pour
la même raison, un processus ou un objet utilisé par une cartographie validée ne peut pas être
supprimé.

| Ressource (`/api/v1/…`) | ADMIN | RAI | AUDITEUR | DG | AUDITE |
|---|---|---|---|---|---|
| `directions/`, `processes/` | lecture, écriture | lecture, écriture | lecture | lecture | lecture |
| `auditable-objects/`, `risk-maps/` (matrice, comparaison, export), `risks/` | lecture | lecture, écriture | lecture | lecture | **403** |

Une cartographie validée est figée (aucune modification ni suppression, 422) ; l'année
suivante se crée par copie d'une version validée.

## Missions : cycle de vie, droits et confirmation

**Prérequis.** Une mission ne peut être créée que si une cartographie des risques est validée
(`risk-maps/{id}/validate/`) ; sinon l'API répond 422 sur `errors.cartographie`. La mission garde
la cartographie qui était validée à sa création, même si une version plus récente est validée
ensuite.

### Cycle de vie

`BROUILLON` (saisie du RAI) → **planifier** → `PLANIFIEE` (inscrite au programme, référence
`DAI/AAAA/Mnn` attribuée, unique même en concurrence) → **lancer** → `EN_PLANIFICATION` (l'étape I
passe « En cours »). Les phases suivantes (`EN_ACCOMPLISSEMENT`, `EN_COMMUNICATION`) s'enchaînent
automatiquement quand les étapes I–X, puis XI–XIV, sont closes et que leur jalon est validé. La
mission peut être **suspendue** (motif) puis reprise, ou **annulée** (motif, définitif). Seul un
brouillon se supprime (suppression logique). Une mission suspendue, annulée ou clôturée refuse
toute écriture sur elle-même et ses objets (422). Les statuts `RAPPORT_DIFFUSE`, `EN_SUIVI` et
`CLOTUREE` sont déclarés mais seront servis aux lots 7 et 8.

### Droits

La source unique est `apps/missions/acces.py` ; l'API expose `mes_droits` (mission) et
`actions_possibles` (étape), et l'interface n'affiche que les boutons correspondants.

| Action | Qui |
|---|---|
| Voir une mission | RAI : toutes ; AUDITEUR : celles où il est chef, auditeur ou superviseur (hors brouillon) ; AUDITE : celles où il est affecté, une fois l'ordre de mission émis ; **ADMIN et DG : aucune (403)** ; mission non visible : 404 |
| Créer, modifier, planifier, lancer, émettre l'ordre, suspendre, reprendre, annuler, supprimer, affecter, remplacer le chef, arbitrer | RAI |
| Confirmer sa déclaration d'indépendance | l'auditeur concerné |
| Démarrer une étape, gérer réunions, entretiens et risques de mission | RAI ou intervenant dont la déclaration est confirmée ou arbitrée (sinon 403) |
| Terminer une étape (sauf I), « non applicable », rétablir | chef de mission |
| Valider ou renvoyer un jalon ; rouvrir | RAI ; superviseur pour VI, X, XIII (réouverture sauf XVIII) ; jamais l'auteur de la fin d'étape |
| Étapes, fiche de suivi, risques, déclarations | RAI et intervenants ; l'audité y reçoit 403 |

L'audité ne voit que l'en-tête de la mission (champs internes masqués), l'équipe, les réunions
et les entretiens dont il est interlocuteur. « Non applicable » n'est ouvert que pour les
missions de conseil et jamais sur un jalon. Chaque action est tracée dans `/api/v1/audit-log/`.

### Livrables vérifiés au lot 3

| Étape | Condition pour la terminer |
|---|---|
| I | l'ordre de mission est émis (c'est l'émission qui termine l'étape) |
| II | réunion d'ouverture tenue, au moins un entretien planifié, déclarations de l'équipe levées |
| IV | au moins un risque sélectionné pour la mission |
| XI | réunion de lancement tenue |
| III, V à X, XII à XVIII | démarrage et « non applicable » possibles ; la fin est refusée (422) avec « Les livrables de l'étape … sont gérés à partir du lot n » (lots 5, 6 ou 7) |

### Mode « confirmation » et empreinte

L'ordre de mission et les déclarations d'indépendance sont confirmés par l'utilisateur
authentifié (`POST …/issue-order/` avec le corps `{"confirme": true}`, obligatoire). Chaque
confirmation est enregistrée de façon immuable (`signatures.Confirmation`) avec le signataire,
l'horodatage du serveur, le texte exact affiché, les données confirmées, l'adresse IP et une
**empreinte SHA-256** du texte et des données (JSON canonique). `signatures.services.verifier`
recalcule l'empreinte pour détecter toute altération. Aucune ré-authentification n'est exigée au
lot 3 ; la signature électronique avancée relève du lot 7 bis. Après l'émission de l'ordre, les
champs de l'étape I sont gelés ; rouvrir l'étape I impose une nouvelle émission (l'ancienne
confirmation est conservée).

### Parcours e2e

`frontend/e2e/missions.spec.ts` rejoue le parcours complet contre la pile de dev. Il crée des
missions dont le titre commence par « E2E — » et les supprime logiquement par SQL ; ce nettoyage
est refusé sauf si `E2E_ALLOW_DB_CLEANUP=1`. Pour une seconde pile à côté de celle de dev :
`WEB_PORT`, `E2E_API_URL`, `E2E_OIDC_AUTHORITY`, `E2E_DB_CONTAINER` et `POSTGRES_DB`
(le client Keycloak de dev doit autoriser l'URI de redirection du port choisi).


## Accomplissement (lot 6) : programme, fiches, pièces, constats

- **Gel du programme (D5)** : la validation du jalon X par le RAI ou le superviseur fige un
  instantané vérifiable (empreinte) du programme de travail. Tout état figé refuse les
  écritures (API, services, `save()`, QuerySets).
- **Fiches de test (D7)** : documentées par les auditeurs, validées par le RAI ou le
  superviseur, jamais par l'auteur ; le jalon XIII exige la validation de toutes les fiches.
- **Stockage des pièces (D8)** : fichiers écrits sur le disque du serveur, hors dépôt, sous
  `FICHIERS_RACINE` (défaut `var/fichiers`, ignoré par Git), via l'interface
  `StockageFichiers` (`STOCKAGE_PREUVES_BACKEND`, `StockageDisque` par défaut ; S3 possible
  plus tard). En production, `FICHIERS_RACINE=/var/lib/onea/fichiers` est le volume Docker
  nommé `onea-fichiers`, monté sur `web` et `worker`. Aucune exposition par Nginx : seul
  l'endpoint de téléchargement authentifié sert une pièce. Les pièces ne sont jamais
  modifiées ni effacées ; l'empreinte SHA-256 est calculée au dépôt et revérifiée au
  téléchargement.
- **Sauvegarde** : sauvegarder le volume `onea-fichiers` avec la base (même instant) ; une
  base restaurée sans son répertoire de fichiers laisse des pièces introuvables.
- **Intégrité** : `python manage.py verifier_pieces [--mission REF]` recompare chaque pièce à
  son empreinte ; code de sortie 0 sans écart, 1 sinon (pièce absente, altérée ou orpheline).
- **Réponse de l'audité (D11)** : l'audité ne voit que les constats soumis et répond
  accord, ou désaccord motivé (confirmé, horodaté), sans bloquer le flux.
- **Livrables (D12)** et **droits (D13)** : ADMIN et DG n'accèdent à rien ; chaque action
  figure dans la piste d'audit et chaque consultation sensible dans le journal.

## Suivi, relances et recherche (lot 8)

- **Suivi** (`apps.suivi`) : registre des recommandations et des actions, preuves de mise en
  oeuvre, demandes de report d'échéance (décision du RAI), clôture de mission. Le tableau de
  bord du RAI (« File de décisions ») renvoie vers les écrans filtrés
  `/recommandations?vue=actions&statut=VERIFIEE`, `/recommandations/reports?statut=EN_ATTENTE`,
  `/recommandations/relances?statut=ECHEC` et `?statut=SANS_ADRESSE` (RAI seulement ; l'API
  correspondante est `GET /api/v1/reminders/` et `GET /api/v1/follow-up/extension-requests/`, filtre `statut`).
- **Relances** : tâche Celery `suivi.relances_quotidiennes` à 07:00 (`suivi-relances`), paliers
  J-15, J et J+15, une relance par palier. `RELANCES_ACTIVES=false` les suspend ;
  `PLATEFORME_URL` (https en production) fonde les liens des courriels. Exploitation :
  `python manage.py envoyer_relances --simulation [--date AAAA-MM-JJ]` liste ce qui serait envoyé
  sans rien écrire. Une relance « sans adresse » ou « en échec » reste visible au RAI.
- **Recherche** : Meilisearch n'est jamais exposé (ni Nginx ni le frontend) ; seul
  `GET /api/v1/search/` y accède, avec le périmètre de l'utilisateur. `python manage.py
  configurer_recherche` (exécuté par le service `migrate` en production) applique les
  réglages de l'index ; `python manage.py reindexer [--type TYPE]` le reconstruit. La
  réconciliation de l'index (`recherche-reconciliation`, 02:00) rattrape les écarts ; celle du suivi
  (`suivi-reconciliation`) tourne chaque heure.

## Dependencies and container images (reproducible builds)

`backend/uv.lock` is committed (runtime + `dev` group). CI uses `uv sync --frozen`; the
backend image installs `uv export --frozen --no-dev --no-emit-project` with
`pip install --require-hashes`. The `uv` binary is copied from a pinned
`ghcr.io/astral-sh/uv:<version>@sha256:...` image.

Update a dependency:

```
cd backend
uv lock --upgrade-package <name>     # or edit pyproject.toml, then: uv lock
uv lock --check                      # must exit 0 (pre-commit hook does the same)
uv sync --frozen                     # local environment
```

Commit `pyproject.toml` and `uv.lock` together.

Check that an image matches the lock (`pip freeze` inside the image vs the export):

```
docker build -f docker/backend.Dockerfile -t onea-backend:check .
docker run --rm --entrypoint pip onea-backend:check freeze | sort > /tmp/image.txt
uv export --frozen --no-dev --no-emit-project --no-hashes --format requirements-txt \
  | grep -v '^#' | grep -v '^ ' | sed 's/ ;.*//' | sort > /tmp/lock.txt
diff /tmp/image.txt /tmp/lock.txt && echo identical
```

Update a container image: pick the exact tag (never a floating one), then read the digest of
the multi-architecture index and write `tag@sha256:...` in `docker/compose.prod.yml` and the
Dockerfiles (tag only in `compose.yml`, `compose.dev.yml` and the CI services):

```
docker buildx imagetools inspect <image>:<exact-tag>   # first "Digest:" line = index digest
sh scripts/verifier-epinglage.sh                       # must exit 0
```
