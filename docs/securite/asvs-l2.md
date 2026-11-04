# Revue de sécurité OWASP ASVS 4.0.3 niveau 2

## Journal des modifications

| Date | Version relue | Objet |
|---|---|---|
| 2026-11-04 | branche `feat/auth-interne`, commit `ccd12f8` | **Rejeu sur l'authentification interne** (Keycloak retiré) : chapitres V2, V3, V4 et V7 rejoués exigence par exigence ; lignes touchées de V1, V5, V8, V9, V10, V13 et V14 mises à jour ; constats AUTH-01 à AUTH-20 de la revue statique de l'authentification et état de leurs corrections (§2.2) ; SEC-03, SEC-05 et SEC-06 rendus sans objet. Revue **statique** : aucune pile lancée pour ce rejeu (voir §1.1). |
| 2026-11-01 | branche `develop`, commit `d99a03f` (lot 9, tâche 27) | Revue initiale, authentification déléguée à Keycloak, avec banc dynamique jetable. Ses conclusions propres à Keycloak sont résumées au §0 et ne s'appliquent plus. |

## 0. Historique : la revue du 2026-11-01 portait sur Keycloak

La revue initiale (lot 9, T27) a été conduite quand l'authentification était déléguée à Keycloak
(jeton porteur OIDC, `userinfo`, realm `onea`, client `onea-admin-sync`). Ses constats propres au
fournisseur d'identité (SEC-03 : OTP et politique de mots de passe du realm ; SEC-05 : en-têtes de
l'hôte SSO ; SEC-06 : URI de redirection du realm de recette) et ses vérifications de jetons
(`alg: none`, contenu modifié, `azp`, traversée du realm `master`) **n'ont plus d'objet** depuis le
remplacement de Keycloak par l'authentification interne (conception :
`docs/superpowers/specs/2026-11-03-authentification-interne-design.md`, modèle de sécurité :
`docs/securite/auth-interne-modele.md`). Ils restent consultables dans l'historique Git de ce
fichier (version du commit `d99a03f`). Les autres constats (SEC-01, SEC-02, SEC-04, SEC-07 à
SEC-10) ne dépendent pas de l'authentification et sont repris tels quels.

## 1. Méthode et périmètre

### 1.1 Rejeu du 2026-11-04 (authentification interne)

- **Périmètre** : `backend/apps/users/` (connexion, codes à usage unique, mots de passe
  temporaires, délégation, envoi des courriels par le `worker`), `backend/apps/core/middleware.py`,
  `apps/core/reseau.py`, `apps/core/journalisation.py`, `config/settings/{base,prod}.py`,
  `config/urls.py`, `docker/compose.prod.yml`, `docker/nginx/prod.conf`, `.env.prod.example`, et
  les écrans d'authentification du frontend (`frontend/src/auth/`) pour les exigences côté client.
- **Sources** : la revue statique de l'authentification du 2026-11-04 (constats AUTH-01 à AUTH-20,
  document de travail hors dépôt, résumé au §2.2), le compte rendu des corrections (commits
  `39163e0`, `f77d1ff`, `f713854`, `91222a0`, `ccd12f8`), puis **relecture du code** pour chaque
  ligne de ce document.
- **Règle de preuve** : « Conforme » seulement si le code (fichier et ligne) **et**, quand il
  existe, un test nommé le montrent. Les chemins de code sont relatifs à `backend/apps/` (code),
  `backend/config/` (réglages) et `backend/tests/` (tests), sauf mention contraire.
- **Ce qui n'a pas été fait pour ce rejeu** : aucune pile lancée, aucun banc dynamique, aucun ZAP,
  aucune requête réelle. Les tests cités n'ont **pas** été relancés par l'auteur de ce rejeu ; le
  compte rendu des corrections indique 614 tests passés sur une sélection (`tests/users` complet et
  fichiers ciblés de `tests/core` et de `tests/`), sans suite complète unique. Le comportement réel
  (envoi par le `worker` jusqu'au relais SMTP, réponses 429 derrière le NAT, en-têtes, cookies dans
  un navigateur) **n'est pas vérifié sur une pile en fonctionnement**.

### 1.2 Revue initiale du 2026-11-01 (conservée pour les chapitres non rejoués)

- **Revue statique** : code backend (16 apps Django, environ 48 000 lignes hors tests et
  migrations), frontend (puits XSS), `docker/nginx/prod.conf`, `docker/compose.prod.yml`,
  `docs/deploy.md`, réglages `config/settings/*`.
- **Analyse dynamique**, uniquement sur une **instance jetable** (PostgreSQL, Redis, API en
  `runserver` avec `peupler_demo --profil formation`, copie de `docker/nginx/prod.conf` avec un
  certificat autosigné et la SPA construite) ; OWASP ZAP (`scripts/recette/zap.sh`) en *baseline*
  et en *api-scan* actif.
- **Tests manuels ciblés** (script `dyn.py`, instance jetable) : IDOR et matrice de lecture par
  rôle sur les 69 routes `GET` de liste, CORS depuis une origine étrangère, `TRACE`.
- **Dépendances** : `pip-audit` sur `uv.lock` (177 paquets, hors outils de développement) et
  `npm audit` sur `package-lock.json`.

## 2. Synthèse des constats

### 2.1 Constats de la revue initiale (SEC-xx)

| Id | Gravité | Sujet | Correction | Statut |
|---|---|---|---|---|
| SEC-01 | **Élevé** | Un UUID envoyé comme entier JSON contourne les gardes de création (visibilité, déclaration d'indépendance, rôle) | T29 | **Corrigé** (T29) : `apps/core/identifiants.py`, `tests/missions/test_sec01_uuid_entier.py` |
| SEC-02 | Moyen | L'ADMIN lit le contenu de toutes les missions par la piste d'audit (`/api/v1/audit-log/`) | arbitrage utilisateur, puis T29 | **Résolu (paramétrable)** : réglage `journal_audit_contenu_missions` (« complet » par défaut, « masqué »), modifiable par l'ADMIN et audité |
| SEC-03 | Moyen | OTP des comptes à privilèges (D19) et politique de mots de passe du realm Keycloak | T29 | **Sans objet depuis le 2026-11-04** (Keycloak retiré). La politique de mots de passe est maintenant dans l'application (V2.1) ; l'OTP obligatoire pour les comptes à privilèges reste **non décidé** (D19, voir 4.3.1) |
| SEC-04 | Moyen | Aucune analyse antivirus en production (`ANTIVIRUS_MOTEUR=aucun`, pas de ClamAV livré) ; macros des formats OLE (`doc`, `xls`, `msg`) non inspectées | décision utilisateur (point ouvert), puis T29 | **Résolu** (`feat/lot9-sec04`) : ClamAV en conteneur séparé, échec fermé ; risque résiduel : macros OLE (`doc`, `xls`, `msg`) |
| SEC-05 | Faible | Hôte SSO : en-têtes HSTS et `nosniff` doublés ; pas de `Permissions-Policy`, de COOP ni de CORP | T29 | **Sans objet depuis le 2026-11-04** : plus d'hôte SSO dans `docker/nginx/prod.conf` |
| SEC-06 | Faible | Realm de recette : URI de redirection `/auth/callback` alors que la SPA utilise `/callback` | T29 | **Sans objet depuis le 2026-11-04** : plus de realm |
| SEC-07 | Faible | Les confirmations horodatées (D10) reposent sur un SHA-256 sans clé : elles détectent une altération accidentelle, pas une falsification par un accès en écriture à la base | T29 (HMAC) ou acceptation | **Risque accepté** par l'utilisateur le 2026-11-02 : le SHA-256 sans clé détecte une altération accidentelle, pas une falsification par un accès en écriture à la base ; atténué par le rôle applicatif sans DELETE/TRUNCATE et les gardes SQL (lot 9 T10) |
| SEC-08 | Faible | Déclarations d'indépendance : `description_conflit` et `arbitrage_justification` lisibles par toute l'équipe de la mission | arbitrage utilisateur | **Corrigé** (T29) : masquage hors RAI, chef de mission et déclarant ; `tests/missions/test_sec08_sec09.py` |
| SEC-09 | Faible | L'AUDITE lit le compte rendu et les décisions d'une réunion pas encore tenue | T29 | **Corrigé** (T29) : `ReunionSerializer.to_representation` |
| SEC-10 | Faible | `npm audit` : 14 vulnérabilités modérées (ReDoS de `minimatch`), toutes dans les outils de développement | T29 (mise à jour) | Ouvert : `overrides` vers `minimatch` 11 incompatible avec `eslint` ; hors produit livré |

Total de la revue initiale : 0 critique, 1 élevé, 3 moyens, 6 faibles ; à ce jour, aucun constat
critique, élevé ou moyen n'est ouvert (SEC-03 sans objet).

### 2.2 Constats de la revue de l'authentification interne (AUTH-xx, 2026-11-04)

Revue statique ligne à ligne de la branche `feat/auth-interne` (commit `e673734`), référentiel
ASVS 4.0.3 L2 (V2, V3, V4, V7, V13, V14). Corrections : commits `39163e0` à `ccd12f8`.
« Corrigé » signifie : code modifié et tests ajoutés, **relus** ; le comportement sur une pile
réelle n'est pas vérifié (§1.1).

| Id | Gravité | Sujet | Statut | Preuve de la correction |
|---|---|---|---|---|
| AUTH-01 | Élevé | En production, `web` envoyait lui-même les courriels d'authentification alors qu'il n'a aucune route SMTP : code de connexion jamais reçu, mots de passe temporaires toujours affichés | **Corrigé** (`f77d1ff`) : tous les courriels d'authentification partent du `worker` ; aucun secret dans le broker (le code est émis par la tâche ; le mot de passe temporaire est chiffré Fernet dans `EnvoiMotDePasse`, 1 h, lu une fois) | `users/envois.py:50-122`, `users/tasks.py:70-104`, `users/auth_views.py:127-135` ; `tests/users/test_envois_courriels.py` (14 tests), `tests/test_deploiement_lot8.py::test_courriels_d_authentification_ont_un_chemin_vers_le_relais_smtp`, `::test_le_code_web_n_envoie_aucun_courriel_d_authentification_lui_meme` |
| AUTH-02 | Élevé | Aucun plafond global des essais de codes de réinitialisation (nouveau code = 5 essais neufs) | **Corrigé** (`f713854`) : codes faux comptés par compte en base sur 24 h, plafond `AUTH_REINITIALISATION_ECHECS_MAX` (15 par défaut) ; au plafond, code supprimé, plus aucun code émis ni accepté jusqu'à la fin de la fenêtre ; quota d'émission (10 codes / 24 h) déplacé du cache vers la base (échec fermé) | `users/auth_services.py:296-355,436-451`, `users/tasks.py:53-62`, `users/models.py:61-67`, `config/settings/base.py:321` ; `tests/users/test_auth_reinitialisation_plafond.py` (9 tests) |
| AUTH-03 | Élevé | Un délégué pouvait prendre la main sur les comptes RAI et DG, ou en créer | **Corrigé** (`39163e0`) : RAI et DG protégés pour un acteur non ADMIN ; seuls les ADMIN attribuent ADMIN, RAI ou DG | `users/delegation.py:61,82-99,150-153` ; `tests/users/test_delegation.py::test_delegate_cannot_touch_rai_or_dg_account`, `::test_delegate_cannot_create_or_assign_reserved_roles`, `::test_delegate_still_manages_auditeurs_and_audites` |
| AUTH-04 | Moyen | Une seule adresse pouvait garder une soixantaine de comptes verrouillés | **Corrigé** (`91222a0`) : plafond d'échecs par adresse, tous comptes confondus (`echecs_connexion`, 30 par 15 min ; `echecs_reinitialisation`, 30 par heure), vérifié avant tout hachage | `users/auth_throttles.py:164-220`, `users/auth_views.py:102,119,143,166,260,282` ; `tests/users/test_auth_limites.py::test_one_address_cannot_lock_many_accounts` |
| AUTH-05 | Moyen | Quota de connexion partagé derrière le NAT et consommé avant le contrôle CSRF | **Corrigé** (`91222a0`) : CSRF vérifié avant les limites ; un compteur par point d'entrée ; connexion portée à 60/min par adresse ; changement de mot de passe limité par utilisateur | `users/auth_views.py:87-97`, `users/auth_throttles.py:107-133`, `config/settings/base.py:298-312` ; `tests/users/test_auth_limites.py::test_csrf_checked_before_the_throttle_on_every_anonymous_endpoint`, `::test_each_endpoint_has_its_own_bucket` |
| AUTH-06 | Moyen (si `/admin/` activé) | `/admin/login/` sans limite applicative | **Corrigé** (`91222a0`) : mêmes limites que la connexion de l'API, avant tout hachage | `users/admin_login.py:23-39`, `users/auth_throttles.py:223-227` ; `tests/users/test_auth_limites.py::test_admin_login_form_goes_through_the_address_limits` |
| AUTH-07 | Faible | La production acceptait un backend courriel console, fichier ou mémoire | **Corrigé** (`ccd12f8`) : seuls SMTP et `dummymail://` (mode « sans courriel ») sont acceptés au démarrage | `config/settings/prod.py:23-41` ; `tests/test_prod_settings.py::test_prod_refuse_un_backend_qui_ecrit_les_courriels_hors_smtp`, `::test_prod_accepte_dummymail_pour_fonctionner_sans_courriel` |
| AUTH-08 | Faible | Le délai d'inactivité de 30 min était contourné par le rafraîchissement automatique des notifications | **Corrigé côté serveur** (`ccd12f8`) : une requête portant `X-Onea-Arriere-Plan: 1` ne compte pas comme activité. **Effectif seulement quand le frontend envoie l'en-tête** (modification en cours, non commitée au moment de ce rejeu) | `core/middleware.py:25,83-84` ; `tests/users/test_auth_durcissements.py::test_background_polling_does_not_keep_the_session_alive` |
| AUTH-09 | Faible (si `/admin/` activé) | Session admin sans délai d'inactivité ; `/admin/password_change/` sans comptage des échecs | **Partiel** (`ccd12f8`) : `/admin/password_change/` répond 404 ; **délai d'inactivité des sessions admin non appliqué** (arbitrage : admin désactivé par défaut en production, sessions bornées à 8 h) | `config/urls.py:47-58` ; `tests/users/test_auth_durcissements.py::test_admin_password_change_page_is_closed` |
| AUTH-10 | Faible | Aucune notification au titulaire des événements sensibles (réinitialisation, changement de courriel, désactivation du code) | **Non corrigé (arbitrage)** : modèles de courriels, destinataires (ancienne adresse) et 6 points d'appel à décider ; la voie d'envoi par le `worker` (`envois`, `tasks`) servira de base | — |
| AUTH-11 | Faible | Identifiants sosies (Unicode) ; unicité insensible à la casse non garantie par la base | **Partiel** (`ccd12f8`) : identifiants ASCII imposés à la création et à l'import ; **contraintes d'unicité en base non posées** (une migration échouerait sur une base contenant déjà des doublons de casse ; contrôle `iexact` dans les services ; la course restante ne permet qu'un déni de service) | `users/account_serializers.py:139-140`, `users/provisioning.py:89-90` ; `tests/users/test_auth_durcissements.py::test_new_usernames_are_ascii_only` |
| AUTH-12 | Faible | Limites par adresse comptées par IPv6 /128 | **Corrigé** (`91222a0`) : clé par /64 en IPv6 | `users/auth_throttles.py:68-79` ; `tests/users/test_auth_limites.py::test_ipv6_counts_by_its_64`, `::test_ipv6_neighbours_share_one_bucket` |
| AUTH-13 | Faible | Liste de mots de passe interdits limitée à celle de Django | **Non corrigé (arbitrage)** : corpus hors ligne de mots de passe compromis à choisir (taille, licence, mise à jour) | — |
| AUTH-14 | Info | Petits écarts de temps entre compte inconnu, verrouillé et actif | Non corrigé | — |
| AUTH-15 | Info | Pas de liste ni de fermeture des autres sessions par l'utilisateur | Non corrigé | — |
| AUTH-16 | Info | La réinitialisation révèle qu'un code est juste quand le nouveau mot de passe est refusé | Non corrigé | — |
| AUTH-17 | Info | Clé Fernet du fichier d'import sans clé de secours ; `GET` destructeur | Non corrigé | — |
| AUTH-18 | Info | TLS non exigé vers le relais SMTP (`smtp://` accepté) | Non corrigé | `config/settings/prod.py:31-35` |
| AUTH-19 | Info | Codes hachés en Argon2 à chaque vérification (coût) | Non corrigé | — |
| AUTH-20 | Info | Code de connexion devinable à raison de 5 essais par 15 min une fois le mot de passe connu | Atténué : les codes de connexion faux comptent aussi dans le plafond par adresse | `tests/users/test_auth_limites.py::test_wrong_login_codes_count_too` |

Bilan : 3 élevés et 3 moyens corrigés ; faibles : AUTH-07 et AUTH-12 corrigés, AUTH-08 corrigé
côté serveur (frontend à terminer), AUTH-09 et AUTH-11 partiels, AUTH-10 et AUTH-13 non faits
(arbitrage) ; aucun constat d'information traité (AUTH-20 atténué).

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

> **Résolu (paramétrable).** Décision utilisateur : lecture complète conservée par défaut, mais réglable. Réglage `journal_audit_contenu_missions` (`core.ParametrePlateforme`) : « COMPLET » (défaut) ou « MASQUE ». En mode masqué, l'ADMIN voit qui, quand, l'action et l'entité ; les valeurs avant/après et `object_repr` des entités de mission sont remplacés par « [masqué] » (comptes, référentiel et réglages restent lisibles) ; le RAI n'est pas concerné. Écriture ADMIN seule, changement audité. Tests : `backend/tests/core/test_audit_log_settings.py`.

- `backend/apps/core/views.py:80-90` : `AuditLogViewSet` avec
  `permission_classes = [IsRAIOrAdmin]`, et un queryset non filtré
  (`LogEntry.objects.select_related(...)`) ; le sérialiseur (`core/serializers.py:47-72`)
  renvoie `changes` avec les valeurs avant et après de chaque champ.
- Or `missions/acces.py:79-96` donne **aucune** mission à l'ADMIN (`Mission.objects.none()`), et
  la matrice des lots refuse l'ADMIN sur les données de mission (test
  `backend/tests/missions/test_api_permissions.py::test_matrice_droits_missions`).
- **Confirmé** : avec la session de l'ADMIN, `GET /api/v1/audit-log/?page_size=200` renvoie
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

### SEC-03 — Sans objet depuis le 2026-11-04 (Keycloak retiré)

Le constat portait sur la configuration du realm Keycloak (OTP des comptes à privilèges,
politique de mots de passe du realm, contrôle des mots de passe compromis). Dans l'authentification
interne : la politique de mots de passe est appliquée par l'application (V2.1, 12 caractères) ;
le contrôle des mots de passe compromis reste partiel (AUTH-13, 2.1.7) ; le code de connexion
par courriel existe mais reste **facultatif pour tous les rôles** : l'obligation pour les comptes
à privilèges (ancienne décision D19) attend une décision de l'ONEA (4.3.1).

### SEC-04 — Moyen — Pas d'analyse antivirus des fichiers téléversés en production (RÉSOLU)

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

- **Résolution** : service `clamav` (image officielle, conteneur séparé, licence GPL-2.0 validée
  par l'utilisateur, `docs/securite/licences.md`) dans `docker/compose.prod.yml` : réseau interne
  `av` (web et worker seuls), sortie `av-out` réservée à freshclam, volume de signatures, plafond
  mémoire, `no-new-privileges`, bilan de santé. `ANTIVIRUS_MOTEUR=clamav` par défaut en
  production, `aucun` refusé par `prod.py` sans `ANTIVIRUS_AUTORISER_AUCUN=true`, échec fermé
  (`ANTIVIRUS_ECHEC_FERME`), limite 50 Mo alignée sur nginx, analyse de toutes les voies de dépôt
  (gabarits, preuves, pièces, import CSV). Tests : `backend/tests/core/test_antivirus.py`
  (faux clamd INSTREAM : sain, FOUND, injoignable, trop gros), `backend/tests/test_prod_settings.py`.
  Procédures : `docs/exploitation/runbook.md` §11.
- **Risque résiduel documenté** : les macros des formats OLE (`doc`, `xls`, `msg`) ne sont pas
  inspectées par l'application. L'analyse de ClamAV (documents OLE2/VBA) en couvre une partie,
  pas les macros inédites ou obfusquées. Atténuations : téléchargement forcé (`attachment`),
  consigne aux auditeurs de ne pas activer les macros, préférence pour les formats OOXML
  contrôlés. Non vérifié sans Docker : démarrage réel de l'image et EICAR de bout en bout
  (runbook §11).

### SEC-05 et SEC-06 — Sans objet depuis le 2026-11-04 (Keycloak retiré)

SEC-05 visait les en-têtes de l'hôte SSO et SEC-06 l'URI de redirection du realm de recette. Il
n'y a plus ni hôte SSO dans `docker/nginx/prod.conf` (un seul `server_name ${PUBLIC_HOST}`), ni
realm, ni redirection OIDC.

### SEC-07 — Faible — Les confirmations horodatées ne sont pas scellées par une clé

> Mise à jour 2026-11-03 : la signature PAdES du rapport final (lot 7 bis, `docs/exploitation/signature-electronique.md`) apporte un scellement par clé du PDF diffusé lorsque le certificat de l'ONEA est configuré. Les confirmations D10 elles-mêmes restent en SHA-256 sans clé (risque accepté inchangé).

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
  (`users/provisioning.py`) ; depuis AUTH-03, un import n'est ouvert qu'aux ADMIN et les
  identifiants sont ASCII (AUTH-11). Le rôle du CSV est le rôle du compte (il n'est plus réécrit
  par un fournisseur d'identité).
- Les vérifications de jetons OIDC de la revue initiale (`alg: none`, contenu modifié, `azp`,
  realm `master`) sont sans objet (§0) : l'API n'accepte plus de jeton porteur
  (`tests/users/test_auth_api.py::test_bearer_header_is_ignored`).

## 4. Tableau ASVS 4.0.3, niveau 2

Statuts :
- **chapitres rejoués le 2026-11-04** (V2, V3, V4, V7, et les lignes marquées « rejoué » de V8,
  V9, V13 et V14) : **Conforme**, **Partiel**, **Non conforme**, **Non applicable** ;
- **chapitres repris de la revue du 2026-11-01** (V1, V5, V10, V12) : **C** conforme, **NC** non
  conforme, **SO** sans objet ; « Banc » = vérifié sur l'instance jetable de cette revue-là. Dans
  V8, V9, V13 et V14, les lignes marquées « repris » gardent la conclusion du 01/11, traduite dans
  le vocabulaire ci-dessus (C → Conforme, « NC partiel » → Partiel). Les lignes reprises n'ont pas
  été rejouées.

### V1 — Architecture (repris du 2026-11-01, sauf 1.2.1)

| Exigence | Statut | Preuve | Action |
|---|---|---|---|
| 1.2.1 Comptes de service à moindre privilège | C | conteneurs `cap_drop: ALL`, `no-new-privileges` (`compose.prod.yml:31-35`), `USER onea` (`backend.Dockerfile:51`) ; rôle PostgreSQL applicatif sans DELETE/TRUNCATE (`deploy.md` §7bis) ; seul `worker` reçoit le secret `email_password` et la route SMTP (`compose.prod.yml:155-182`). Rejoué le 2026-11-04 : le compte de service Keycloak `onea-admin-sync` n'existe plus | — |
| 1.2.2 Communications authentifiées entre composants | C | Redis protégé par mot de passe, Meilisearch par clé maîtresse exigée (`prod.py:73-74`), réseaux `internal` (`deploy.md`, tableau des réseaux) ; `scripts/recette/tests/reseaux.sh` | — |
| 1.4.1 Contrôle d'accès appliqué côté serveur | C, sauf SEC-01 | `DEFAULT_PERMISSION_CLASSES = IsAuthenticated` (`base.py:278`), permissions par app | SEC-01 (corrigé depuis) |
| 1.4.4 Un mécanisme unique de contrôle d'accès | NC | gardes avant sérialiseur dupliquées dans 7 apps (`_uuid`, `mission_du_corps`) | SEC-01 (fonction partagée, corrigé depuis) |
| 1.5.1 Exigences de sérialisation et de validation définies | C | sérialiseurs explicites, `CleRelation` (`missions/serializers.py:86`) | — |
| 1.6.1 Politique de gestion des clés | C | secrets dans des fichiers `*_FILE` (`base.py:24-39`), `docs/deploy.md` §3 (rotation) ; `backend/tests/test_settings_secrets.py` | — |
| 1.8.1 Données sensibles identifiées | C | `docs/stockage-fichiers.md`, `no-store` sur l'API | — |
| 1.12.2 Fichiers téléversés servis hors du domaine ou en pièce jointe | C | pas de `MEDIA_URL` (`base.py:166-167`) ; téléchargements par l'API en `attachment` (`documents/views.py:97-107`, `accomplissement/views.py:699-704`) | — |
| 1.14.6 Pas de technologie client obsolète | C | SPA React 19, aucun plugin | — |

### V2 — Authentification (rejoué le 2026-11-04, authentification interne)

| Exigence | Statut | Preuve | Notes |
|---|---|---|---|
| 2.1.1 Mots de passe d'au moins 12 caractères | Conforme | `MinimumLengthValidator` `min_length: 12` (`config/settings/base.py:156-164`), appliqué au changement, à la réinitialisation par code (`users/auth_services.py:423,446,504`) ; `tests/users/test_auth_models.py::test_min_length_12_rejected` | Les mots de passe temporaires générés font 16 caractères |
| 2.1.2 Au moins 64 caractères permis, plus de 128 refusés | Partiel | `MOT_DE_PASSE_MAX = 256` (`users/auth_serializers.py:8`), `maxLength` identique côté client (`frontend/src/auth/LoginPage.tsx:161`, `NewPasswordFields.tsx:31`) | 64 permis ; la borne est 256, pas 128 (choix contre le déni de service Argon2 : la longueur reste bornée) |
| 2.1.3 Pas de troncature | Conforme | `trim_whitespace=False` (`users/auth_serializers.py:14,35`) ; une valeur trop longue est refusée (400), jamais tronquée ; Argon2 hache toute la valeur | — |
| 2.1.4 Tout caractère Unicode imprimable permis | Conforme | aucun validateur de jeu de caractères (`base.py:156-164`) | — |
| 2.1.5 L'utilisateur peut changer son mot de passe | Conforme | `ChangementMotDePasseView` (`users/auth_views.py:287-320`) ; `tests/users/test_auth_password.py::test_change_requires_old_password` | — |
| 2.1.6 Changement : mot de passe actuel et nouveau exigés | Conforme | `changer_mot_de_passe` (`users/auth_services.py:493-515`), échec compté dans le verrouillage (`_reconfirmer`, `:473-490`) ; `test_auth_password.py::test_change_wrong_old_password_five_times_locks_the_account` | — |
| 2.1.7 Contrôle des mots de passe compromis | Partiel | `CommonPasswordValidator` (liste Django d'environ 20 000 mots de passe courants, `base.py:162`), au changement et à la réinitialisation, pas à la connexion | AUTH-13 non corrigé (arbitrage : corpus hors ligne à choisir) |
| 2.1.8 Indicateur de robustesse | Non conforme | aucun indicateur dans `frontend/src/auth/NewPasswordFields.tsx` (seule la règle est affichée) | Évolution d'interface |
| 2.1.9 Pas de règle de composition | Conforme | validateurs : longueur, similarité, mots courants, numérique seul (`base.py:156-164`) ; aucune exigence de majuscule ou de symbole | `NumericPasswordValidator` refuse un mot de passe uniquement numérique |
| 2.1.10 Pas de rotation périodique imposée | Conforme | aucune expiration des mots de passe choisis ; seul le mot de passe **temporaire** expire (72 h, `users/services.py:313-326`) | — |
| 2.1.11 Coller et gestionnaires de mots de passe permis | Conforme | champs `type="password"` avec `autoComplete` `current-password` / `new-password`, aucun blocage du collage (`frontend/src/auth/LoginPage.tsx:159-161`, `NewPasswordFields.tsx:29-43`) | — |
| 2.1.12 Afficher le mot de passe saisi | Non conforme | aucun bouton « afficher » dans `LoginPage.tsx` ni `NewPasswordFields.tsx` | Évolution d'interface |
| 2.2.1 Anti-automatisation (force brute, essais d'identifiants, verrouillage) | Partiel | verrouillage 5 échecs / 15 min sous verrou de ligne (`users/auth_services.py:128-189`) ; compteurs par point d'entrée et par adresse, IPv6 par /64, CSRF avant comptage (`users/auth_throttles.py:68-133`, `auth_views.py:87-97`) ; plafond d'échecs par adresse tous comptes confondus (`auth_throttles.py:164-220`) ; plafond de 15 codes de réinitialisation faux par compte et 24 h, en base (`auth_services.py:325-355`) ; admin sous les mêmes limites (`users/admin_login.py:23-39`) ; tests `tests/users/test_auth_limites.py` (22 cas), `test_auth_reinitialisation_plafond.py`, `test_auth_login.py::test_lock_after_5_failures_for_15_minutes` | Restes : un botnet réparti verrouille encore des comptes ciblés (verrouillage par compte) et devine les codes à 6 chiffres au rythme du plafond par compte (15 par jour) ; derrière un NAT, le plafond d'échecs (30 / 15 min) est partagé par tout le site ; les limites par adresse sont en cache et laissent passer si le cache tombe (les limites par compte, en base, restent). Non vérifié sur une pile réelle |
| 2.2.2 Authentificateurs faibles (courriel) limités à la vérification secondaire | Partiel | le code par courriel est le seul second facteur proposé (facultatif, `auth_services.py:531-541`) ; le code « mot de passe oublié » par courriel remplace le mot de passe pour la récupération (`auth_services.py:409-459`) | Pas de facteur plus fort (TOTP, WebAuthn) ; risque connu, voir 2.3.2 |
| 2.2.3 Notification sécurisée après changement des moyens d'authentification | Non conforme | aucun courriel au titulaire après réinitialisation, changement de courriel ou désactivation du code (`users/services.py:207-251,410-471`) | AUTH-10 non corrigé (arbitrage) |
| 2.3.1 Mots de passe initiaux aléatoires, expirant vite, non durables | Conforme | 16 caractères tirés par `secrets.choice` (`users/auth_services.py:229,281-282`), 72 h, changement imposé (`users/services.py:313-326`, `core/middleware.py:89-110`) ; `tests/users/test_auth_otp.py::test_temporary_password_is_long_and_random`, `test_auth_login.py::test_temp_password_expired_blocks_login`, `::test_must_change_password_only_allows_change_endpoint` | — |
| 2.3.2 Appareils d'authentification fournis par l'utilisateur (FIDO, U2F) | Non conforme | aucun WebAuthn ni TOTP | Évolution prévue par la conception (« WebAuthn : évolution possible ») |
| 2.3.3 Instructions de renouvellement des authentificateurs à durée limitée | Non applicable | aucun authentificateur à renouveler (le mot de passe temporaire se remplace à la première connexion) | — |
| 2.4.1 Stockage par fonction de hachage de mots de passe | Conforme | Argon2id en premier (`config/settings/base.py:151-154`) ; `tests/users/test_auth_models.py::test_password_hash_is_argon2` | PBKDF2 gardé seulement pour relire d'anciennes empreintes |
| 2.4.2 Sel d'au moins 32 bits | Conforme | sel aléatoire de Django (`Argon2PasswordHasher`, sel de 128 bits environ) | Valeur par défaut de Django 5.2 |
| 2.4.3 PBKDF2 : au moins 100 000 itérations | Conforme | PBKDF2 de Django 5.2 (1 000 000 itérations), uniquement en relecture | — |
| 2.4.4 bcrypt : facteur de travail ≥ 10 | Non applicable | bcrypt non utilisé | — |
| 2.4.5 Itération supplémentaire avec un sel secret (« poivre ») | Non conforme | aucun poivre : l'empreinte ne dépend que du mot de passe et du sel | Une fuite de la base seule permet l'attaque hors ligne (coût Argon2) |
| 2.5.1 Secret initial ou de récupération jamais envoyé en clair | Non conforme | le courriel de bienvenue et celui de réinitialisation par un administrateur portent le mot de passe temporaire en clair (`users/courriels.py:34-60`) ; `smtp://` en clair accepté vers le relais (`config/settings/prod.py:28-35`, AUTH-18) | Choix de conception (pas de lien d'activation). Atténuations : 72 h, changement imposé, envoi seulement si mis en file, aucun secret dans le broker (AUTH-01) |
| 2.5.2 Pas d'indice ni de question secrète | Conforme | aucune (conception) | — |
| 2.5.3 La récupération ne révèle pas le mot de passe actuel | Conforme | le code mène à un **nouveau** mot de passe (`users/auth_services.py:409-459`) ; empreintes non réversibles | — |
| 2.5.4 Pas de compte partagé ou par défaut | Conforme | aucun compte créé par défaut ; `creer_administrateur` nominatif ; `creer_comptes_e2e` refusé hors `DEBUG`, hors base jetable et hors hôte local (`tests/users/test_creer_comptes_e2e.py::test_refuse_hors_debug`, `::test_refuse_une_base_qui_n_est_pas_jetable`) | — |
| 2.5.5 Notification quand un facteur est changé | Non conforme | voir 2.2.3 | AUTH-10 |
| 2.5.6 Récupération par un mécanisme sûr | Partiel | code à 6 chiffres par courriel : haché, 10 min, 5 essais, usage unique, 10 codes / 24 h et 15 codes faux / 24 h par compte, en base (`users/auth_services.py:233-355`, `users/tasks.py:30-67`) ; réponse uniforme (`auth_views.py:225-255`) ; `tests/users/test_auth_password.py::test_forgot_identical_for_unknown_disabled_and_active`, `::test_reset_uniform_failure_whatever_the_reason`, `test_auth_reinitialisation_plafond.py::test_distributed_guessing_across_fresh_codes_is_capped` | Le courriel n'est pas un canal hors ligne au sens de l'ASVS ; codes à 6 chiffres (passage à 8 : décision produit) |
| 2.5.7 Facteur perdu : vérification d'identité au même niveau qu'à l'enrôlement | Partiel | la désactivation du code par un administrateur ou un délégué est tracée (`users/services.py:449-471`) ; la vérification d'identité est une **procédure** (`docs/exploitation/runbook.md` §5, « vérifier l'identité de la personne »), non imposée par le code | — |
| 2.6.1 Secrets de consultation à usage unique | Non applicable | pas de codes de secours | — |
| 2.6.2 Secrets de consultation suffisamment aléatoires | Non applicable | idem | — |
| 2.6.3 Secrets de consultation résistants aux attaques hors ligne | Non applicable | idem | — |
| 2.7.1 Pas de SMS ou de téléphone par défaut | Non applicable | aucun SMS ni appel ; le code par courriel est facultatif, désactivé par défaut (`users/models.py:60`) | Voir 2.2.2 |
| 2.7.2 Code hors bande expirant en 10 minutes | Conforme | `OTP_VALIDITE = 10 min` (`users/auth_services.py:29,249`) ; étape de connexion en attente bornée à 10 min (`auth_views.py:154-161`) ; `tests/users/test_auth_otp.py::test_expired_after_10_minutes` | — |
| 2.7.3 Usage unique, pour la seule demande d'origine | Conforme | usage unique sous verrou (`auth_services.py:254-273`), un seul code actif par compte et par objet (`users/models.py:117-124`), objets RESET et LOGIN séparés, code de connexion lié à la session en attente (`auth_views.py:154-164`) ; `test_auth_otp.py::test_code_valid_once`, `::test_wrong_code_counts_attempt_and_objet_is_isolated`, `::test_new_code_invalidates_old` | — |
| 2.7.4 Canal hors bande sûr et indépendant | Partiel | courriel émis par le `worker` seul (`users/tasks.py:70-92`) ; transport STARTTLS ou TLS implicite possible (`config/settings/prod.py:42-45`), mais `smtp://` en clair accepté | AUTH-18 non corrigé |
| 2.7.5 Seule l'empreinte du code est conservée | Conforme | `code_hash = make_password(code)` (`users/auth_services.py:248`) ; `tests/users/test_auth_otp.py::test_code_is_six_digits_and_stored_hashed` | — |
| 2.7.6 Code initial tiré d'un générateur sûr, ≥ 20 bits (6 chiffres suffisent) | Conforme | `secrets.choice` sur 6 chiffres (`users/auth_services.py:239`) | — |
| 2.8.1 OTP à durée de vie définie (TOTP) | Non applicable | pas de générateur TOTP (les codes sont hors bande, voir 2.7) | — |
| 2.8.2 Clés symétriques des OTP protégées | Non applicable | idem | — |
| 2.8.3 Algorithmes approuvés pour les OTP | Non applicable | idem | — |
| 2.8.4 TOTP utilisable une seule fois dans sa période | Non applicable | idem | — |
| 2.8.5 Réutilisation d'un TOTP journalisée et notifiée | Non applicable | idem | — |
| 2.8.6 Générateur physique révocable | Non applicable | idem | — |
| 2.9.1 Clés des vérificateurs cryptographiques protégées | Non applicable | pas de vérificateur cryptographique (WebAuthn, certificat client) | — |
| 2.9.2 Nonce de défi d'au moins 64 bits | Non applicable | idem | — |
| 2.9.3 Algorithmes approuvés | Non applicable | idem | — |
| 2.10.1 Secrets entre services non fondés sur des identifiants immuables | Partiel | mots de passe de base, Redis, SMTP et clé Meilisearch dans des fichiers de secrets (`docker/compose.prod.yml` `secrets:`), rotation documentée (`docs/deploy.md` §3.3) | Ce sont des mots de passe statiques, renouvelés à la main |
| 2.10.2 Pas d'identifiant par défaut pour les comptes de service | Conforme | `scripts/generer-secrets.sh` ; refus des valeurs de modèle et de développement (`config/settings/prod.py:77-92`) ; `tests/test_prod_settings.py`, `tests/test_secrets_ops.py` | — |
| 2.10.3 Mots de passe de service protégés contre la récupération hors ligne, y compris en accès local | Partiel | fichiers `0600` dans un dossier `0700` (`docs/deploy.md` §3.1), montés sous `/run/secrets` | Lisibles par root sur l'hôte et par le conteneur qui les reçoit ; pas de coffre |
| 2.10.4 Secrets hors du code et du dépôt | Conforme | `.gitleaks.toml`, `tests/test_secrets_ops.py` ; aucun mot de passe par défaut dans les commandes d'amorçage | — |

### V3 — Sessions (rejoué le 2026-11-04)

| Exigence | Statut | Preuve | Notes |
|---|---|---|---|
| 3.1.1 Pas de jeton de session dans l'URL | Conforme | session dans un cookie seulement (`config/settings/base.py:484-490`) ; un en-tête `Authorization: Bearer` n'authentifie rien (`tests/users/test_auth_api.py::test_bearer_header_is_ignored`) ; journal nginx sans chaîne de requête | — |
| 3.2.1 Nouveau jeton à l'authentification | Conforme | `login()` change la clé (`users/auth_views.py:76-84`) ; l'étape « code » vide la session et en crée une nouvelle (`:124`) ; `update_session_auth_hash` au changement de mot de passe (`:318`) ; `tests/users/test_auth_login.py::test_login_ok_sets_session_cookie` | — |
| 3.2.2 Au moins 64 bits d'entropie | Conforme | clé de session Django (32 caractères aléatoires, environ 165 bits) | Valeur par défaut de Django |
| 3.2.3 Stockage sûr dans le navigateur | Conforme | cookie `HttpOnly`, `Secure`, préfixe `__Host-` (`config/settings/prod.py:112-123`) ; `tests/test_prod_settings.py::test_prod_cookies_are_host_prefixed_secure_httponly` | Plus de jeton dans `sessionStorage` |
| 3.2.4 Jetons générés par un algorithme approuvé | Conforme | générateur `secrets` de Django | — |
| 3.3.1 Déconnexion et expiration invalident la session côté serveur | Conforme | `logout()` supprime la ligne de session (`users/auth_views.py:172-183`) ; `SessionLimiteeMiddleware` fait de même à l'expiration (`core/middleware.py:77-82`) ; `tests/users/test_auth_login.py::test_logout_ends_session` | — |
| 3.3.2 Réauthentification périodique (L2 : 12 h, ou 30 min d'inactivité) | Partiel | sessions de l'API : 8 h absolues et 30 min d'inactivité (`config/settings/base.py:488-489`, `core/middleware.py:51-86`) ; `test_auth_login.py::test_idle_30_minutes_expires_session`, `::test_absolute_8_hours_even_when_active` ; requêtes d'arrière-plan exclues de l'activité (AUTH-08, `test_auth_durcissements.py::test_background_polling_does_not_keep_the_session_alive`) | Conforme pour l'API. Restes : sessions de `/admin/` sans délai d'inactivité (AUTH-09, admin désactivé par défaut) ; l'exclusion du rafraîchissement automatique n'agit qu'une fois l'en-tête envoyé par le frontend (en cours) |
| 3.3.3 Fermeture des autres sessions après changement de mot de passe | Conforme | `terminer_sessions(..., sauf=...)` (`users/auth_views.py:319`, `users/auth_services.py:358-382`) ; toutes les sessions à une réinitialisation ou une désactivation ; `tests/users/test_auth_password.py::test_change_keeps_current_session_and_ends_the_others`, `::test_reset_with_code_changes_password_and_kills_sessions` | Automatique, sans option |
| 3.3.4 Voir et fermer ses sessions actives | Non conforme | aucun écran ni point d'API | AUTH-15 non corrigé |
| 3.4.1 Attribut `Secure` | Conforme | `SESSION_COOKIE_SECURE` exigé vrai, `CSRF_COOKIE_SECURE` (`config/settings/prod.py:114-117`) ; `tests/test_prod_settings.py::test_prod_refuse_session_cookie_secure_desactive` | — |
| 3.4.2 Attribut `HttpOnly` | Conforme | `SESSION_COOKIE_HTTPONLY` (`base.py:486`), `CSRF_COOKIE_HTTPONLY` (`prod.py:123`) ; `test_prod_cookies_are_host_prefixed_secure_httponly` | — |
| 3.4.3 Attribut `SameSite` | Conforme | `Lax` pour la session et le CSRF (`base.py:485,490`) ; `tests/test_security_defaults.py::test_session_cookie_policy_defaults` | — |
| 3.4.4 Préfixe `__Host-` | Conforme | `__Host-onea-session`, `__Host-onea-csrf` (`prod.py:119-120`) | — |
| 3.4.5 Chemin du cookie le plus précis possible | Conforme | une seule application par nom d'hôte, cookies `__Host-` (chemin `/`, sans domaine) | — |
| 3.5.1 Révocation des jetons OAuth | Non applicable | aucun OAuth | — |
| 3.5.2 Jetons de session plutôt que clés statiques | Conforme | sessions seulement (`base.py:277`) ; `tests/test_security_defaults.py::test_api_default_authentication_is_session_only` | Le jeton de `/metrics` est réservé à la supervision |
| 3.5.3 Jetons sans état signés | Non applicable | sessions en base, pas de jeton sans état | — |
| 3.7.1 Session complète ou réauthentification avant une opération sensible | Partiel | mot de passe actuel exigé pour changer de mot de passe et pour désactiver son code de connexion (`users/auth_services.py:493-558`) ; changement de mot de passe imposé avant tout accès (`core/middleware.py:89-110`) | Les actions d'administration des comptes (création, réinitialisation d'un tiers, rôle, délégation) n'exigent pas de réauthentification |

### V4 — Contrôle d'accès, délégation comprise (rejoué le 2026-11-04)

| Exigence | Statut | Preuve | Notes |
|---|---|---|---|
| 4.1.1 Contrôle sur une couche serveur de confiance | Conforme | permissions DRF (`users/account_permissions.py`) **et** contrôle répété dans les services sous verrou de ligne (`users/services.py:379-387,426-427,459,494-499`, `users/delegation.py:139-153`) | — |
| 4.1.2 Attributs de droits non modifiables par l'utilisateur | Conforme | rôle, état et délégation relus en base à chaque appel (`users/delegation.py:68-79`) ; `ProfilUtilisateurSerializer` refuse tout champ inconnu ; `is_staff` et `is_superuser` jamais modifiables ; `tests/users/test_delegation.py::test_delegate_cannot_grant_self_rights`, `::test_delegate_cannot_delegate` | — |
| 4.1.3 Moindre privilège | Partiel | délégués limités aux comptes AUDITEUR et AUDITE (`users/delegation.py:61,82-99`, AUTH-03) ; délégation et import réservés à l'ADMIN | Restes : un délégué « créer » ou « réinitialiser » peut obtenir l'affichage du mot de passe temporaire (`envoyer_courriel=false`) et donc prendre la main sur un compte AUDITEUR ou AUDITE ; l'ADMIN lit le contenu des missions par la piste d'audit tant que le réglage SEC-02 reste à « complet » |
| 4.1.5 Échec sûr | Conforme | acteur inconnu ou inactif : aucun droit (`users/delegation.py:68-79`) ; cible introuvable : protégée (`:92-93`) ; `Mission.objects.none()` par défaut (`missions/acces.py:96`) ; `tests/users/test_delegation.py::test_disabled_delegate_has_no_rights`, `::test_peut_rejects_unknown_action` | — |
| 4.2.1 IDOR | Conforme | comptes : `get_object` puis droits sur la cible (`droits_sur`, `users/delegation.py:111-123`), revérifiés dans le service ; missions : SEC-01 corrigé (`tests/missions/test_sec01_uuid_entier.py`) ; `tests/users/test_delegation.py::test_delegate_cannot_touch_rai_or_dg_account`, `::test_delegate_cannot_touch_admin_account`, `::test_delegate_cannot_touch_other_delegate`, `::test_delegate_cannot_touch_staff_or_superuser` ; fichier de mots de passe d'import lisible par son seul auteur | Matrice de lecture des missions : banc du 01/11, non rejoué |
| 4.2.2 Protection CSRF forte | Conforme | CSRF exigé sur toute écriture, y compris anonyme (connexion, code, déconnexion, oubli, réinitialisation), **avant** les limites de débit (`users/auth_views.py:87-97`) ; `CSRF_TRUSTED_ORIGINS = https://PUBLIC_HOST` ; cookies `SameSite=Lax` ; pas de CORS ; `tests/users/test_auth_login.py::test_csrf_required_on_post`, `tests/users/test_auth_api.py::test_session_write_without_csrf_token_is_refused`, `tests/users/test_auth_limites.py::test_csrf_checked_before_the_throttle_on_every_anonymous_endpoint` | Applicable depuis le passage aux sessions (était « sans objet » avec le jeton porteur) |
| 4.3.1 Interfaces d'administration protégées par plusieurs facteurs | Non conforme | le code de connexion par courriel est facultatif pour tous, y compris l'ADMIN (`users/auth_services.py:531-541`) ; `/admin/` désactivé par défaut en production (`config/settings/prod.py:99`, `tests/test_admin_toggle.py::test_admin_is_not_mounted_when_disabled`) ; une session ouverte par `/admin/login/` n'ouvre pas l'API (`users/authentication.py:23-27`) | Obligation du second facteur pour les comptes à privilèges : **décision ONEA en attente** (D19) |
| 4.3.2 Pas de listage ni de métadonnées exposées | Conforme | `/metrics` → 404 sans jeton (`tests/test_metriques.py`) ; schéma OpenAPI réservé à une session `is_staff` en production (`config/urls.py:13-16`) ; `tests/users/test_auth_api.py::test_docs_non_admin_session_is_403` | — |
| 4.3.3 Autorisation supplémentaire ou séparation des tâches | Partiel | séparation des tâches : seuls les ADMIN gèrent les comptes ADMIN, RAI et DG et les délégations (`users/delegation.py:145-153`) ; « quatre yeux » des missions (`missions/services/etapes.py`, scénario S4-08) | Aucune authentification renforcée pour les actions d'administration |

### V5 — Validation, assainissement, encodage (repris du 2026-11-01)

| Exigence | Statut | Preuve | Action |
|---|---|---|---|
| 5.1.2 Affectation de masse | C | `Meta.fields` explicites, statuts et auteurs en lecture seule ; `retirer_immuables` (`missions/views.py:137-149`) | — |
| 5.1.3 Validation positive des entrées | NC (partiel) | les UUID acceptent la forme entière (SEC-01) | SEC-01 (corrigé depuis) |
| 5.1.4 Données structurées typées | C | `ChoiceField`, bornes, caractères de contrôle refusés (`referentiel/serializers.py:212-219`) | — |
| 5.2.2 Assainissement du texte libre | C | gabarits Django avec échappement automatique, aucun `mark_safe` ni `|safe` (recherche dans `backend/apps`) | — |
| 5.2.5 Injection de gabarit | C | bac à sable Jinja immuable (`documents/moteur/bac_a_sable.py:84-124`) ; `backend/tests/documents/test_moteur_securite.py` ; ZAP 90035 PASS | — |
| 5.2.6 SSRF | C | aucune URL fournie par l'utilisateur ; URL de Gotenberg, Meilisearch et ClamAV fixées par la configuration ; liens des courriels construits depuis `PLATEFORME_URL` (https exigé, `prod.py:48-50`), jamais depuis l'en-tête `Host` | — |
| 5.2.7 SVG et contenu scriptable | C | SVG absent de la liste blanche (`core/fichiers.py:52-74`) | — |
| 5.3.1 Encodage de sortie | C | JSON seul en production (`prod.py:93-96`) ; React échappe par défaut, aucun `dangerouslySetInnerHTML` (recherche dans `frontend/src`) | — |
| 5.3.4 Requêtes paramétrées | C | voir les faux positifs du §3 | — |
| 5.3.x Injection de formules CSV/XLSX | C | `neutraliser_formule` et `data_type = "s"` ; tests `test_exports.py` de 4 apps | — |
| 5.5.x Désérialisation | C | Celery en JSON seulement (`base.py`) ; les tâches d'authentification ne reçoivent que des identifiants (AUTH-01) | — |

### V7 — Erreurs et journalisation (rejoué le 2026-11-04)

| Exigence | Statut | Preuve | Notes |
|---|---|---|---|
| 7.1.1 Ni identifiants secrets ni jeton de session dans les journaux | Conforme | journal `onea.securite` : identifiant interne du compte et adresse, jamais le mot de passe, le code ni l'identifiant saisi (`users/auth_services.py:25-27,97-103`) ; clé de limitation par identifiant = HMAC (`users/auth_throttles.py:136-161`) ; `MasquageFiltre` (`core/journalisation.py:29-59`) ; backends courriel console, fichier et mémoire refusés en production (AUTH-07) ; `tests/users/test_auth_otp.py::test_code_never_in_logs`, `test_auth_login.py::test_failed_login_is_logged_without_password`, `test_auth_password.py::test_password_events_are_logged_without_secrets` | — |
| 7.1.2 Pas d'autre donnée sensible | Conforme | adresses de courriel et chaînes de requête masquées (`core/journalisation.py:39-40`) ; `tests/core/test_journalisation.py::test_aucune_donnee_personnelle_dans_les_journaux` | L'adresse IP du client figure dans le journal de sécurité (nécessaire à l'enquête) |
| 7.1.3 Événements de sécurité journalisés | Partiel | échecs de connexion et de réinitialisation avec motif, verrouillages, blocage de la réinitialisation (niveau `ERROR`), plafond par adresse atteint, changements et réinitialisations de mot de passe, actions de gestion des comptes, échec d'envoi d'un mot de passe temporaire (`ERROR`) : `users/auth_services.py`, `users/auth_throttles.py:187-191`, `users/services.py`, `users/envois.py:114-121` | Les connexions **réussies** et les refus d'accès (403) n'ont pas de ligne dédiée : seulement la ligne de requête (`onea.requete` : chemin, statut, `user_id`) |
| 7.1.4 Informations suffisantes pour l'enquête | Conforme | JSON horodaté en UTC, `correlation_id` propagé aux tâches Celery, `logger`, compte et adresse (`core/journalisation.py:65-82,134-148`) ; `tests/core/test_journalisation.py::test_correlation_propagee_a_la_tache_celery` | — |
| 7.2.1 Toutes les décisions d'authentification journalisées | Partiel | refus : oui, avec motif et adresse (`auth_services.py:97-103,462-470`) | Succès : seulement la ligne de requête (statut 200, `user_id`, sans adresse dans le journal applicatif ; l'adresse est dans le journal d'accès nginx) |
| 7.2.2 Décisions de contrôle d'accès en échec journalisées | Partiel | ligne de requête avec statut 403 et `user_id` (`core/journalisation.py:90-126`) | Pas de motif ni de cible dans le journal |
| 7.3.1 Journaux protégés contre l'injection | Conforme | `json.dumps` (`core/journalisation.py:82`), nginx `escape=json` | — |
| 7.3.3 Journaux de sécurité protégés | Partiel | piste d'audit inaltérable (déclencheurs SQL, `core/gardes_sql.py`, `tests/core/test_gardes_sql.py`) | Le journal `onea.securite` va sur la sortie standard des conteneurs (`json-file`, 3 × 10 Mo, `docker/compose.prod.yml:25-29`) : lisible par l'administrateur de l'hôte, pas de centralisation, conservation courte |
| 7.3.4 Horloges synchronisées | Partiel | horodatage des journaux en UTC (`core/journalisation.py:68`), `USE_TZ = True` | La synchronisation de l'hôte (NTP) n'est pas vérifiable dans le dépôt |
| 7.4.1 Message d'erreur générique | Conforme | `api_exception_handler` (`core/handlers.py`), refus uniformes de connexion et de réinitialisation (`users/auth_views.py:60-61,213-218`) ; `tests/core/test_exception_handler.py` | — |
| 7.4.2 Gestion des exceptions dans tout le code | Conforme | broker injoignable : même réponse et repli journalisé (`users/auth_views.py:128-135,251-254`, `users/envois.py:66-75`) ; échec SMTP sans effet sur l'appelant (`users/courriels.py:24-31`) ; `tests/users/test_envois_courriels.py::test_login_answer_unchanged_when_the_broker_is_down`, `::test_broker_down_shows_the_password_once_and_keeps_no_row` | — |
| 7.4.3 Gestionnaire d'erreur de dernier recours | Conforme | `handler500 = erreur_500` (`config/urls.py:61`, `core/views.py:159-166`) ; échec de tâche journalisé sans arguments (`core/journalisation.py:151-160`, `tests/core/test_journalisation.py::test_echec_de_tache_journalise_sans_arguments`) | — |

### V8 — Protection des données (lignes touchées par l'authentification)

| Exigence | Statut | Preuve | Notes |
|---|---|---|---|
| 8.1.1 Pas de cache des données sensibles (rejoué) | Conforme | `PasDeCacheApiMiddleware` (`core/middleware.py:131-145`) ; réponses portant un mot de passe temporaire en `no-store` (`users/account_views.py:152-166`) ; `tests/users/test_auth_api.py::test_api_responses_are_no_store_private` | — |
| 8.2.2 Pas de donnée sensible dans le stockage du navigateur (rejoué) | Conforme | plus aucun jeton côté client : la session est un cookie `HttpOnly` ; `sessionStorage` ne garde que l'état du tutoriel (`frontend/src/features/tutoriel/storage.ts`), `localStorage` l'état de la barre latérale (`frontend/src/layouts/useSidebarCollapsed.ts`) | — |
| 8.3.1 Données sensibles hors de l'URL (rejoué) | Conforme | mots de passe et codes dans le corps des `POST` seulement (`users/auth_serializers.py`) ; recherche `q` exclue des journaux | — |
| 8.3.4 Données sensibles identifiées et protégées (repris) | Partiel | SEC-02 (paramétrable), SEC-08 et SEC-09 (corrigés) | Ligne du 01/11 (« NC partiel »), non rejouée |
| 8.3.7 Chiffrement authentifié des données qui doivent l'être (rejoué) | Conforme | mots de passe temporaires en attente d'envoi (`EnvoiMotDePasse`, 1 h, lu une fois) et fichier des mots de passe d'import (24 h, un téléchargement) chiffrés par Fernet (AES-CBC + HMAC-SHA-256), clé dérivée de `SECRET_KEY` avec un sel propre (`users/envois.py:44-47`, `users/provisioning.py`) ; `tests/users/test_envois_courriels.py::test_worker_drops_an_expired_row`, `::test_daily_purge_removes_expired_rows` | La base et `SECRET_KEY` sont tous deux dans `web` et `worker` : protège contre la fuite d'une sauvegarde seule |
| 8.3.x Intégrité des preuves (repris) | Conforme | écriture unique et SHA-256 vérifié à la lecture (`ouvrir_piece_verifiee`) ; `backend/tests/accomplissement/test_integrite.py`, `backend/tests/documents/test_integrite.py` | SEC-07 (confirmations) |

### V9 — Communications (lignes touchées)

| Exigence | Statut | Preuve | Notes |
|---|---|---|---|
| 9.1.1 TLS pour toutes les connexions client (repris) | Conforme | redirection 80 → 443 vers un hôte fixe (`prod.conf`) ; HSTS 1 an | — |
| 9.1.2 Suites de chiffrement fortes (repris) | Conforme | TLS 1.2 et 1.3, liste Mozilla *intermediate*, sans tickets (`prod.conf`) ; `scripts/recette/tests/tls.sh` | — |
| 9.2.1 Certificats de confiance pour les connexions sortantes (rejoué) | Conforme | seule connexion sortante de l'application : le relais SMTP, depuis le `worker` ; contexte TLS par défaut de Python (vérification du certificat et du nom) avec `SSL_CERT_FILE` (`docker/compose.prod.yml:101`, `CA_BUNDLE_PATH`) | La ligne « TLS vers Keycloak » de la revue initiale est sans objet. Non vérifié face au relais réel de l'ONEA |
| 9.2.2 Chiffrement des connexions sortantes (rejoué) | Partiel | STARTTLS (`smtp+tls://`) ou TLS implicite (`smtps://`) gérés (`config/settings/prod.py:42-45`, `tests/test_prod_settings.py::test_prod_email_transport_security_and_timeout`) | `smtp://` en clair reste accepté (AUTH-18) : codes et mots de passe temporaires passeraient en clair jusqu'au relais. PostgreSQL, Redis, Meilisearch, Gotenberg et ClamAV sont joints en clair sur des réseaux Docker `internal` |

### V10 — Code malveillant (repris du 2026-11-01)

| Exigence | Statut | Preuve | Action |
|---|---|---|---|
| 10.3.2 Intégrité des dépendances | C | `uv.lock` et `package-lock.json` versionnés ; `scripts/verifier-epinglage.sh` (images épinglées) | — |
| 10.3.x Dépendances sans vulnérabilité connue | C (produit) / NC (outils de développement) | `pip-audit` : 0 ; `npm audit --omit=dev` : 0 ; outils de développement : 14 modérées (au 01/11 ; à rejouer : `argon2-cffi` et `cryptography` sont maintenant au cœur de l'authentification) | SEC-10 |
| 10.2.x Pas de fonction cachée ni de porte dérobée | C | commandes de test et de démonstration gardées : `creer_comptes_e2e` refuse hors `DEBUG`, hors base `onea_e2e_*` et hors hôte local ; `peupler_demo` interdit en production ; aucun mot de passe par défaut (rejoué le 2026-11-04 pour cette ligne : les clients Keycloak de développement et de charge n'existent plus) | — |

### V12 — Fichiers et ressources (repris du 2026-11-01)

| Exigence | Statut | Preuve | Action |
|---|---|---|---|
| 12.1.1 Taille maximale | C | 50 Mo (`base.py:201`), nginx 55 Mo sur `/api/` et 1 Mo ailleurs (`prod.conf:46,110`) ; contrôle avant lecture (`accomplissement/views.py:640`) | — |
| 12.1.2 Bombes de décompression | C | ≤ 2 000 entrées, ≤ 200 Mo, ratio ≤ 20 au-delà de 16 Mo, sans décompresser (`core/fichiers.py:184-215`) ; `backend/tests/core/test_fichiers.py` | — |
| 12.1.3 Quota par utilisateur ou par espace | C | `DOCUMENTS_QUOTA_MO`, débit `televersement` de 30/h (`base.py:174,265`) | — |
| 12.2.1 Type réel contrôlé (signature d'octets) | C | `controler_entete` (`core/fichiers.py:138-170`) ; `backend/tests/accomplissement/test_api_securite_fichiers.py` | — |
| 12.3.1 Nom du client jamais dans un chemin | C | `core/fichiers.py:13` (le nom ne sert qu'à l'extension), stockage adressé par identifiant | — |
| 12.3.2 Traversée de chemin | C | `_nom_suspect` sur les archives (`core/fichiers.py:180-181`) ; `nom_telechargement` retire les séparateurs et les caractères de contrôle (`documents/views.py:88-94`) | — |
| 12.4.1 Stockage hors de la racine web | C | `valider_documents_root` (`prod.py:57`) ; pas de `MEDIA_URL` | — |
| 12.4.2 Analyse antivirus | C | ClamAV (`compose.prod.yml`), `prod.py` refuse `aucun`, échec fermé ; `backend/tests/core/test_antivirus.py` | SEC-04 (résolu) |
| 12.5.1 Pas de service de fichiers par extension | C | nginx ne sert que `/static/` (collectstatic) | — |
| 12.5.2 `Content-Disposition` et `nosniff` sur les téléchargements | C | `as_attachment=True`, `nosniff` (`documents/views.py:97-107`), nginx `nosniff` partout | — |
| 12.6.1 SSRF par fichier (liens externes OOXML) | C | `verifier_sortie` refuse champs et liens externes (`documents/moteur/controle_ooxml.py`) ; `backend/tests/documents/test_securite.py` | — |

### V13 — API (lignes touchées)

| Exigence | Statut | Preuve | Notes |
|---|---|---|---|
| 13.1.1 Même encodage et même parseur partout (repris) | Partiel | la garde et le sérialiseur analysaient l'UUID différemment (SEC-01) | Ligne du 01/11 (« NC partiel ») ; SEC-01 corrigé depuis par T29, non rejoué ici |
| 13.1.3 Pas de secret dans l'URL (rejoué) | Conforme | session par cookie ; mots de passe et codes dans le corps ; le lien du fichier de mots de passe d'import est un UUID à usage unique réservé à son auteur | — |
| 13.1.4 Décisions d'accès dans l'API (rejoué) | Conforme | voir V4 | — |
| 13.2.1 Méthodes HTTP limitées (repris) | Conforme | `http_method_names` sans PUT (par exemple `signatures/views.py:60`) ; banc du 01/11 : `TRACE` → 405 | — |
| 13.2.3 CSRF de l'API (rejoué) | Conforme | voir 4.2.2 | Était « sans objet » avec le jeton porteur |
| 13.2.5 Content-Type vérifié (repris) | Conforme | `MultiPartParser` explicite pour les fichiers ; JSON seul en production | `FormParser` reste actif : sans effet sur le CSRF, vérifié avant tout traitement |
| 13.2.6 Limitation de débit (rejoué) | Conforme | nginx `/api/` 50 r/s, rafale 100 (`docker/nginx/prod.conf:31,107`) ; authentification : un compteur par point d'entrée et par adresse, plafonds d'échecs, compteur par utilisateur pour le changement de mot de passe (`config/settings/base.py:298-312`, `users/auth_throttles.py`) ; `tests/users/test_auth_limites.py`, `tests/core/test_throttling.py` | Réponse 429 avec `Retry-After` ; les compteurs par adresse laissent passer si le cache tombe (les limites par compte, en base, restent) |
| 13.x CORS (rejoué) | Conforme | aucune application ni intergiciel CORS en production, variable `CORS_ALLOWED_ORIGINS` ignorée ; `tests/test_prod_settings.py::test_prod_ignores_a_stale_cors_variable`, `::test_prod_cors_preflight_from_foreign_origin_has_no_allow_origin` | Même origine pour la SPA et l'API |

### V14 — Configuration (lignes touchées)

| Exigence | Statut | Preuve | Notes |
|---|---|---|---|
| 14.1.x Construction reproductible (repris) | Conforme | images épinglées (`scripts/verifier-epinglage.sh`), `uv sync --frozen` | — |
| 14.1.3 Configuration durcie du cadriciel (rejoué) | Partiel | production : `DEBUG=False`, `SESSION_COOKIE_SECURE` exigé, backends courriel restreints à SMTP et `dummymail://` (AUTH-07), `/admin/` désactivé par défaut, `/admin/password_change/` en 404 (`config/settings/prod.py`, `config/urls.py:47-58`) | Restes : `smtp://` en clair accepté (AUTH-18) ; `AUTH_REINITIALISATION_ECHECS_MAX` n'est pas transmis par `docker/compose.prod.yml` (la valeur par défaut 15 s'applique en production, le réglage par `.env.prod` est sans effet) |
| 14.2.1 Dépendances à jour (repris) | Conforme (produit) | voir V10 | SEC-10 |
| 14.3.2 Mode débogage désactivé (rejoué) | Conforme | `DEBUG = False` (`config/settings/prod.py:17`) ; `tests/test_prod_settings.py` | — |
| 14.3.3 Pas de bannière de version (repris) | Conforme | `server_tokens off` ; banc du 01/11 : `Server: nginx` | — |
| 14.4.1 `Content-Type` et jeu de caractères (repris) | Conforme | JSON `application/json`, téléchargements typés | — |
| 14.4.3 CSP (rejoué) | Conforme | `Content-Security-Policy` posé par nginx sur l'unique hôte (`docker/nginx/prod.conf:91`) ; `style-src 'unsafe-inline'` accepté (styles inline de Radix) | Plus d'hôte SSO : la réserve SEC-05 tombe |
| 14.4.4 `X-Content-Type-Options: nosniff` (repris) | Conforme | banc du 01/11, toutes les réponses | — |
| 14.4.5 HSTS (rejoué) | Conforme | `max-age=31536000; includeSubDomains` (nginx et `SECURE_HSTS_SECONDS`, `prod.py:109-110`) | Plus de doublon sur un hôte SSO |
| 14.4.6 `Referrer-Policy` (repris) | Conforme | `strict-origin-when-cross-origin` (banc du 01/11) | — |
| 14.4.7 Protection contre l'encadrement (repris) | Conforme | `X-Frame-Options: DENY` et `frame-ancestors 'none'` (banc du 01/11) | — |
| 14.5.1 Méthodes HTTP (repris) | Conforme | `TRACE` → 405 (banc du 01/11) | — |
| 14.5.2 En-têtes de proxy non falsifiables (rejoué) | Conforme | `X-Real-IP` cru seulement depuis `TRUSTED_PROXY_CIDRS` (adresse fixe de nginx), qui écrase `X-Real-IP` et `X-Forwarded-*` (`core/reseau.py`, `core/middleware.py:113-128`) ; adresse utilisée pour les limites de l'authentification ; `tests/core/test_adresse_client.py` ; `scripts/recette/tests/edge.sh` | — |
| 14.5.3 CORS : liste d'origines stricte (rejoué) | Conforme | voir 13.x | — |

### 4.1 Décompte des chapitres rejoués

| Chapitre | Conforme | Partiel | Non conforme | Non applicable | Total |
|---|---|---|---|---|---|
| V2 Authentification | 21 | 9 | 7 | 15 | 52 |
| V3 Sessions | 13 | 2 | 1 | 2 | 18 |
| V4 Contrôle d'accès | 6 | 2 | 1 | 0 | 9 |
| V7 Journalisation | 7 | 5 | 0 | 0 | 12 |
| V8 (lignes du tableau) | 5 | 1 | 0 | 0 | 6 |
| V9 (lignes du tableau) | 3 | 1 | 0 | 0 | 4 |
| V13 (lignes du tableau) | 7 | 1 | 0 | 0 | 8 |
| V14 (lignes du tableau) | 13 | 1 | 0 | 0 | 14 |

Pour V8, V9, V13 et V14, les lignes « repris » sont comptées avec leur statut du 01/11 traduit
(C → Conforme, « NC partiel » → Partiel). Les non-conformités de V2, V3 et V4 sont des
évolutions fonctionnelles (indicateur de robustesse, affichage du mot de passe, WebAuthn,
poivre, liste des sessions), des arbitrages (AUTH-10, mot de passe temporaire envoyé par
courriel) ou une décision de l'ONEA (second facteur obligatoire des administrateurs, D19).

## 5. Relecture contradictoire des constats élevés (étape 4)

Le seul constat élevé, SEC-01, a été soumis à un second relecteur indépendant, avec le code et
sans la conclusion. Son verdict est consigné ci-dessous.

_(à compléter)_

Pour les constats élevés de l'authentification (AUTH-01 à AUTH-03), les corrections ont été
relues par une revue de code ; aucune relecture contradictoire indépendante n'est consignée.

## 6. Analyse dynamique : rapports

> Les résultats ci-dessous datent de la revue du 2026-11-01 (pile avec Keycloak). **Aucune
> analyse dynamique n'a été rejouée sur l'authentification interne** : à faire sur la recette
> (`scripts/recette/zap.sh`, critère B6 de `docs/PRET-A-LIVRER.md`), avec une session ouverte
> par `POST /api/v1/auth/login/` au lieu d'un jeton porteur.

- Script : `scripts/recette/zap.sh` (baseline de l'application, api-scan sur OpenAPI ;
  `ZAP_ACTIF=1` ajoute l'analyse active, sur une instance jetable seulement). Les rapports
  (HTML, JSON, Markdown) vont dans `.recette/zap/`. Ce sont des artefacts : ils ne sont pas
  versionnés, car ils peuvent contenir des en-têtes de requête.
- Exécution de la revue initiale (instance jetable, analyse active) : `FAIL-NEW: 0`,
  `WARN-NEW: 4`, `PASS: 118`. Les 4 avertissements sont traités au §3 (faux positifs) et dans
  la CSP (`style-src 'unsafe-inline'` accepté). Baseline de l'application : informatif seulement
  (COEP absent, commentaires dans le JavaScript minifié, directives de cache).

## 7. Constats ouverts

- **Revue initiale** : SEC-10 (outils de développement). SEC-07 accepté. SEC-03, SEC-05 et
  SEC-06 sans objet.
- **Authentification interne, à décider** : AUTH-10 (notifications au titulaire), AUTH-13
  (liste de mots de passe compromis), second facteur obligatoire pour les comptes à privilèges
  (D19, 4.3.1), codes à 8 chiffres au lieu de 6 (2.2.1, 2.5.6).
- **Authentification interne, à terminer** : AUTH-08 (en-tête `X-Onea-Arriere-Plan` à envoyer
  par le frontend), AUTH-09 (délai d'inactivité des sessions admin), AUTH-11 (contraintes
  d'unicité insensibles à la casse en base, après contrôle des données), AUTH-18 (exiger TLS
  vers le relais SMTP), transmission de `AUTH_REINITIALISATION_ECHECS_MAX` par
  `docker/compose.prod.yml`, AUTH-14 à AUTH-17 et AUTH-19 (information).
- **À vérifier sur une pile réelle** : envoi des courriels d'authentification par le `worker`
  jusqu'au relais, réponses 429 et plafonds derrière le NAT, cookies et en-têtes dans un
  navigateur, analyse ZAP (§6), scénarios S4-29 à S4-41 de `docs/recette/scenarios-de-test.md`.
