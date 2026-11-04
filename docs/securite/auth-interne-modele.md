# Authentification interne : modèle de sécurité

Note de conception pour la relecture de sécurité. Elle décrit l'authentification qui remplace
Keycloak (conception : `docs/superpowers/specs/2026-11-03-authentification-interne-design.md`),
ce que chaque contrôle protège, et où il se trouve dans le code. La correspondance avec l'ASVS
niveau 2 est dans `docs/securite/asvs-l2.md` (rejouée le 2026-11-04 sur cette authentification).

Statut (2026-11-04) : rédigée d'après le code de la branche `feat/auth-interne`, puis mise à jour
après la revue de sécurité statique de l'authentification (constats AUTH-01 à AUTH-20) et ses
corrections (commits `39163e0` à `ccd12f8`), puis après le second tour de corrections (re-revue N1 à N9, commit `7f6b9dc`) le troisième (D1 à D4, commit `2fbaad9`) et le quatrième (plafond de tous les refus, hachages factices hors verrou, réinitialisation uniforme par identifiant, commit `4eabb55`). Les corrections ont été **relues**, et leurs tests
lancés par le développeur sur une sélection (`tests/users` complet et fichiers ciblés) ; leur
comportement **n'a pas été vérifié sur une pile en fonctionnement** (envoi réel par le `worker`,
réponses 429 derrière un NAT, navigateur).

## 1. Périmètre et hypothèses

- Un seul navigateur client (la SPA React), servie sous la **même origine** que l'API par `nginx`
  (`docker/nginx/prod.conf`) : pas de CORS, pas de jeton Bearer (un en-tête
  `Authorization: Bearer` n'authentifie rien).
- Les comptes sont créés par un administrateur (ou un délégué, pour les rôles AUDITEUR et AUDITE
  seulement) ; pas d'inscription libre, pas de fédération d'identité, pas de WebAuthn (évolution
  possible).
- Le relais SMTP de l'ONEA n'est pas encore fourni : tout le flux doit rester utilisable sans
  courriel (repli par un administrateur, mode `EMAIL_URL=dummymail://`).
- Le réseau interne (`web`, `backend`) n'est pas exposé ; `nginx` est le seul pair de confiance
  pour l'adresse du client (`TRUSTED_PROXY_CIDRS`). `web` n'a **aucune sortie** : seuls les
  conteneurs `worker-auth` et `worker` (réseau `mail-out`, secret `email_password`) joignent le relais SMTP.

## 2. Actifs et menaces

| Actif | Menace | Contrôle principal (section 3) |
|---|---|---|
| Mots de passe | vol de base, rejeu, devinette | C1, C2, C3 |
| Comptes (existence, état) | énumération par la connexion ou « mot de passe oublié » | C4 |
| Sessions | vol de cookie, fixation, session trop longue, session d'un compte retiré | C5, C6, C7 |
| Codes à usage unique | rejeu, force brute (y compris répartie sur plusieurs codes et plusieurs adresses), accumulation | C8, C15 |
| Mots de passe temporaires | fuite par journal, historique, réponse API ou file de messages ; réutilisation | C9, C10, C16 |
| Droits de gestion des comptes | élévation de privilèges d'un délégué, appropriation d'un compte d'administrateur, de RAI ou de DG | C11 |
| Piste d'audit | action de compte non tracée, secret dans l'audit | C12 |
| Disponibilité | verrouillage volontaire de comptes en masse, quota partagé derrière un NAT, saturation de l'envoi de courriels, coût du hachage | C4, C13, C15 |

## 3. Contrôles : ce qui protège contre quoi

Chemins relatifs à `backend/apps/users/` sauf mention contraire.

| Id | Contrôle | Protège contre | Où |
|---|---|---|---|
| C1 | Hachage Argon2id (`argon2-cffi`), `PBKDF2` conservé seulement pour relire d'éventuelles anciennes empreintes ; politique : 12 caractères, mots courants, similarité, numérique seul | vol de base, devinette | `config/settings/base.py` (`PASSWORD_HASHERS`, `AUTH_PASSWORD_VALIDATORS`) |
| C2 | Mot de passe jamais stocké ni journalisé en clair ; mot de passe temporaire renvoyé une seule fois (et seulement s'il n'a pas été mis en file d'envoi), jamais écrit dans l'audit ni les journaux ; réponses concernées en `Cache-Control: no-store` ; la production refuse les backends courriel console, fichier et mémoire (AUTH-07) | fuite par journal, cache, historique | `services.py` (`_poser_mot_de_passe_temporaire`, `creer_compte`, `reinitialiser_mot_de_passe`), `account_views.py` (`_reponse_mot_de_passe`), `config/settings/prod.py` |
| C3 | Changement de mot de passe : mot de passe actuel exigé, nouveau différent, toutes les autres sessions fermées ; réinitialisation (code ou administrateur) ferme toutes les sessions | vol de session après compromission, rejeu | `auth_services.py` (`changer_mot_de_passe`, `reinitialiser_mot_de_passe`, `terminer_sessions`) |
| C4 | Réponse de connexion **uniforme** (compte inconnu, mot de passe faux, verrouillé, désactivé, mot de passe temporaire expiré) ; chaque refus coûte un hachage (pas d'oracle de temps) ; « mot de passe oublié » répond toujours 202 avec le même texte, le traitement (hachage, envoi) étant fait par le `worker` ; verrouillage 15 min après 5 échecs consécutifs | énumération de comptes, force brute | `auth_services.py` (`authentifier`, `_conclure`, `_verifier_mot_de_passe`), `auth_views.py`, `tasks.py` (`envoyer_code_reinitialisation`) |
| C5 | Session Django en base, cookie `HttpOnly`, `SameSite=Lax`, `Secure` et préfixe `__Host-` en production ; CSRF sur toute écriture, y compris anonyme, **vérifié avant les limites de débit** (AUTH-05) ; jeton lu par `GET /api/v1/auth/csrf/` ; la session est renouvelée à la connexion | vol de cookie, CSRF, fixation, épuisement du quota d'un site par une page tierce | `config/settings/base.py`, `prod.py`, `auth_views.py` (`_CsrfObligatoireMixin`), `authentication.py` (`SessionAuthentication401`) |
| C6 | Durée de session : 8 h au plus (absolue) et 30 min d'inactivité ; une requête d'arrière-plan portant `X-Onea-Arriere-Plan: 1` (rafraîchissement automatique) ne compte pas comme activité (AUTH-08) ; une session non ouverte par l'endpoint de connexion est refusée par l'API | session oubliée, poste laissé ouvert, session forgée | `apps/core/middleware.py` (`SessionLimiteeMiddleware`), `authentication.py` |
| C7 | État du compte relu en base à chaque requête : désactivation, rôle et délégation prennent effet à la requête suivante ; désactivation = sessions fermées, connexion et réinitialisation refusées | compte retiré qui garde l'accès | `authentication.py`, `delegation.py`, `services.py` |
| C8 | Code à usage unique : 6 chiffres, haché, 10 min, 5 essais, usage unique, un seul code actif par compte et par objet (réinitialisation / connexion) ; purge à 24 h ; OTP de connexion activable **uniquement par le titulaire** et seulement si l'envoi de courriels est configuré | rejeu, force brute d'un code | `auth_services.py` (`emettre_otp`, `verifier_otp`, `activer_otp_connexion`), `tasks.py` (`purger_codes`) |
| C9 | Changement de mot de passe obligatoire à la première connexion et après réinitialisation : l'API répond 403 à tout sauf aux endpoints d'authentification tant que ce n'est pas fait ; mot de passe temporaire valable 72 h | usage prolongé d'un secret partagé | `apps/core/middleware.py` (`MotDePasseAChangerMiddleware`), `auth_services.py` (`compte_utilisable`) |
| C10 | Fichier des mots de passe d'un import (seulement ceux qui n'ont pas été mis en file d'envoi) : chiffré (Fernet, clé dérivée de `SECRET_KEY`), lisible par l'importateur seul, détruit au premier téléchargement et au plus tard à 24 h ; réponse `no-store` | fuite d'une liste de mots de passe | `provisioning.py` (`lire_fichier_mots_de_passe`, `purger_fichiers_mots_de_passe`), `account_views.py` (`import_passwords`) |
| C11 | Délégation : quatre droits (créer, réinitialiser, rôles, désactiver) accordés par un administrateur seul ; un délégué n'agit que sur des comptes **AUDITEUR et AUDITE** : jamais sur un administrateur, un RAI, un DG (AUTH-03), un compte `is_staff`/`is_superuser`, un autre délégué ni lui-même ; il n'attribue que les rôles AUDITEUR et AUDITE ; il ne délègue pas et n'importe pas ; droits relus en base, rien en cache ; les services répètent les contrôles sous verrou de ligne ; l'import CSV ne crée jamais d'ADMIN | élévation de privilèges, prise de contrôle d'un compte d'administrateur, de RAI ou de DG (validations et signatures) | `delegation.py` (`ROLES_RESERVES_ADMIN`, `_cible_protegee`, `exiger_attribution_role`), `account_permissions.py`, `services.py`, `provisioning.py` |
| C12 | Piste d'audit de toute action de compte (création, réinitialisation, rôle, désactivation, délégation, OTP, amorçage, et les actions du titulaire : changement de mot de passe volontaire ou imposé, réinitialisation par code, activation et désactivation du code de connexion) avec l'acteur et l'action nommée (`additional_data.action`, exposée par l'API du journal dans `action_metier`) ; une entrée est écrite même quand aucun champ suivi ne change (le mot de passe n'est jamais suivi) ; journal de sécurité séparé (`onea.securite` : échecs, verrouillages, blocage de la réinitialisation, plafonds par adresse, échec d'envoi d'un mot de passe temporaire) sans mot de passe ni code ; les compteurs de limites sont exclus de l'audit ; le `correlation_id` relie les lignes, y compris celles du `worker` | non-répudiation, enquête | `apps/core/audit.py`, `apps.py` (`exclude_fields`), `auth_services.py` (`logger_securite`), `envois.py`, commandes `creer_administrateur`, `donner_mots_de_passe_temporaires` |
| C13 | Limites de débit **par point d'entrée**, par adresse client (IPv6 regroupée par /64, AUTH-12) : connexion 60/min, code de connexion 30/min, demande de code 20/min, réinitialisation 20/min ; par identifiant saisi : 5 demandes de code par heure ; par utilisateur : changement de mot de passe et retrait du code de connexion 10/min, gestion des comptes 30/h ; `/admin/login/` soumis aux limites de la connexion (AUTH-06) ; `nginx` 50 requêtes/s par adresse sur `/api/` | saturation, envoi en masse, quota partagé derrière un NAT | `config/settings/base.py` (`DEFAULT_THROTTLE_RATES`), `auth_throttles.py`, `admin_login.py`, `docker/nginx/prod.conf` |
| C14 | Amorçage et reprise sans interface : `creer_administrateur` (refuse un compte non ADMIN, un compte désactivé, un identifiant ambigu), `donner_mots_de_passe_temporaires` (ignore les comptes staff), `creer_comptes_e2e` (refuse hors `DEBUG`, hors base `onea_e2e_*`, hors hôte local) ; `/admin/password_change/` fermé (404, AUTH-09) ; identifiants ASCII imposés aux nouveaux comptes (AUTH-11) | blocage de l'exploitation, commande de test détournée en production, comptes sosies | `apps/users/management/commands/`, `config/urls.py`, `account_serializers.py`, `provisioning.py` |
| C15 | Plafonds d'échecs **en base, par compte** : 15 codes de réinitialisation faux par 24 h (`AUTH_REINITIALISATION_ECHECS_MAX`), puis plus aucun code émis ni accepté jusqu'à la fin de la fenêtre (refus identique, journal `ERROR`) ; 10 codes émis par compte et par 24 h (échec fermé si le cache tombe) (AUTH-02). Plafonds d'**échecs par adresse**, tous comptes confondus, vérifiés avant tout hachage : 30 mots de passe ou codes de connexion faux (ou comptes inconnus) par 15 min (`echecs_connexion`), 30 réinitialisations refusées par heure (`echecs_reinitialisation`) (AUTH-04). Depuis le troisième tour (D1), un refus compte **selon sa nature, jamais selon que le secret était juste** (`Resultat.comptage`, jamais envoyé au client) : mauvais secret sur un compte utilisable, chaque refus ; compte inutilisable (verrouillé, désactivé, mot de passe temporaire expiré, réinitialisation bloquée), **une seule fois par adresse, compte et fenêtre**, bon ou mauvais secret (clé HMAC) ; identifiant inconnu, chaque refus, au plus 5 par adresse, identifiant et fenêtre ; code remplacé, rien ; sur la réinitialisation, depuis le quatrième tour, **tout refus** compte au plus 5 fois par adresse, identifiant saisi et fenêtre (inconnu, existant, désactivé ou bloqué : même effet). Un plafond plus large, `echecs_tous` (120 par 15 min), compte **tous les refus** de toute nature, quel que soit le secret, et borne le hachage non authentifié par adresse ; les hachages factices d'égalisation (4 par refus de code) s'exécutent hors de la transaction qui verrouille la ligne du compte ; les compteurs sont atomiques (10 tranches `cache.incr`, N4). Au plus `AUTH_CODES_CONNEXION_MAX` (10) codes de connexion envoyés par compte et par 15 min, compteur en base sous verrou de ligne (N6) ; un code remplacé par un plus récent est marqué (`remplace_le`), refusé sans compter comme échec | devinette répartie des codes à 6 chiffres, verrouillage en masse depuis une adresse | `auth_services.py` (`quota_codes_reinitialisation`, `reinitialisation_bloquee`, `_compter_echec_reinitialisation`), `models.py`, `auth_throttles.py` (`_EchecsParIp`) |
| C16 | Tous les courriels d'authentification partent de **`worker-auth`** (AUTH-01, N2) : `web` met une tâche en file (file Celery dédiée `auth`, Redis), sans secret dans le message, pour qu'un code de connexion (10 min) n'attende pas derrière une conversion de document ; le `worker` principal (`-Q celery,auth`) sert `auth` en secours ; le code (connexion, réinitialisation) est émis par la tâche ; le mot de passe temporaire attend chiffré (Fernet) dans `EnvoiMotDePasse` au plus 1 h, lu une fois puis supprimé, et n'est envoyé que s'il est encore le mot de passe du compte | second facteur inutilisable en production, mot de passe dans la file de messages, envoi d'un mot de passe périmé | `envois.py`, `tasks.py` (`envoyer_code_connexion`, `envoyer_code_reinitialisation`, `envoyer_mot_de_passe_temporaire`), `auth_views.py`, `config/settings/base.py` (`CELERY_TASK_ROUTES`), `docker/compose.prod.yml` (`worker-auth`) |

## 4. Risques résiduels et décisions à connaître

- **Codes à 6 chiffres face à un botnet** : les plafonds par adresse ne gênent pas un attaquant
  réparti sur de nombreuses adresses ; c'est alors le plafond par compte (15 codes faux par 24 h)
  qui borne la devinette, soit environ 1,5 × 10⁻⁵ de chance par compte et par jour. Passer à
  8 chiffres diviserait ce taux par 100 : décision produit (spécification, interface, courriel).
- **Plafond d'échecs partagé derrière un NAT** : tous les agents qui sortent par une même adresse
  publique partagent le plafond de 30 échecs par 15 minutes (un compte verrouillé ou désactivé n'y coûte qu'une unité par adresse et fenêtre, quel que soit le nombre de ressaisies : les propriétaires de comptes verrouillés ne l'épuisent pas, et le compteur ne révèle pas si le mot de passe essayé était le bon). Un initié malveillant (ou beaucoup
  de fautes de frappe un lundi matin) peut bloquer les connexions **de cette adresse** jusqu'à
  15 minutes (réponse 429), sans verrouiller de compte ni gêner les autres adresses. Réglable par
  `THROTTLE_RATE_ECHECS_CONNEXION` (par exemple `60/15min`). Sans effet si les postes arrivent
  au serveur avec leur propre adresse (déploiement sur site).
- **Risque résiduel de la file `auth`** : le `worker` principal peut réserver un message `auth` (un par
  processus) pendant une longue conversion ; `worker-auth` le prend normalement avant lui. Retirer `auth`
  du `worker` supprimerait ce risque mais aussi le secours. Les fenêtres des compteurs restent fixes
  (N7, accepté).
- **Risques acceptés à la clôture (quatrième tour, aucune autre passe prévue)** :
  - le compteur d'échecs de **connexion** distingue encore un compte inutilisable (une unité par adresse et fenêtre) d'un identifiant inconnu (jusqu'à 5) : indice d'existence d'un compte verrouillé ou désactivé, sans révéler de mot de passe ; la réinitialisation, elle, est rendue uniforme ;
  - un code de connexion faux coûte 4 hachages Argon2 (égalisation D2), accessible seulement à qui connaît déjà le mot de passe, et borné par les plafonds ;
  - `echecs_tous` (120 refus par 15 min et par adresse) laisse encore environ 8 hachages par minute et par adresse, voire 32 pour des refus de code ; un attaquant réparti sur de nombreuses adresses n'est borné que par les limites de débit globales de nginx ;
  - les compteurs par adresse restent en cache (voir ci-dessous) et à fenêtres fixes (N7).
- **Limites par adresse en cache** : si le cache (Redis) tombe, ces limites laissent passer, avec
  un avertissement ; le verrouillage des comptes, le quota d'émission et le plafond de codes faux,
  en base, restent appliqués.
- **Verrouillage volontaire** : quelqu'un qui connaît un identifiant peut toujours le verrouiller
  15 minutes ; depuis une seule adresse, il ne peut plus en verrouiller qu'une poignée (plafond
  d'échecs par adresse) ; un administrateur déverrouille par réinitialisation.
- **Délégués** : ils ne gèrent que les comptes AUDITEUR et AUDITE (AUTH-03). Avec « créer des
  comptes » ou « réinitialiser les mots de passe », un délégué peut encore choisir de ne pas
  envoyer le courriel et voir le mot de passe temporaire : il peut donc prendre la main sur un
  compte AUDITEUR ou AUDITE. Décision de conception, signalée dans l'écran de délégation et dans
  le manuel de l'administrateur.
- **Échec d'envoi par le `worker`** : `web` ne peut savoir que si le courriel a été **mis en
  file**. Si le `worker` échoue ensuite (relais injoignable, adresse refusée), le mot de passe
  temporaire de ce courriel est perdu : une ligne `ERROR` « Mot de passe temporaire perdu
  (<raison>) : compte=<id> envoi=<id>. Réinitialisez le mot de passe avec affichage. » est écrite dans
  `onea.securite` (sept raisons : file indisponible, identifiant invalide, en attente introuvable, expiré
  avant l'envoi, compte désactivé, illisible après un changement de `SECRET_KEY`, envoi SMTP en échec ;
  jamais le mot de passe), et l'administrateur refait une réinitialisation, envoi décoché. **Cette
  ligne est celle que l'exploitant doit surveiller.** Dans une transaction de l'appelant, la mise en
  file est différée à la validation (`transaction.on_commit`) : l'écran répond « mis en file » aussitôt. Pas de nouvel essai automatique
  (un mot de passe n'est jamais envoyé deux fois). Un `worker` arrêté plus d'une heure laisse
  expirer les envois en attente (purge quotidienne). Pour un import, une panne du relais impose
  une réinitialisation par compte.
- **Second facteur** : facultatif, par courriel, activable par le titulaire seul ; il n'est
  obligatoire pour aucun rôle, y compris ADMIN (ancienne décision D19 : à reprendre avec l'ONEA ;
  ASVS 4.3.1 non conforme tant qu'elle n'est pas prise). L'OTP par courriel dépend du relais SMTP,
  du `worker` et du compte de courriel de l'agent.
- **Notifications au titulaire non envoyées (AUTH-10, arbitrage)** : aucune alerte par courriel
  après une réinitialisation par un administrateur, un changement d'adresse ou la désactivation du
  code ; à décider (modèles, destinataires dont l'ancienne adresse).
- **Liste de mots de passe interdits (AUTH-13, arbitrage)** : seule la liste de Django (environ
  20 000 mots de passe courants) est utilisée ; un corpus hors ligne de mots de passe compromis
  est à choisir (taille, licence, mise à jour).
- **Délai d'inactivité de l'admin Django non appliqué (AUTH-09)** : si `DJANGO_ADMIN_ENABLED=true`,
  une session ouverte par `/admin/login/` n'a pas de délai d'inactivité de 30 minutes (elle expire
  8 h après sa dernière modification) ; `/admin/password_change/` est fermé. L'admin est désactivé
  par défaut en production.
- **Unicité insensible à la casse non garantie en base (AUTH-11)** : les services refusent un
  identifiant ou une adresse déjà pris (comparaison sans casse), mais aucune contrainte de base
  ne l'impose ; deux créations simultanées `jdoe` / `JDoe` peuvent passer. Effet : déni de service
  sur la connexion (l'identifiant est reconnu sans casse, comme l'adresse ; un identifiant ou une
  adresse qui correspond à plusieurs comptes est refusé comme un identifiant inconnu et le
  journal de sécurité nomme les comptes à renommer), pas de prise de contrôle. Les contraintes
  demandent d'abord un contrôle des doublons existants.
- **Rafraîchissement en arrière-plan (AUTH-08)** : le frontend envoie l'en-tête
  `X-Onea-Arriere-Plan: 1` sur ses interrogations automatiques (compteur de la cloche, suivi de
  l'état des documents : `apiFetch(..., { background: true })`, commit `8addfca`). Toute nouvelle
  interrogation automatique doit faire de même ; sinon un onglet laissé ouvert garde la session
  jusqu'à 8 h.
- **TLS vers le relais SMTP non exigé (AUTH-18)** : `smtp://` reste accepté pour un relais
  interne ; codes et mots de passe temporaires passeraient alors en clair sur le réseau.
- **Sessions en base** : les données de session sont signées par `SECRET_KEY` ; une rotation de la
  clé sans conserver l'ancienne dans `secret_key_fallbacks` ferme les sessions et rend illisibles
  les fichiers de mots de passe d'import et les envois en attente (24 h et 1 h au plus).
  Procédure : `docs/deploy.md` §3.3.
- **Accès à la base** : les empreintes de mots de passe, les sessions et le journal d'audit sont
  dans la base applicative et ses sauvegardes : protéger les sauvegardes comme la base.
- **Admin Django** (`/admin/`) : désactivé en production sauf `DJANGO_ADMIN_ENABLED=true` ; sa
  connexion passe par les mêmes contrôles et les mêmes limites que l'API (verrouillage,
  expiration, pas de contournement de l'OTP : `apps/users/admin_login.py`).

## 5. Ce qui reste à vérifier

- Scénarios S4-29 à S4-41 de `docs/recette/scenarios-de-test.md`, exécutés sur une recette (pile
  complète avec `worker`, Redis et Mailpit).
- Essai réel avec le relais SMTP de l'ONEA depuis le `worker` (délais, TLS, SPF/DKIM, boîtes
  d'arrivée).
- Analyse dynamique (ZAP) rejouée avec une session (`docs/securite/asvs-l2.md` §6).
- Choix éventuel des rôles soumis à un second facteur obligatoire, et des arbitrages AUTH-10 et
  AUTH-13.
