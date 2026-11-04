# Authentification interne : modèle de sécurité

Note de conception pour la relecture de sécurité. Elle décrit l'authentification qui remplace
Keycloak (conception : `docs/superpowers/specs/2026-11-03-authentification-interne-design.md`),
ce que chaque contrôle protège, et où il se trouve dans le code. Elle **ne remplace pas** la
revue ASVS niveau 2 (`docs/securite/asvs-l2.md`), qui doit être rejouée sur cette authentification
(chapitres V2, V3, V4 notamment) : les constats de ce fichier-là datent de l'ancienne version.

Statut : rédigée d'après le code de la branche `feat/auth-interne` ; **rien ici n'a été testé
par un tiers**. La revue de sécurité statique de l'authentification est conduite séparément.

## 1. Périmètre et hypothèses

- Un seul navigateur client (la SPA React), servie sous la **même origine** que l'API par `nginx`
  (`docker/nginx/prod.conf`) : pas de CORS avec identifiants, pas de jeton Bearer (un en-tête
  `Authorization: Bearer` n'authentifie rien).
- Les comptes sont créés par un administrateur (ou un délégué) ; pas d'inscription libre, pas de
  fédération d'identité, pas de WebAuthn (évolution possible).
- Le relais SMTP de l'ONEA n'est pas encore fourni : tout le flux doit rester utilisable sans
  courriel (repli par un administrateur).
- Le réseau interne (`web`, `db`, `redis`) n'est pas exposé ; `nginx` est le seul pair de confiance
  pour l'adresse du client (`TRUSTED_PROXY_CIDRS`).

## 2. Actifs et menaces

| Actif | Menace | Contrôle principal (section 3) |
|---|---|---|
| Mots de passe | vol de base, rejeu, devinette | C1, C2, C3 |
| Comptes (existence, état) | énumération par la connexion ou « mot de passe oublié » | C4 |
| Sessions | vol de cookie, fixation, session trop longue, session d'un compte retiré | C5, C6, C7 |
| Codes à usage unique | rejeu, force brute, accumulation | C8 |
| Mots de passe temporaires | fuite par journal, historique ou réponse API, réutilisation | C9, C10 |
| Droits de gestion des comptes | élévation de privilèges d'un délégué, appropriation d'un compte d'administrateur | C11 |
| Piste d'audit | action de compte non tracée, secret dans l'audit | C12 |
| Disponibilité | verrouillage volontaire d'un compte, saturation de l'envoi de courriels | C4, C13 |

## 3. Contrôles : ce qui protège contre quoi

| Id | Contrôle | Protège contre | Où |
|---|---|---|---|
| C1 | Hachage Argon2id (`argon2-cffi`), `PBKDF2` conservé seulement pour relire d'éventuelles anciennes empreintes ; politique : 12 caractères, mots courants, similarité, numérique seul | vol de base, devinette | `config/settings/base.py` (`PASSWORD_HASHERS`, `AUTH_PASSWORD_VALIDATORS`) |
| C2 | Mot de passe jamais stocké ni journalisé en clair ; mot de passe temporaire renvoyé une seule fois et jamais écrit dans l'audit ni les journaux ; réponses concernées en `Cache-Control: no-store` | fuite par journal, cache, historique | `apps/users/services.py` (`_poser_mot_de_passe_temporaire`), `account_views.py` (`_reponse_mot_de_passe`) |
| C3 | Changement de mot de passe : mot de passe actuel exigé, nouveau différent, toutes les autres sessions fermées ; réinitialisation (code ou administrateur) ferme toutes les sessions | vol de session après compromission, rejeu | `auth_services.py` (`changer_mot_de_passe`, `reinitialiser_mot_de_passe`, `terminer_sessions`) |
| C4 | Réponse de connexion **uniforme** (compte inconnu, mot de passe faux, verrouillé, désactivé, mot de passe temporaire expiré) ; chaque refus coûte un hachage (pas d'oracle de temps) ; « mot de passe oublié » répond pareil, le traitement (hachage, SMTP) étant mis en file ; verrouillage 15 min après 5 échecs consécutifs ; limites par adresse (`connexion`) et par identifiant saisi (`mot_de_passe_oublie`) | énumération de comptes, force brute | `auth_services.py` (`authentifier`, `_conclure`, `_verifier_mot_de_passe`), `auth_views.py`, `auth_throttles.py`, `tasks.py` (`envoyer_code_reinitialisation`) |
| C5 | Session Django en base, cookie `HttpOnly`, `SameSite=Lax`, `Secure` et préfixe `__Host-` en production ; CSRF sur toute écriture, jeton lu par `GET /api/v1/auth/csrf/` ; la session est renouvelée à la connexion | vol de cookie, CSRF, fixation | `config/settings/base.py`, `prod.py`, `auth_views.py`, `authentication.py` (`SessionAuthentication401`) |
| C6 | Durée de session : 8 h au plus (absolue) et 30 min d'inactivité ; une session non ouverte par l'endpoint de connexion est refusée par l'API | session oubliée, session forgée | `apps/core/middleware.py` (`SessionLimiteeMiddleware`), `authentication.py` |
| C7 | État du compte relu en base à chaque requête : désactivation, rôle et délégation prennent effet à la requête suivante ; désactivation = sessions fermées, connexion et réinitialisation refusées | compte retiré qui garde l'accès | `authentication.py`, `delegation.py`, `services.py` |
| C8 | Code à usage unique : 6 chiffres, haché, 10 min, 5 essais, usage unique, un seul code actif par compte et par objet (réinitialisation / connexion) ; plafond de 10 codes de réinitialisation par compte et par 24 h ; purge à 24 h ; OTP de connexion activable **uniquement par le titulaire** et seulement si l'envoi de courriels est configuré | rejeu, force brute du code, abus d'envoi | `auth_services.py` (`emettre_otp`, `verifier_otp`, `quota_codes_reinitialisation`, `activer_otp_connexion`), `tasks.py` (`purger_codes`) |
| C9 | Changement de mot de passe obligatoire à la première connexion et après réinitialisation : l'API répond 403 à tout sauf aux endpoints d'authentification tant que ce n'est pas fait ; mot de passe temporaire valable 72 h | usage prolongé d'un secret partagé | `apps/core/middleware.py` (`MotDePasseAChangerMiddleware`), `auth_services.py` (`compte_utilisable`) |
| C10 | Fichier des mots de passe d'un import : chiffré (Fernet, clé dérivée de `SECRET_KEY`), lisible par l'importateur seul, détruit au premier téléchargement et au plus tard à 24 h ; réponse `no-store` | fuite d'une liste de mots de passe | `provisioning.py` (`lire_fichier_mots_de_passe`, `purger_fichiers_mots_de_passe`), `account_views.py` (`import_passwords`) |
| C11 | Délégation : quatre droits (créer, réinitialiser, rôles, désactiver) accordés par un administrateur seul ; un délégué n'agit jamais sur un administrateur, un compte `is_staff`/`is_superuser`, un autre délégué ni lui-même, ne donne pas le rôle Administrateur, ne délègue pas ; droits relus en base, rien en cache ; les services répètent les contrôles sous verrou de ligne ; l'import CSV ne crée jamais d'ADMIN | élévation de privilèges, prise de contrôle d'un compte d'administrateur | `delegation.py`, `account_permissions.py`, `services.py`, `provisioning.py` |
| C12 | Piste d'audit de toute action de compte (création, réinitialisation, rôle, désactivation, délégation, OTP, amorçage) avec l'acteur ; journal de sécurité séparé (échecs, verrouillages) sans mot de passe ni code ; le `correlation_id` relie les lignes | non-répudiation, enquête | `apps/core/audit.py`, `auth_services.py` (`logger_securite`), commandes `creer_administrateur`, `donner_mots_de_passe_temporaires` |
| C13 | Limites de débit : `THROTTLE_RATE_CONNEXION`, `THROTTLE_RATE_MOT_DE_PASSE_OUBLIE`, `THROTTLE_RATE_GESTION_COMPTES` (créations, réinitialisations, désactivation d'OTP, qui envoient des courriels) ; limite `nginx` 50 requêtes/s par adresse sur `/api/` | saturation, envoi en masse | `config/settings/base.py`, `auth_throttles.py`, `docker/nginx/prod.conf` |
| C14 | Amorçage et reprise sans interface : `creer_administrateur` (refuse un compte non ADMIN, un compte désactivé, un identifiant ambigu), `donner_mots_de_passe_temporaires` (ignore les comptes staff), `creer_comptes_e2e` (refuse hors `DEBUG`, hors base `onea_e2e_*`, hors hôte local) | blocage de l'exploitation, commande de test détournée en production | `apps/users/management/commands/` |

## 4. Risques résiduels et décisions à connaître

- **Verrouillage volontaire** : quelqu'un qui connaît un identifiant peut le verrouiller 15 minutes
  en répétant les échecs. C'est le compromis retenu (pas de verrouillage par adresse seule) ; la
  limite par adresse et l'audit permettent de le détecter ; un administrateur déverrouille par
  réinitialisation.
- **Délégué et comptes non administrateurs** : avec « créer des comptes » ou « réinitialiser les
  mots de passe », un délégué reçoit des mots de passe temporaires et peut donc prendre la main
  sur un compte non administrateur (RAI, auditeur, audité, DG). Décision de conception, signalée
  dans l'écran de délégation et dans le manuel de l'administrateur.
- **Second facteur** : facultatif, par courriel, activable par le titulaire seul. Il n'est pas
  obligatoire pour les comptes à privilèges (ancienne décision D19 : à reprendre avec l'ONEA).
  L'OTP par courriel dépend du relais SMTP et du compte de courriel de l'agent.
- **SMTP absent** : pas de « mot de passe oublié » automatique ; repli par un administrateur ou un
  délégué ; un administrateur bloqué par son OTP est récupéré par
  `creer_administrateur --desactiver-otp`.
- **Sessions en base** : les données de session sont signées par `SECRET_KEY` ; une rotation de la clé
  sans conserver l'ancienne dans `secret_key_fallbacks` ferme les sessions et rend illisibles les
  fichiers de mots de passe d'import encore présents (24 h au plus). Procédure : `docs/deploy.md` §3.3.
- **Accès à la base** : les empreintes de mots de passe, les sessions et le journal d'audit sont
  dans la base applicative et ses sauvegardes : protéger les sauvegardes comme la base.
- **Admin Django** (`/admin/`) : désactivé en production sauf `DJANGO_ADMIN_ENABLED=true` ; sa
  connexion passe par les mêmes contrôles que l'API (verrouillage, expiration, pas de contournement
  de l'OTP : `apps/users/admin_login.py`).

## 5. Ce qui reste à vérifier

- Rejeu de l'audit ASVS niveau 2 sur cette authentification (suite de la revue).
- Scénarios S4-29 à S4-37 de `docs/recette/scenarios-de-test.md`, exécutés sur une recette.
- Essai réel avec le relais SMTP de l'ONEA (délais, SPF/DKIM, boîtes d'arrivée).
- Choix éventuel des rôles soumis à un second facteur obligatoire.
