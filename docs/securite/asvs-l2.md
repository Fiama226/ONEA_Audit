# Revue de sécurité OWASP ASVS 4.0.3 niveau 2 (lot 9, tâche 27)

Version relue : branche `develop` au commit `d99a03f` (worktree `feat/lot9-t27`), le 01/11/2026.
Les corrections relèvent de la tâche T29 ; ce document ne modifie aucun code.

## 1. Méthode et périmètre

- **Revue statique** : code backend (16 apps Django, environ 48 000 lignes hors tests et
  migrations), frontend (authentification OIDC, puits XSS), `docker/nginx/prod.conf`,
  `docker/compose.prod.yml`, realm de développement et script du realm de recette,
  `docs/deploy.md`, réglages `config/settings/*`.
- **Règle de preuve** : un constat n'est listé que s'il a été confirmé par la lecture du code
  (chemin et ligne cités), par un script ou par une requête sur l'instance jetable.
- **Analyse dynamique**, uniquement sur une **instance jetable** démarrée pour la revue, jamais
  sur la pile de développement ni sur la recette :
  - PostgreSQL `l9t27-db` (base `onea_l9t27`, port 15433), Redis `l9t27-redis` (16380),
    Keycloak 26.8.1 `l9t27-kc` (18181, realm de développement importé) ;
  - API : `runserver` sur le port 8127 (réglages `dev`) avec les données de démonstration
    `peupler_demo --profil formation` ;
  - `l9t27-nginx` : copie de `docker/nginx/prod.conf`, dont **seules** les adresses amont ont
    été remplacées, avec un certificat autosigné (`audit.l9t27.test`, `sso.l9t27.test`) et la
    SPA construite (`vite build`) ;
  - OWASP ZAP (`zaproxy/zap-stable`) lancé par `scripts/recette/zap.sh` : *baseline* sur
    l'application et sur le SSO, *api-scan* actif sur le schéma OpenAPI avec le jeton porteur
    d'un AUDITEUR.
- **Tests manuels ciblés** (script `dyn.py`, instance jetable) : IDOR et matrice de lecture par
  rôle sur les 69 routes `GET` de liste, jeton `alg: none`, contenu de jeton modifié (rôle
  `RAI` injecté), traversée des chemins Keycloak (`/realms/master` encodé, doublé, en majuscules,
  `..`), CORS depuis une origine étrangère, `TRACE`, limitation de débit du SSO, verrouillage
  anti-force-brute de Keycloak.
- **Dépendances** : `pip-audit` sur `uv.lock` (177 paquets, hors outils de développement) et
  `npm audit` sur `package-lock.json`.

## 2. Synthèse des constats

| Id | Gravité | Sujet | Correction |
|---|---|---|---|
| SEC-01 | **Élevé** | Un UUID envoyé comme entier JSON contourne les gardes de création (visibilité, déclaration d'indépendance, rôle) | T29 |
| SEC-02 | Moyen | L'ADMIN lit le contenu de toutes les missions par la piste d'audit (`/api/v1/audit-log/`) | arbitrage utilisateur, puis T29 |
| SEC-03 | Moyen | OTP des comptes à privilèges (D19) et politique de mots de passe non documentés ni appliqués | T29 (documentation + `realm.sh`) |
| SEC-04 | Moyen | Aucune analyse antivirus en production (`ANTIVIRUS_MOTEUR=aucun`, pas de ClamAV livré) ; macros des formats OLE (`doc`, `xls`, `msg`) non inspectées | décision utilisateur (point ouvert), puis T29 |
| SEC-05 | Faible | Hôte SSO : en-têtes HSTS et `nosniff` doublés ; pas de `Permissions-Policy`, de COOP ni de CORP | T29 |
| SEC-06 | Faible | Realm de recette : URI de redirection `/auth/callback` alors que la SPA utilise `/callback` | T29 |
| SEC-07 | Faible | Les confirmations horodatées (D10) reposent sur un SHA-256 sans clé : elles détectent une altération accidentelle, pas une falsification par un accès en écriture à la base | T29 (HMAC) ou acceptation |
| SEC-08 | Faible | Déclarations d'indépendance : `description_conflit` et `arbitrage_justification` lisibles par toute l'équipe de la mission | arbitrage utilisateur |
| SEC-09 | Faible | L'AUDITE lit le compte rendu et les décisions d'une réunion pas encore tenue | T29 |
| SEC-10 | Faible | `npm audit` : 14 vulnérabilités modérées (ReDoS de `minimatch`), toutes dans les outils de développement | T29 (mise à jour) |

Total : **0 critique, 1 élevé, 3 moyens, 6 faibles**. La relecture contradictoire de SEC-01
(étape 4 du plan) est consignée en §5.

## 3. Constats détaillés

### SEC-01 — Élevé — Un UUID envoyé sous forme d'entier JSON contourne les gardes de création

**Mécanisme.** Plusieurs vues de création lisent l'identifiant du parent dans le corps **avant**
le sérialiseur pour répondre 404 ou 403 avant 400 :

- `backend/apps/missions/permissions.py:50-63` (`mission_du_corps`) :
  `identifiant = UUID(str(brut))` puis `except ValueError: return None`, avec le commentaire
  « Champ absent ou illisible : `None`, le sérialiseur répondra 400 ».
- Des fonctions équivalentes (`_uuid(brut)` / `_uuid_du_corps`) existent dans
  `accomplissement/views.py:81-91` et `analyse/views.py:60-64`.

Pour `n = uuid.int`, `UUID(str(n))` lève `ValueError` : la garde renvoie `None` et **ne fait
aucun contrôle**. Le sérialiseur, lui, accepte l'entier. `CleRelation`
(`missions/serializers.py:86-97`) utilise un `serializers.UUIDField()` de DRF, qui convertit un
entier par `uuid.UUID(int=data)`. Il résout ensuite l'objet dans `Mission.objects.all()`, sans
borne de visibilité. Les services (`creer_reunion`, `ajouter_question`, etc.) ne contrôlent que
l'état (gel, statut), jamais le rôle de l'acteur.

**Confirmation dynamique** (instance jetable). `formation.auditeur2` est AUDITEUR de la mission
`DAI/2026/M01`, et sa déclaration d'indépendance n'est pas levée :

| Requête `POST /api/v1/meetings/` | Réponse |
|---|---|
| `"mission": "b24fc79a-…"` (chaîne) | **403** « Confirmez votre déclaration d'indépendance… » |
| `"mission": 237016…` (le même UUID en entier) | **201** : réunion créée (journalisée dans la piste d'audit) |
| mission en BROUILLON, chaîne | 404 |
| mission en BROUILLON, entier | 422 « Les travaux commencent une fois la mission planifiée. » : la garde de visibilité n'a **pas** répondu 404, seule la règle d'état a bloqué |

**Sites concernés** : toute vue de création dont la garde lit un identifiant dans un corps
**JSON**. Les corps multipart (dépôt de pièces `accomplissement/views.py:616-628`, dépôt de
preuves `suivi/views.py:541-556`) ne transportent que des chaînes : ils ne sont pas exposés. Les
paramètres de requête (`?mission=`) non plus, car ils répondent 400 à une valeur illisible.

- `missions/views.py:151-155` (`creer_pour_mission`) : réunions, entretiens, risques de
  mission ; `missions/views.py:426`.
- `analyse/views.py:96` (questionnaires, descriptions, grilles, MARC, forces et faiblesses,
  objectifs), `analyse/views.py:186` (`QuestionViewSet.create`), actions `initialize`
  (`analyse/views.py:382`, `:582`).
- `communication/views.py:280-289` (création de rapport) et `:623-627` (réponse de l'audité au
  rapport provisoire).
- `recommandations/views.py:115-120` (actions, `peut_proposer`), `:207-213` (acceptations),
  `:280-290` (engagements de l'audité).
- `constats/views.py:265-272` (réponse de l'audité à un constat).
- `accomplissement/views.py:292-300` (tests prévus), `:423-434` (fiches de test).
- `suivi/views.py:678-682` (demandes de report).

L'exploitation complète a été démontrée sur `meetings`. Pour les autres sites, la garde est
contournée de la même façon ; l'effet final dépend de ce que revérifient le sérialiseur et le
service. Les tests de T29 doivent couvrir chaque site.

**Scénarios.** (1) Un AUDITEUR dont la déclaration n'est pas levée contribue à la mission. Le
contrôle d'indépendance exigé par les normes IIA est contourné. (2) Un AUDITEUR qui connaît
l'UUID d'une mission où il n'intervient pas écrit dedans au lieu d'obtenir 404 ; les UUID ne se
devinent pas, mais ils circulent (liens, exports, journaux). (3) Un AUDITE répond ou s'engage
sur un objet qui n'est pas le sien. Les rôles ADMIN et DG restent bloqués par
`MissionAccessPermission` (`missions/permissions.py:66-78`).

**Correction proposée (T29).**
1. Une seule fonction partagée (dans `apps/core`) pour lire un identifiant du corps, qui exige
   `isinstance(brut, str)` (sinon 400) ou applique le **même** `UUIDField` que le sérialiseur.
   Elle remplace `mission_du_corps` et les `_uuid` locaux.
2. Mieux : contrôler visibilité et contribution **après** validation, sur
   `serializer.validated_data[...]` (`perform_create` ou `validate_<champ>`), pour qu'aucun écart
   d'analyse ne soit possible entre la garde et le sérialiseur.
3. Défense en profondeur : un `CleRelation` qui refuse les entiers, et des querysets de FK bornés
   aux objets visibles.
4. Tests : le cas `int(uuid)` dans chaque matrice de droits (`backend/tests/*/test_api_permissions.py`,
   `backend/tests/test_matrice_droits_lot{6,7,8}.py`).

### SEC-02 — Moyen — L'ADMIN lit le contenu de toutes les missions par la piste d'audit

- `backend/apps/core/views.py:80-90` : `AuditLogViewSet` avec
  `permission_classes = [IsRAIOrAdmin]`, et un queryset non filtré
  (`LogEntry.objects.select_related(...)`) ; le sérialiseur (`core/serializers.py:47-72`)
  renvoie `changes` avec les valeurs avant et après de chaque champ.
- Or `missions/acces.py:79-96` donne **aucune** mission à l'ADMIN (`Mission.objects.none()`), et
  la matrice des lots refuse l'ADMIN sur les données de mission (test
  `backend/tests/missions/test_api_permissions.py::test_matrice_droits_missions`).
- **Confirmé** : avec le jeton de l'ADMIN, `GET /api/v1/audit-log/?page_size=200` renvoie
  683 entrées, dont le texte intégral des rapports d'orientation, objectifs, lignes MARC, forces
  et faiblesses, risques de mission, avis de l'audité et réponses aux questionnaires.
- La spécification (`docs/superpowers/specs/2026-10-27-plateforme-audit-interne-design.md:151`)
  prévoit « Piste d'audit consultable par l'ADMIN et le RAI : qui, quand, quoi, avant/après ».
  Les deux règles se contredisent : **arbitrage de l'utilisateur requis**.
- **Scénario** : l'administrateur de la plateforme (DSI), hors du Département Audit Interne, lit
  les constats et les preuves décrites d'une mission qui vise sa propre direction.
- **Correction proposée** : pour l'ADMIN, restreindre la piste d'audit aux objets de plateforme
  (`users.*`, `documents.gabaritdocument`, `documents.formatnumerotation`,
  `signatures.parametresignature`, référentiel), ou masquer `changes` et `object_repr` des objets
  de mission. Sinon, acceptation écrite de l'utilisateur.

### SEC-03 — Moyen — OTP des comptes à privilèges (D19) et politique de mots de passe non appliqués

- D19 (plan du lot 9) : « OTP Keycloak obligatoire pour les comptes `ADMIN` et pour les
  administrateurs du realm `master` ». Or `docs/deploy.md` §5 (l.331-420) ne décrit **aucune**
  étape OTP : ni action requise *Configure OTP*, ni flux conditionnel par rôle.
- `docs/deploy.md:407` demande une longueur minimale de 12, mais `scripts/recette/realm.sh:20-24`
  ne pose ni `passwordPolicy` ni OTP. La recette ne vérifie donc pas la configuration cible ; la
  politique ne prévoit pas non plus de contrôle des mots de passe compromis (ASVS 2.1.7).
- **Scénario** : le mot de passe d'un ADMIN est hameçonné. Un seul facteur suffit pour ouvrir
  l'administration des comptes (désactivation, import CSV de comptes RAI provisoires) et la
  piste d'audit (SEC-02).
- **Correction proposée** : dans `deploy.md` §5, une étape « OTP » (flux *browser* avec une
  condition sur le rôle `ADMIN`, ou action requise `CONFIGURE_TOTP` pour les comptes ADMIN et les
  administrateurs `master`), une politique `length(12) and notUsername and passwordHistory(5)`
  et, si l'ONEA l'accepte, une liste de mots de passe interdits. Les mêmes réglages dans
  `realm.sh`, et un test `scripts/recette/tests/` qui lit le realm.

### SEC-04 — Moyen — Pas d'analyse antivirus des fichiers téléversés en production

- `backend/config/settings/base.py:208` : `ANTIVIRUS_MOTEUR` vaut `aucun` par défaut, et
  `prod.py` ne l'exige pas. `docker/compose.prod.yml` ne livre pas de service ClamAV, et
  `docs/stockage-fichiers.md:78-85` le décrit comme un « point d'extension ». Point déjà ouvert
  côté utilisateur (`docs/HANDOFF.md:43`).
- `backend/apps/core/fichiers.py:68-70` accepte `doc`, `xls` et `msg` (OLE) sans inspecter leurs
  macros ; seuls les formats OOXML sont contrôlés (`vbaProject`). Le document
  `docs/stockage-fichiers.md:76` le reconnaît : « l'antivirus est le recours ».
- **Scénario** : un audité dépose comme preuve un `.xls` à macro malveillante. L'auditeur le
  télécharge (`Content-Disposition: attachment`) et l'ouvre dans Office.
- **Correction proposée** : livrer `clamav/clamav` (GPL-2.0, service séparé : **licence à faire
  valider par l'utilisateur** au regard de la règle 2) dans `compose.prod.yml`, sur le réseau
  interne, et exiger `ANTIVIRUS_MOTEUR=clamd` dans `prod.py`. À défaut, refuser `doc`, `xls` et
  `msg` à macros (flux `Macros` / `_VBA_PROJECT` d'OLE) ou les retirer de la liste blanche, et
  consigner l'acceptation du risque.

### SEC-05 — Faible — En-têtes de sécurité de l'hôte SSO

- `docker/nginx/prod.conf:174-175` ajoute HSTS et `nosniff`, que Keycloak émet déjà. ZAP signale
  « Strict-Transport-Security Multiple Header Entries ». L'hôte n'a ni `Permissions-Policy`, ni
  `Cross-Origin-Opener-Policy`, ni `Cross-Origin-Resource-Policy`. Le CSP de Keycloak est
  minimal (`frame-src 'self'; frame-ancestors 'self'; object-src 'none'`) et absent sur
  certaines ressources.
- **Correction proposée** : `proxy_hide_header Strict-Transport-Security;` et
  `proxy_hide_header X-Content-Type-Options;` dans ce bloc, ajout de `Permissions-Policy`, et
  réglage des *Security defenses* du realm (CSP, `X-Frame-Options`) documenté dans `deploy.md`.

### SEC-06 — Faible — URI de redirection du realm de recette

- `scripts/recette/realm.sh:50` déclare `https://$PUBLIC_HOST/auth/callback`, alors que la SPA
  redirige vers `${origin}/callback` (`frontend/src/auth/oidc.ts:35`, route
  `frontend/src/routes.tsx:63`) et que `docs/deploy.md` §5 indique `/callback`. La connexion par
  navigateur en recette est refusée par Keycloak, ce qui pousse à élargir les URI (joker).
- **Correction proposée** : `https://$PUBLIC_HOST/callback` dans `realm.sh`, et un test de
  recette qui compare les `redirectUris` du realm à la route de la SPA.

### SEC-07 — Faible — Les confirmations horodatées ne sont pas scellées par une clé

- `backend/apps/signatures/services.py:43-52` : `empreinte = sha256(texte canonique + données)`,
  stockée dans la même base ; `verifier` (l.80-85) la recalcule. Quiconque peut écrire dans la
  base peut modifier une confirmation et recalculer l'empreinte. Les déclencheurs SQL
  d'immuabilité (`apps/core/gardes_sql.py`) réduisent ce risque sans le supprimer (un
  propriétaire de la base peut les désactiver).
- **Correction proposée** : HMAC-SHA-256 avec une clé lue dans un fichier de secret distinct de
  la base (nouveau secret, rotation documentée). Ou acceptation : D10 est une confirmation, pas
  une signature électronique qualifiée.

### SEC-08 — Faible — Conflits d'intérêts lisibles par toute l'équipe

- `backend/apps/missions/views.py:463-474` (`DeclarationViewSet`, borné à `missions_visibles`) et
  `missions/serializers.py:498-507` (`description_conflit`, `arbitrage_justification`). Confirmé
  par requête : `formation.auditeur1` lit les 3 déclarations de `DAI/2026/M01`, celles de ses
  collègues comprises.
- **Correction proposée** (si ce n'est pas voulu) : masquer ces deux champs, sauf pour le RAI, le
  chef de mission et la personne qui déclare.

### SEC-09 — Faible — L'AUDITE lit le compte rendu d'une réunion pas encore tenue

- `backend/apps/missions/views.py:681-687` (`ReunionViewSet`, `audite_actions = LECTURE`) et
  `missions/serializers.py:666-700` : `compte_rendu` et `decisions` sont renvoyés sans masquage,
  même si `tenue_le` est vide. À comparer avec `EntretienSerializer.to_representation`
  (l.750-756), qui masque les notes internes pour l'AUDITE.
- **Correction proposée** : pour l'AUDITE, ne renvoyer `compte_rendu` et `decisions` qu'une fois
  `tenue_le` posé.

### SEC-10 — Faible — Dépendances de développement vulnérables

- `npm audit` : 14 alertes modérées, toutes issues de GHSA-g3hv-75wg-m249 (`minimatch < 11.0.1`,
  ReDoS), via `eslint`, `typescript-eslint`, `eslint-plugin-jsx-a11y` et `openapi-typescript`.
  `npm audit --omit=dev` donne 0. `pip-audit` (backend, `uv.lock`) : aucune vulnérabilité connue.
- **Correction proposée** : mettre à jour ces outils (ou forcer `minimatch` par `overrides`) ;
  sans effet sur le produit livré.

### Faux positifs écartés (avec preuve)

- **ZAP « SQL Injection » (40018), 321 alertes** : les réponses comparées sont des 400 (filtre
  invalide) ou des 429 (limiteur `onea_api` de nginx), pas un effet SQL. Les seuls SQL bruts
  sont paramétrés (`constats/managers.py:41-45`, `core/gardes_sql.py:493-545`,
  `missions/services/missions.py:212`, `referentiel/services.py:99`). Il n'y a ni `raw()`, ni
  `extra()`, ni `RawSQL`.
- **ZAP « Server Error » (100000), 361 alertes** : des 502 « no live upstreams » (journal du
  nginx jetable) et 7 réponses 500 dues à l'épuisement des ports TCP de Windows
  (`OperationalError … Address already in use`) sous la charge du scan sur `runserver`. Ce sont
  des artefacts du banc, pas de l'application.
- **ZAP « Unexpected Content-Type » (100001)** : 404 Django en `text/html` sur des chemins qui
  ne correspondent pas au motif UUID (`/id/`). Pas de fuite (`DEBUG=False` en production,
  `backend/tests/test_prod_settings.py`).
- **Jetons forgés** : `alg: none` → 401 ; contenu modifié (rôle `RAI`) avec la signature
  d'origine → 401 ; `x.y.z` → 401. Le jeton est validé par Keycloak (`userinfo`) et le rôle vient
  uniquement des claims de `userinfo` (`apps/users/oidc.py:82-137`).
- **Lecture de `azp` sans vérifier la signature** (`apps/users/authentication.py:34-46`) : la
  valeur sert seulement à refuser un client ; le jeton est ensuite validé par Keycloak, et un
  `azp` modifié invalide la signature (401 confirmé ci-dessus).
- **Contournement du realm `master`** : `/realms/%6daster/`, `/realms//master/`,
  `/realms/MASTER/`, `/realms/onea/../master/`, `..%2f` → 404 ; `;x` → 400.
- **Injection de gabarit (SSTI) docxtpl** : `ImmutableSandboxedEnvironment` sans globals, avec
  les filtres dangereux retirés et les opérateurs bornés (`documents/moteur/bac_a_sable.py:30-124`),
  plus une analyse statique des balises (`moteur/balises.py`). Tests :
  `backend/tests/documents/test_moteur_securite.py`. ZAP 90035/90036 : PASS.
- **Injection de formules CSV/XLSX** : `neutraliser_formule` (`referentiel/exports.py:50-68`,
  déclencheurs `= + - @ \t \r`) et `data_type = "s"` en XLSX, dans les 4 modules d'export
  (`programmation`, `referentiel`, `suivi`, `tableaux_de_bord`). Tests `test_exports.py` de chaque
  app.
- **Recherche** : double filtre, celui de Meilisearch par audience (`recherche/visibilite.py:21-43`,
  valeurs échappées) puis une revérification en base de chaque résultat
  (`recherche/services.py:84-121`).
- **Import CSV des comptes** : un CSV ne crée jamais d'ADMIN ni de compte `is_staff`
  (`users/provisioning.py:319-392`) ; le rôle CSV reste provisoire et est réécrit depuis
  Keycloak à la première connexion (`users/oidc.py:248-277`).

## 4. Tableau ASVS 4.0.3, niveau 2 (sous-ensemble applicable)

Statuts : **C** conforme, **NC** non conforme, **SO** sans objet. « Banc » = vérifié sur
l'instance jetable de la revue.

### V1 — Architecture

| Exigence | Statut | Preuve | Action |
|---|---|---|---|
| 1.2.1 Comptes de service à moindre privilège | C | `onea-admin-sync` limité à `view-users` et `manage-users` (`deploy.md` §5 7bis, `realm.sh:62-75`) ; conteneurs `cap_drop: ALL`, `no-new-privileges` (`compose.prod.yml:34-35`), `USER onea` (`backend.Dockerfile:51`) | — |
| 1.2.2 Communications authentifiées entre composants | C | Redis protégé par mot de passe, Meilisearch par clé maîtresse exigée (`prod.py:67-68`), réseaux `internal` (`deploy.md` §1) ; `scripts/recette/tests/reseaux.sh` | — |
| 1.4.1 Contrôle d'accès appliqué côté serveur | C, sauf SEC-01 | `DEFAULT_PERMISSION_CLASSES = IsAuthenticated` (`base.py:249`), permissions par app | SEC-01 |
| 1.4.4 Un mécanisme unique de contrôle d'accès | NC | gardes avant sérialiseur dupliquées dans 7 apps (`_uuid`, `mission_du_corps`) | SEC-01 (fonction partagée) |
| 1.5.1 Exigences de sérialisation et de validation définies | C | sérialiseurs explicites, `CleRelation` (`missions/serializers.py:86`) | — |
| 1.6.1 Politique de gestion des clés | C | secrets dans des fichiers `*_FILE` (`base.py:24-39`), `docs/deploy.md` §3 (rotation) ; `backend/tests/test_settings_secrets.py` | — |
| 1.8.1 Données sensibles identifiées | C | `docs/stockage-fichiers.md`, `no-store` sur l'API | — |
| 1.12.2 Fichiers téléversés servis hors du domaine ou en pièce jointe | C | pas de `MEDIA_URL` (`base.py:166-167`) ; téléchargements par l'API en `attachment` (`documents/views.py:97-107`, `accomplissement/views.py:699-704`) | — |
| 1.14.6 Pas de technologie client obsolète | C | SPA React 19, aucun plugin | — |

### V2 — Authentification (déléguée à Keycloak)

| Exigence | Statut | Preuve | Action |
|---|---|---|---|
| 2.1.1 Mots de passe d'au moins 12 caractères | NC (recette) / C (doc) | `deploy.md:407` ; absent de `realm.sh:20-24` | SEC-03 |
| 2.1.7 Contrôle des mots de passe compromis | NC | aucune liste de mots interdits | SEC-03 |
| 2.2.1 Protection contre la force brute | C | `bruteForceProtected` (`realm.sh:22`, `deploy.md:404-406`) ; nginx `onea_sso_auth` 5 r/s, rafale 20 (`prod.conf:34,196-199`). Banc : 40 tentatives simultanées → 26 × 400, 14 × 429, puis le bon mot de passe est refusé (compte verrouillé temporairement) | — |
| 2.2.3 Notification de changement d'identifiant | SO | délégué à Keycloak et à l'annuaire | — |
| 2.3.1 Mots de passe initiaux aléatoires | C | `realm.sh:84-88` (`openssl rand`) ; aucun compte de test en production (`deploy.md:333-336`) | — |
| 2.5.x Récupération du compte | C | `resetPasswordAllowed=false` (realm de développement) ; récupération par l'annuaire | — |
| 2.7/2.8 Second facteur (OTP, D19) pour les comptes à privilèges | NC | aucune étape OTP dans `deploy.md` §5 ni dans `realm.sh` | SEC-03 |
| 2.10.1 Pas de secret statique entre services | C | secrets clients dans des fichiers ; refus des valeurs de modèle et de développement (`prod.py:46-87`) ; `backend/tests/test_prod_settings.py` | — |
| 2.10.4 Secrets absents du code | C | `scripts/generer-secrets.sh`, `backend/tests/test_secrets_ops.py` ; `realm-onea.json` réservé au développement (`deploy.md:333-336`) | — |

### V3 — Sessions et jetons

| Exigence | Statut | Preuve | Action |
|---|---|---|---|
| 3.1.1 Pas de jeton dans l'URL | C | jeton porteur en en-tête (`frontend/src/api/client.ts`) ; journal nginx sans chaîne de requête (`prod.conf:24-29`) | — |
| 3.2.3 Stockage du jeton côté client | C | `sessionStorage`, pas `localStorage` (`frontend/src/auth/oidc.ts:40-42`) | — |
| 3.3.1 Déconnexion qui invalide la session | C | `POST /api/v1/session/fin/` purge le cache `userinfo`, puis déconnexion Keycloak (`users/views.py:32`, `users/oidc.py:69-73`) ; `backend/tests/users/test_userinfo_cache.py` | — |
| 3.3.2 Délai d'inactivité | C | sessions Keycloak, `SESSION_COOKIE_AGE = 8 h` pour l'admin Django (`base.py:457`) | — |
| 3.3.4 Révocation effective | C (avec délai) | cache `userinfo` ≤ 60 s, borné par `exp` (`users/oidc.py:61-66`, décision D5) ; désactivation locale immédiate (`authentication.py:93-94`) | — |
| 3.4.1-3.4.5 Attributs des cookies | C | `__Host-`, `Secure`, `HttpOnly`, `SameSite=Lax` (`prod.py:107-112`) ; `backend/tests/test_security_defaults.py` | — |
| 3.5.2 Jetons signés et validés | C | validation par `userinfo` de Keycloak ; banc : `alg: none` et contenu modifié → 401 | — |
| 3.5.3 Jetons d'un autre client refusés | C | `OIDC_ALLOWED_AZP` (`authentication.py:61-68`, `base.py:440`) ; `backend/tests/users/test_auth_api.py`, `test_oidc.py` | — |
| 3.7.1 Réauthentification pour les opérations sensibles | SO | confirmations D10 par case à cocher explicite ; pas de signature qualifiée | SEC-07 (information) |

### V4 — Contrôle d'accès

| Exigence | Statut | Preuve | Action |
|---|---|---|---|
| 4.1.1 Contrôle côté serveur de confiance | C | permissions DRF et services | — |
| 4.1.2 Attributs de droits non modifiables par l'utilisateur | C | rôle uniquement depuis les claims `userinfo` (`users/oidc.py:132-137`) ; `direction` et `fonction` modifiables par l'administrateur seulement (`deploy.md` §5.4) ; `ProfilUtilisateurSerializer` refuse tout champ inattendu (`users/account_serializers.py:133-149`) | — |
| 4.1.3 Moindre privilège | NC | SEC-02 (l'ADMIN lit tout par la piste d'audit), SEC-08 | SEC-02, SEC-08 |
| 4.1.5 Échec sûr | C | `Mission.objects.none()` par défaut (`missions/acces.py:96`) ; 404 sur une mission invisible | — |
| 4.2.1 IDOR (lecture et modification d'objets existants) | C | querysets bornés à `missions_visibles` et `*_lisibles` ; banc : matrice des 69 routes de liste pour l'AUDITE, le DG, l'ADMIN et l'AUDITEUR, sans fuite hors périmètre (hors SEC-02) ; `backend/tests/test_matrice_droits_lot6.py`, `lot7`, `lot8`, `backend/tests/*/test_api_permissions.py` | — |
| 4.2.1 IDOR (création, FK du corps) | NC | SEC-01, confirmé sur le banc (201 au lieu de 403) | SEC-01 |
| 4.2.2 CSRF | SO | API en jeton porteur seulement (D4) ; admin Django : `CsrfViewMiddleware` (`base.py:111`) | — |
| 4.3.1 Interfaces d'administration protégées | C | `/admin/` désactivé en production par défaut (`prod.py:94`, `backend/tests/test_admin_toggle.py`) ; console Keycloak derrière `ADMIN_ALLOW_CIDR` (banc : 404) | SEC-03 (OTP) |
| 4.3.2 Pas de listage de répertoires ni de métadonnées | C | `/metrics` → 404 sans jeton (`core/views.py:55-66`, `backend/tests/test_metriques.py`) ; schéma OpenAPI réservé à `IsAdminUser` en production (`base.py:283`) | — |
| 4.3.3 Machines à états et fenêtres d'écriture | C | `missions/services/etapes.py:91-183`, gardes de gel ; `backend/tests/analyse/test_fenetre_ecriture.py`, `backend/tests/programmation/test_gel.py` | — |

### V5 — Validation, assainissement, encodage

| Exigence | Statut | Preuve | Action |
|---|---|---|---|
| 5.1.2 Affectation de masse | C | `Meta.fields` explicites, statuts et auteurs en lecture seule ; `retirer_immuables` (`missions/views.py:137-149`) | — |
| 5.1.3 Validation positive des entrées | NC (partiel) | les UUID acceptent la forme entière (SEC-01) | SEC-01 |
| 5.1.4 Données structurées typées | C | `ChoiceField`, bornes, caractères de contrôle refusés (`referentiel/serializers.py:212-219`) | — |
| 5.2.2 Assainissement du texte libre | C | gabarits Django avec échappement automatique, aucun `mark_safe` ni `|safe` (recherche dans `backend/apps`) | — |
| 5.2.5 Injection de gabarit | C | bac à sable Jinja immuable (`documents/moteur/bac_a_sable.py:84-124`) ; `backend/tests/documents/test_moteur_securite.py` ; ZAP 90035 PASS | — |
| 5.2.6 SSRF | C | aucune URL fournie par l'utilisateur ; URL de Keycloak, Gotenberg et Meilisearch fixées par la configuration | — |
| 5.2.7 SVG et contenu scriptable | C | SVG absent de la liste blanche (`core/fichiers.py:52-74`) | — |
| 5.3.1 Encodage de sortie | C | JSON seul en production (`prod.py:88-91`) ; React échappe par défaut, aucun `dangerouslySetInnerHTML` (recherche dans `frontend/src`) | — |
| 5.3.4 Requêtes paramétrées | C | voir les faux positifs du §3 | — |
| 5.3.x Injection de formules CSV/XLSX | C | `neutraliser_formule` et `data_type = "s"` ; tests `test_exports.py` de 4 apps | — |
| 5.5.x Désérialisation | C | Celery en JSON seulement (`base.py:369-371`) | — |

### V7 — Erreurs et journalisation (T13)

| Exigence | Statut | Preuve | Action |
|---|---|---|---|
| 7.1.1 Pas de secret ni de jeton dans les journaux | C | filtre `MasquageFiltre` (`base.py:486`), clé de cache = SHA-256 du jeton (`users/oidc.py:43-45`) ; `backend/tests/core/test_journalisation.py` ; `scripts/recette/tests/journaux.sh` | — |
| 7.1.2 Pas de donnée personnelle inutile | C | `accesslog = None` dans gunicorn (`gunicorn_conf.py:3`) ; nginx sans chaîne de requête | — |
| 7.1.3 Événements de sécurité journalisés | C | refus de jeton journalisé (`authentication.py:67,81-90`) ; consultation des pièces (`journaliser_consultation`) ; piste d'audit `auditlog` avec acteur (`backend/tests/core/test_audit_actor_bearer.py`) | — |
| 7.1.4 Corrélation des événements | C | `X-Correlation-ID = $request_id` (`prod.conf:119`), `CorrelationMiddleware` | — |
| 7.3.1 Journaux protégés contre l'injection | C | JSON (`FormateurJson`), `escape=json` dans nginx | — |
| 7.3.3 Piste d'audit inaltérable | C | déclencheurs SQL (`core/gardes_sql.py`, `backend/tests/core/test_gardes_sql.py`) ; API en lecture seule (`core/views.py:80`) | SEC-02 (portée de lecture) |
| 7.4.1 Message d'erreur générique | C | `api_exception_handler`, format `{detail, errors}` ; `backend/tests/core/test_exception_handler.py`, `backend/tests/core/test_audit_log_api_robustness.py` | — |

### V8 — Protection des données

| Exigence | Statut | Preuve | Action |
|---|---|---|---|
| 8.1.1 Pas de cache des données sensibles | C | `PasDeCacheApiMiddleware` (`core/middleware.py:202-216`) ; banc : `Cache-Control: no-store, private` sur `/api/v1/me/` ; téléchargements `private, no-store` (`documents/views.py:105`) | — |
| 8.2.2 Pas de donnée sensible dans le stockage du navigateur | C | `sessionStorage` (jeton seul) ; `localStorage` ne sert qu'à l'état de la barre latérale (`frontend/src/layouts/useSidebarCollapsed.ts`) | — |
| 8.3.1 Données sensibles hors de l'URL | C | identifiants seulement dans l'URL ; recherche `q` exclue des journaux nginx | — |
| 8.3.4 Données sensibles identifiées et protégées | NC (partiel) | SEC-02, SEC-08, SEC-09 | voir constats |
| 8.3.x Intégrité des preuves | C | écriture unique et SHA-256 vérifié à la lecture (`ouvrir_piece_verifiee`) ; `backend/tests/accomplissement/test_integrite.py`, `backend/tests/documents/test_integrite.py` | SEC-07 (confirmations) |

### V9 — Communications (T19)

| Exigence | Statut | Preuve | Action |
|---|---|---|---|
| 9.1.1 TLS pour toutes les connexions client | C | redirection 80 → 443 vers un hôte fixe (`prod.conf:58-81`) ; HSTS 1 an | — |
| 9.1.2 Suites de chiffrement fortes | C | TLS 1.2 et 1.3, liste Mozilla *intermediate*, sans tickets (`prod.conf:50-56`) ; `scripts/recette/tests/tls.sh` | — |
| 9.2.1 TLS vers Keycloak | C | `OIDC_OP_BASE_URL` en `https://` exigé et `OIDC_VERIFY_SSL` obligatoire (`prod.py:39-45`) ; `backend/tests/test_prod_settings.py` | — |
| 9.2.x Relais SMTP | C | `smtps://` ou STARTTLS (`prod.py:33-37`), mot de passe dans un fichier | — |

### V10 — Code malveillant (T14)

| Exigence | Statut | Preuve | Action |
|---|---|---|---|
| 10.3.2 Intégrité des dépendances | C | `uv.lock` et `package-lock.json` versionnés ; `scripts/verifier-epinglage.sh` (images épinglées) | — |
| 10.3.x Dépendances sans vulnérabilité connue | C (produit) / NC (outils de développement) | `pip-audit` : 0 ; `npm audit --omit=dev` : 0 ; outils de développement : 14 modérées | SEC-10 |
| 10.2.x Pas de fonction cachée ni de porte dérobée | C | client `onea-dev-cli` réservé à `dev.py:6` ; `onea-charge` réservé à la recette (D20) | — |

### V12 — Fichiers et ressources (T15)

| Exigence | Statut | Preuve | Action |
|---|---|---|---|
| 12.1.1 Taille maximale | C | 50 Mo (`base.py:201`), nginx 55 Mo sur `/api/` et 1 Mo ailleurs (`prod.conf:46,110`) ; contrôle avant lecture (`accomplissement/views.py:640`) | — |
| 12.1.2 Bombes de décompression | C | ≤ 2 000 entrées, ≤ 200 Mo, ratio ≤ 20 au-delà de 16 Mo, sans décompresser (`core/fichiers.py:184-215`) ; `backend/tests/core/test_fichiers.py` | — |
| 12.1.3 Quota par utilisateur ou par espace | C | `DOCUMENTS_QUOTA_MO`, débit `televersement` de 30/h (`base.py:174,265`) | — |
| 12.2.1 Type réel contrôlé (signature d'octets) | C | `controler_entete` (`core/fichiers.py:138-170`) ; `backend/tests/accomplissement/test_api_securite_fichiers.py` | — |
| 12.3.1 Nom du client jamais dans un chemin | C | `core/fichiers.py:13` (le nom ne sert qu'à l'extension), stockage adressé par identifiant | — |
| 12.3.2 Traversée de chemin | C | `_nom_suspect` sur les archives (`core/fichiers.py:180-181`) ; `nom_telechargement` retire les séparateurs et les caractères de contrôle (`documents/views.py:88-94`) | — |
| 12.4.1 Stockage hors de la racine web | C | `valider_documents_root` (`prod.py:57`) ; pas de `MEDIA_URL` | — |
| 12.4.2 Analyse antivirus | NC | `ANTIVIRUS_MOTEUR=aucun` en production | SEC-04 |
| 12.5.1 Pas de service de fichiers par extension | C | nginx ne sert que `/static/` (collectstatic) | — |
| 12.5.2 `Content-Disposition` et `nosniff` sur les téléchargements | C | `as_attachment=True`, `nosniff` (`documents/views.py:97-107`), nginx `nosniff` partout | — |
| 12.6.1 SSRF par fichier (liens externes OOXML) | C | `verifier_sortie` refuse champs et liens externes (`documents/moteur/controle_ooxml.py`) ; `backend/tests/documents/test_securite.py` | — |

### V13 — API

| Exigence | Statut | Preuve | Action |
|---|---|---|---|
| 13.1.1 Même encodage et même parseur partout | NC (partiel) | la garde et le sérialiseur analysent l'UUID différemment | SEC-01 |
| 13.1.3 Pas de secret dans l'URL | C | jeton en en-tête | — |
| 13.1.4 Décisions d'accès dans l'API | C | voir V4 | — |
| 13.2.1 Méthodes HTTP limitées | C | `http_method_names` sans PUT (par exemple `signatures/views.py:60`) ; banc : `TRACE` → 405 | — |
| 13.2.3 CSRF de l'API | SO | jeton porteur (D4) | — |
| 13.2.5 Content-Type vérifié | C | `MultiPartParser` explicite pour les fichiers ; JSON seul en production | — |
| 13.2.6 Limitation de débit | C | nginx `/api/` 50 r/s, rafale 100 (`prod.conf:33,111`) ; DRF par utilisateur (`base.py:258-271`), `backend/tests/core/test_throttling.py` ; banc : 429 observés | — |
| 13.x CORS | C | production : `CORS_ALLOWED_ORIGINS` vide par défaut (`prod.py:22`) ; banc : aucun `Access-Control-Allow-Origin` pour une origine étrangère | — |

### V14 — Configuration (T1, T9, T17, en-têtes)

| Exigence | Statut | Preuve | Action |
|---|---|---|---|
| 14.1.x Construction reproductible | C | images épinglées (`scripts/verifier-epinglage.sh`), `uv sync --frozen` | — |
| 14.2.1 Dépendances à jour | C (produit) | voir V10 | SEC-10 |
| 14.3.2 Mode débogage désactivé | C | `DEBUG = False` (`prod.py:17`) ; `backend/tests/test_prod_settings.py` | — |
| 14.3.3 Pas de bannière de version | C | `server_tokens off` (`prod.conf:45`) ; banc : `Server: nginx` | — |
| 14.4.1 `Content-Type` et jeu de caractères | C | JSON `application/json`, téléchargements typés | — |
| 14.4.3 CSP | C (application) / NC (SSO, faible) | application : `default-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'none'` (banc) ; `style-src 'unsafe-inline'` accepté (styles inline de Radix) ; SSO : CSP de Keycloak minimal | SEC-05 |
| 14.4.4 `X-Content-Type-Options: nosniff` | C | banc, sur toutes les réponses | — |
| 14.4.5 HSTS | C (application) / NC (SSO, doublon) | `max-age=31536000; includeSubDomains` | SEC-05 |
| 14.4.6 `Referrer-Policy` | C | `strict-origin-when-cross-origin` (banc) | — |
| 14.4.7 Protection contre l'encadrement | C | `X-Frame-Options: DENY` et `frame-ancestors 'none'` (banc) | — |
| 14.5.1 Méthodes HTTP | C | `TRACE` → 405 (banc) | — |
| 14.5.2 En-têtes de proxy non falsifiables | C | `X-Forwarded-*` imposés par nginx (`prod.conf:106-119`) ; `TRUSTED_PROXY_CIDRS` (`base.py:120`) ; `backend/tests/core/test_adresse_client.py` ; `scripts/recette/tests/edge.sh` | — |
| 14.5.3 CORS : liste d'origines stricte | C | voir V13 | — |

## 5. Relecture contradictoire des constats élevés (étape 4)

Le seul constat élevé, SEC-01, a été soumis à un second relecteur indépendant, avec le code et
sans la conclusion. Son verdict est consigné ci-dessous.

_(à compléter)_

## 6. Analyse dynamique : rapports

- Script : `scripts/recette/zap.sh` (baseline application et SSO, api-scan sur OpenAPI avec le
  jeton d'un compte de recette ; `ZAP_ACTIF=1` ajoute l'analyse active, sur une instance jetable
  seulement). Les rapports (HTML, JSON, Markdown) vont dans `.recette/zap/`. Ce sont des
  artefacts : ils ne sont pas versionnés, car ils peuvent contenir des en-têtes de requête.
- Exécution de la revue (instance jetable, analyse active) : `FAIL-NEW: 0`, `WARN-NEW: 4`,
  `PASS: 118`. Les 4 avertissements sont traités au §3 (faux positifs) et dans SEC-05 (CSP
  `style-src 'unsafe-inline'` accepté). Baseline de l'application : informatif seulement (COEP
  absent, commentaires dans le JavaScript minifié, directives de cache). Baseline du SSO :
  SEC-05.

## 7. Constats ouverts pour T29

SEC-01 (obligatoire avant la mise en production), SEC-03, SEC-05, SEC-06, SEC-09, SEC-10.
Décision de l'utilisateur requise : SEC-02 (portée de la piste d'audit pour l'ADMIN), SEC-04
(ClamAV, licence GPL-2.0 d'un service séparé, ou refus des formats OLE), SEC-07 (HMAC ou
acceptation), SEC-08 (visibilité des conflits d'intérêts).
