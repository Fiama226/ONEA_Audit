# Authentification interne (remplacement de Keycloak) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** L'application gère elle-même connexion, comptes, mots de passe, OTP par courriel et délégation ; Keycloak est supprimé.

**Architecture:** Session Django (cookie `HttpOnly`, CSRF) servie sous la même origine que le front ; modèles et services dans `apps/users` (modules `auth_*`), endpoints sous `/api/v1/auth/`. Le front remplace le client OIDC par un `AuthProvider` fondé sur `/api/v1/auth/session/`. Keycloak, sa synchronisation et ses tests sont supprimés en dernier.

**Tech Stack:** Django 5.2, DRF, `argon2-cffi` (MIT), sessions en base, Mailpit (dev) ; React 19, TanStack Query, react-hook-form + zod.

**Spec:** `docs/superpowers/specs/2026-11-03-authentification-interne-design.md`

Branche : `feat/auth-interne` créée depuis `develop` (worktree `C:/tmp-auth`). Python : `C:\v\onea\Scripts\python.exe` ; base de test dédiée `onea_auth_test` (jamais `onea`) ; tests ciblés seulement, suites complètes à la fin (Task 12).

## Global Constraints

- Licences autorisées par `CLAUDE.md` uniquement ; français dans l'interface et les messages, anglais dans le code et les commits ; chaque commit se termine par `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Mot de passe : 12 caractères minimum ; hachage Argon2id ; temporaire généré aléatoirement, valable 72 h, changement obligatoire à la première connexion.
- OTP : 6 chiffres, haché, valable 10 min, 5 essais, usage unique, un seul actif par agent et par objet (`RESET` / `LOGIN`), purgé après 24 h.
- Verrouillage : 5 échecs consécutifs, 15 minutes ; réponse identique (message, code HTTP, délai) pour compte inexistant, mauvais mot de passe ou compte verrouillé.
- Sessions : 8 h au plus, 30 min d'inactivité, toutes invalidées au changement de mot de passe, stockage en base.
- Rôles inchangés : ADMIN, RAI, AUDITEUR, AUDITE, DG. Rôle obligatoire à la création. Plus de `role_provisoire`.
- Délégation : quatre droits `creer`, `reinitialiser`, `roles`, `desactiver` ; réservée à l'ADMIN ; un délégué ne peut ni se donner des droits, ni toucher un ADMIN, ni attribuer ADMIN, ni déléguer, ni se désactiver.
- OTP à la connexion : activable par le seul propriétaire, et seulement si l'envoi de courriels est configuré ; l'administrateur ou un délégué « réinitialiser » peut le **désactiver** (journalisé).
- Aucun mot de passe, code ou jeton en clair dans l'API après coup, les journaux ou la piste d'audit.
- Navigateur seul : plus de jeton Bearer ; `CORS_ALLOWED_ORIGINS` retiré.

## Review Focus

- Énumération : « mot de passe oublié » et « connexion » répondent pareil pour compte inconnu, désactivé, verrouillé (Task 3, 4).
- Rejeu / force brute d'OTP : 6e essai, code expiré, code déjà utilisé, ancien code après redemande (Task 2, 4).
- Élévation de privilèges : délégué qui s'octroie un droit, rend ADMIN, désactive un ADMIN ou lui-même (Task 6).
- Compte désactivé avec session ouverte : la requête suivante est refusée (Task 3).
- Mot de passe temporaire expiré ou jamais changé : seul le changement est possible (Task 3).
- Import CSV : le fichier de mots de passe temporaires n'est téléchargeable qu'une fois (Task 7).

## File Structure

- `backend/apps/users/models.py` : champs d'authentification sur `User`, modèles `CodeOtp`, `DelegationGestionComptes`.
- `backend/apps/users/auth_services.py` : connexion, verrouillage, OTP, mots de passe temporaires, réinitialisation.
- `backend/apps/users/auth_views.py`, `auth_urls.py`, `auth_serializers.py`, `auth_throttles.py` : API `/api/v1/auth/`.
- `backend/apps/users/delegation.py` : calcul des droits effectifs (`peut(acteur, action, cible)`).
- `backend/apps/users/courriels.py` : courriels de bienvenue et de code.
- `frontend/src/auth/` : `AuthProvider`, `useAuth`, pages `LoginPage`, `ForgotPasswordPage`, `ChangePasswordPage`, `OtpStep`.
- Supprimés (Task 11) : `keycloak_admin.py`, `keycloak_sync.py`, `oidc.py`, `authentication.OIDCBearerAuthentication`, `tasks.py` (sync), `docker/keycloak/`, `frontend/src/auth/oidc*`.

---

### Task 1: Modèle de données et hachage

**Files:**
- Modify: `backend/apps/users/models.py`, `backend/config/settings/base.py:151` (validateurs, `PASSWORD_HASHERS`), `backend/pyproject.toml` (+ `argon2-cffi`), `backend/uv.lock`
- Create: migration `backend/apps/users/migrations/00NN_auth_interne.py`
- Test: `backend/tests/users/test_auth_models.py`

**Interfaces:**
- Produces: sur `User` : `doit_changer_mot_de_passe: bool`, `mot_de_passe_expire_le: DateTime|None`, `echecs_connexion: int`, `verrouille_jusqu_a: DateTime|None`, `otp_connexion_actif: bool`. Modèle `CodeOtp(user, objet: "RESET"|"LOGIN", code_hash, expire_le, essais, utilise_le, created_at)`. Modèle `DelegationGestionComptes(user OneToOne, creer, reinitialiser, roles, desactiver: bool, accorde_par, accorde_le)` sous auditlog. Suppression de `keycloak_id`, `keycloak_sync_*`, `role_provisoire`, `profil_gere_localement`.

- [ ] **Step 1: Write failing tests** `test_auth_models.py` : `test_password_hash_is_argon2` (`make_password` commence par `argon2$`), `test_min_length_12_rejected` (`validate_password("Court1!")` lève), `test_one_active_otp_per_objet` (contrainte unique conditionnelle sur `utilise_le is null`), `test_delegation_is_one_per_user`.
- [ ] **Step 2: Run** `pytest tests/users/test_auth_models.py -v` → FAIL.
- [ ] **Step 3: Implement** champs, modèles, `PASSWORD_HASHERS` (Argon2 en tête), `MinimumLengthValidator` à 12, migration (suppression des champs Keycloak dans la même migration, données de dev non conservées sauf rôle).
- [ ] **Step 4: Run** le test et `python manage.py makemigrations --check` → PASS.
- [ ] **Step 5: Commit** `feat(users): auth models, argon2 hashing, 12-char policy`.

### Task 2: Services de codes OTP et de mots de passe temporaires

**Files:**
- Create: `backend/apps/users/auth_services.py` (partie OTP), `backend/apps/users/courriels.py`
- Test: `backend/tests/users/test_auth_otp.py`

**Interfaces:**
- Produces: `emettre_otp(user, objet) -> str` (renvoie le code en clair une seule fois, invalide l'éventuel code actif) ; `verifier_otp(user, objet, code) -> bool` (usage unique, 5 essais, expiration 10 min) ; `generer_mot_de_passe_temporaire() -> str` (≥ 16 caractères) ; `envoi_courriel_actif() -> bool` (vrai si `EMAIL_HOST` configuré ou backend console/Mailpit en dev) ; `envoyer_bienvenue(user, mot_de_passe) -> bool`, `envoyer_code(user, code, objet) -> bool` ; `purger_codes_expires() -> int` (supprime les codes expirés depuis plus de 24 h, appelé par une tâche Celery quotidienne `users.purger_codes` ajoutée à `CELERY_BEAT_SCHEDULE`).

- [ ] **Step 1: Write failing tests** : `test_purge_removes_codes_expired_over_24h_only`, `test_code_is_six_digits_and_stored_hashed`, `test_code_valid_once` (2e vérification False), `test_sixth_attempt_rejected_even_with_good_code`, `test_expired_after_10_minutes` (freezegun), `test_new_code_invalidates_old`, `test_code_never_in_logs` (caplog).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** avec `secrets.choice`, `check_password` pour comparer, courriels en français depuis modèles texte.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(users): one-time codes and welcome emails`.

### Task 3: Connexion, session, verrouillage

**Files:**
- Modify: `backend/apps/users/auth_services.py`, `backend/config/settings/base.py` (session en base, 8 h, middleware d'inactivité 30 min, `DEFAULT_AUTHENTICATION_CLASSES` = `SessionAuthentication401`), `backend/apps/core/middleware.py`
- Create: `backend/apps/users/auth_views.py`, `auth_urls.py`, `auth_serializers.py`, `auth_throttles.py` ; brancher dans `backend/config/urls.py`
- Test: `backend/tests/users/test_auth_login.py`

**Interfaces:**
- Produces (API) : `POST /api/v1/auth/login/ {identifiant, mot_de_passe}` → 200 `{etape: "OK"|"OTP"|"CHANGER_MOT_DE_PASSE", me}` ou 401 `{detail: "Identifiant ou mot de passe incorrect."}` identique dans tous les cas d'échec ; `POST /auth/login/otp/ {code}` ; `POST /auth/logout/` ; `GET /auth/session/` (200 avec `me` ou 401) ; `GET /auth/csrf/`. Service `authentifier(identifiant, mot_de_passe) -> Resultat`.

- [ ] **Step 1: Write failing tests** : `test_login_ok_sets_session_cookie`, `test_unknown_wrong_password_and_locked_give_identical_response` (corps, statut), `test_lock_after_5_failures_for_15_minutes`, `test_disabled_account_cannot_login`, `test_disabled_account_session_rejected_on_next_request`, `test_temp_password_expired_blocks_login`, `test_must_change_password_only_allows_change_endpoint`, `test_login_with_email_or_username`, `test_idle_30_minutes_expires_session`, `test_csrf_required_on_post`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement**. Comparaison à temps constant (hacher un mot de passe factice si le compte n'existe pas) ; limitation par IP via DRF throttle.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(users): session login with lockout and uniform errors`.

### Task 4: Mot de passe oublié, changement, OTP à la connexion

**Files:**
- Modify: `auth_services.py`, `auth_views.py`, `auth_urls.py`
- Test: `backend/tests/users/test_auth_password.py`

**Interfaces:**
- Produces : `POST /auth/password/forgot/ {identifiant}` → toujours 202 même corps ; `POST /auth/password/reset/ {identifiant, code, nouveau_mot_de_passe}` ; `POST /auth/password/change/ {ancien, nouveau}` (session) ; `POST /auth/otp/enable/` et `/disable/` (propriétaire ; `enable` refusé 409 « Envoi de courriels non configuré » si `envoi_courriel_actif()` est faux) ; le login renvoie `etape: "OTP"` quand `otp_connexion_actif`. Un changement ou une réinitialisation invalide toutes les sessions de l'agent, remet `echecs_connexion` à 0 et `doit_changer_mot_de_passe` à faux.

- [ ] **Step 1: Write failing tests** : `test_forgot_identical_for_unknown_disabled_and_active`, `test_forgot_sends_code_only_to_active_account`, `test_reset_with_code_changes_password_and_kills_sessions`, `test_reset_wrong_code_five_times_locks_code`, `test_reset_rejects_weak_password`, `test_change_requires_old_password`, `test_otp_enable_refused_without_email`, `test_login_requires_otp_when_enabled`, `test_otp_cannot_be_enabled_by_admin_for_other_user`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement**. Invalidation des sessions : supprimer les `Session` dont `_auth_user_id` correspond.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(users): password reset, change and optional login OTP`.

### Task 5: Création de compte, réinitialisation et déblocage par l'administrateur

**Files:**
- Modify: `backend/apps/users/services.py`, `account_views.py`, `account_serializers.py`, `account_urls.py`
- Test: `backend/tests/users/test_account_creation.py`

**Interfaces:**
- Consumes: Task 2 (`generer_mot_de_passe_temporaire`, `envoyer_bienvenue`).
- Produces : `creer_compte(*, donnees, par: User, envoyer_courriel: bool) -> tuple[User, str|None]` (le mot de passe temporaire n'est renvoyé que si le courriel n'est pas parti) ; `reinitialiser_mot_de_passe(compte, *, par) -> tuple[str, bool]` (déverrouille, invalide les sessions) ; `desactiver_otp(compte, *, par)`. Endpoints : `POST /user-accounts/` (rôle obligatoire), `POST /user-accounts/{id}/reset-password/`, `POST /user-accounts/{id}/disable-otp/`. Piste d'audit : acteur, cible, action, sans secret.

- [ ] **Step 1: Write failing tests** : `test_create_requires_role`, `test_create_sends_welcome_and_hides_password`, `test_create_without_email_returns_password_once`, `test_second_read_never_returns_password`, `test_reset_unlocks_account_and_kills_sessions`, `test_disable_otp_logged`, `test_audit_entry_has_no_secret`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**. **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(users): admin account creation and reset`.

### Task 6: Délégation de la gestion des comptes

**Files:**
- Create: `backend/apps/users/delegation.py`
- Modify: `account_permissions.py`, `account_views.py`, `account_serializers.py`, `account_urls.py` (`/user-accounts/{id}/delegation/`)
- Test: `backend/tests/users/test_delegation.py`

**Interfaces:**
- Produces : `peut(acteur: User, action: Literal["creer","reinitialiser","roles","desactiver"], cible: User|None) -> bool` ; `GET/PUT /user-accounts/{id}/delegation/` (ADMIN seulement). `IsAdmin` est remplacé par `PeutGererComptes(action)` sur les endpoints concernés.

- [ ] **Step 1: Write failing tests** : `test_admin_can_do_all`, `test_delegate_limited_to_granted_actions`, `test_delegate_cannot_grant_self_rights`, `test_delegate_cannot_touch_admin_account`, `test_delegate_cannot_assign_admin_role`, `test_delegate_cannot_delegate`, `test_delegate_cannot_disable_self`, `test_revoked_delegation_effective_immediately`, `test_delegation_changes_audited`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**. **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(users): configurable account-management delegation`.

### Task 7: Imports CSV/annuaire sans Keycloak et commande d'amorçage

**Files:**
- Modify: `backend/apps/users/provisioning.py` (suppression de la lecture annuaire Keycloak ; `importer_csv` crée directement les comptes), `backend/apps/users/management/commands/import_accounts.py`, `demo.py`
- Create: `backend/apps/users/management/commands/creer_administrateur.py`
- Test: `backend/tests/users/test_provisioning_csv.py` (mis à jour), `test_creer_administrateur.py`

**Interfaces:**
- Produces : `importer_csv(contenu, *, by, dry_run, envoyer_courriel) -> RapportImport` avec `fichier_mots_de_passe_id: UUID|None` ; `GET /user-accounts/import-passwords/{id}/` renvoie le CSV une seule fois puis 404 et détruit le contenu ; commande `creer_administrateur --identifiant X --courriel Y` (crée ou réinitialise, affiche le mot de passe temporaire une fois) ; `demo.py` donne un mot de passe temporaire aux six comptes de test.

- [ ] **Step 1: Write failing tests** : `test_import_creates_accounts_with_temp_passwords`, `test_password_file_downloadable_once`, `test_import_emails_when_active`, `test_creer_administrateur_creates_then_resets`, `test_six_demo_accounts_must_change_password`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**. **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(users): CSV import and bootstrap command without Keycloak`.

### Task 8: Front — connexion, session, pages publiques

**Files:**
- Modify: `frontend/src/auth/AuthProvider.tsx`, `useAuth.ts`, `types.ts`, `frontend/src/api/client.ts` (cookies `credentials: "include"`, en-tête CSRF, plus de `Authorization`), `frontend/src/routes.tsx`, `frontend/src/i18n/fr.ts`
- Create: `frontend/src/auth/LoginPage.tsx`, `OtpStep.tsx`, `ForgotPasswordPage.tsx`, `ResetPasswordPage.tsx`, `ChangePasswordPage.tsx` (+ tests)
- Delete: `frontend/src/auth/oidc.ts`, `oidc.test.ts`, dépendance `oidc-client-ts`

**Interfaces:**
- Consumes: endpoints des Tasks 3-4.
- Produces : `useAuth()` expose `{status, me, login(identifiant, mdp), verifyOtp(code), logout()}` ; routes `/connexion`, `/mot-de-passe-oublie`, `/mot-de-passe/reinitialiser`, `/mot-de-passe/changer` ; `RequireAuth` redirige vers `/mot-de-passe/changer` quand `etape === "CHANGER_MOT_DE_PASSE"`.

- [ ] **Step 1: Write failing tests** : `LoginPage` (erreur liée au champ avec `aria-describedby` et focus, message identique), `OtpStep`, `ChangePasswordPage` (règle 12 caractères affichée), `AuthProvider` (401 → anonyme ; session expirée → message), `RequireAuth` redirection.
- [ ] **Step 2: Run** `npx vitest run src/auth` → FAIL. **Step 3: Implement** selon `docs/design/charte-graphique.md`. **Step 4: Run** → PASS, puis `tsc`, `eslint`, `prettier`.
- [ ] **Step 5: Commit** `feat(frontend): in-app login, OTP and password pages`.

### Task 9: Front — administration des comptes, délégation, Mon compte

**Files:**
- Modify: `frontend/src/features/utilisateurs/` (`api.ts`, `schemas.ts`, `pages/UserListPage.tsx`, `pages/UserDetailPage.tsx`, `components/` ; supprimer `KeycloakSyncNotice.tsx`, `AccountStatusCard.tsx` état de synchro), `frontend/src/features/` page « Mon compte » (OTP à la connexion, changement de mot de passe), `frontend/src/api/schema.d.ts` régénéré par `scripts/gen-api.sh`
- Test: tests de chaque page modifiée

**Interfaces:**
- Consumes: Tasks 5-7. Produces : formulaire « Nouvel agent » (rôle obligatoire, case « Envoyer le courriel de bienvenue »), affichage unique du mot de passe temporaire, bouton « Réinitialiser le mot de passe », bouton « Désactiver le code de connexion », carte « Délégation » (quatre cases, ADMIN seulement), import CSV avec téléchargement unique.

- [ ] **Step 1: Write failing tests** (création sans courriel affiche le mot de passe une fois ; carte Délégation invisible pour non-ADMIN ; case OTP désactivée avec explication si courriels non configurés).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**. **Step 4: Run** `vitest` ciblé + `scripts/check-api-fresh.sh` → PASS.
- [ ] **Step 5: Commit** `feat(frontend): account administration, delegation and my-account`.

### Task 10: Infrastructure : même origine, courriel, suppression de Keycloak

**Files:**
- Modify: `docker/compose.yml`, `compose.dev.yml`, `compose.prod.yml` (retirer `keycloak`, `keycloak-db`), `docker/nginx/prod.conf`, `.env.example`, `Makefile`, `scripts/dev-up.ps1`, `dev-down.ps1`, `e2e.sh`, `e2e.ps1`, `check-services.sh`, `generer-secrets.sh`, `backup.sh`, `restore.sh`, `scripts/recette/*`, `backend/config/settings/{base,dev,prod,test}.py` (retirer OIDC et CORS, `SESSION_COOKIE_SECURE` et `CSRF_TRUSTED_ORIGINS` en prod), proxy de dev Vite pour `/api`
- Delete: `docker/keycloak/`
- Test: `backend/tests/test_prod_settings.py`, `test_deploiement_lot8.py` (adaptés)

- [ ] **Step 1: Write failing tests** : `prod` refuse de démarrer sans `SESSION_COOKIE_SECURE`; aucun fichier compose ne mentionne `keycloak` ; `.env.example` sans variable `KEYCLOAK_*`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**. **Step 4: Run** `docker compose config -q` sur les trois fichiers + tests → PASS.
- [ ] **Step 5: Commit** `chore(infra): remove Keycloak from stack, same-origin proxy`.

### Task 11: Suppression du code Keycloak et migration des tests

**Files:**
- Delete: `backend/apps/users/{keycloak_admin,keycloak_sync,oidc}.py`, `authentication.OIDCBearerAuthentication`, tâches de synchronisation, `backend/tests/users/test_keycloak_*.py`, `test_oidc.py`, `test_userinfo_cache.py`, `test_account_oidc_sync.py`, dépendance `mozilla-django-oidc`
- Modify: `backend/tests/conftest.py` (fixtures de clients authentifiés par `force_login`, plus de `fake_keycloak`), tous les tests qui forgent un jeton Bearer ; `frontend/e2e/*` (connexion par formulaire)

- [ ] **Step 1:** `grep -ri "keycloak\|oidc" backend frontend/src frontend/e2e docker scripts` ; la liste est la liste de travail.
- [ ] **Step 2: Implement** suppression et réécriture des fixtures.
- [ ] **Step 3: Run** `pytest -q -x` sur `tests/users` et un échantillon par app (`missions`, `documents`, `suivi`) → PASS ; `grep` ne renvoie plus rien hors historique/doc.
- [ ] **Step 4: Commit** `refactor: remove Keycloak and OIDC code and tests`.

### Task 12: Sécurité, documentation, vérification finale

**Files:**
- Modify: `docs/securite/asvs-l2.md` (V2/V3 rejoués sur la nouvelle authentification), `docs/exploitation/{runbook,mise-en-production,deploy}.md`, `docs/manuels/*`, `docs/formation/*`, `docs/recette/scenarios-de-test.md`, `CLAUDE.md` (stack : Auth = sessions Django), `docs/PRET-A-LIVRER.md`, `docs/HANDOFF.md`
- Test: scénarios de recette ajoutés (énumération, force brute, rejeu d'OTP, élévation d'un délégué)

- [ ] **Step 1:** lancer `ecc:security-reviewer` sur `apps/users/auth_*` et corriger les constats critiques et élevés.
- [ ] **Step 2:** mettre à jour les documents ci-dessus.
- [ ] **Step 3: Run** suites complètes back et front (une seule fois, mémoire : front seul puis back seul), `tsc`, `eslint`, `ruff`, `mypy`, `scripts/check-api-fresh.sh`, `docker compose config -q`, `npm run budget` (dépassement préexistant noté).
- [ ] **Step 4:** parcours manuel sur le site de test (création, première connexion, oubli, OTP, délégation).
- [ ] **Step 5: Commit** `docs: authentication, security review and delivery checklist`.
