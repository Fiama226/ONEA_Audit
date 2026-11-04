# Passation — plateforme d'audit interne ONEA

Dernière mise à jour : **2026-11-04** (revue de sécurité de l'authentification et rejeu ASVS compris). Rien n'est poussé : tout est local (Git). Sources de vérité de cet
état : `git log --oneline` et `git branch --merged develop` (le texte précédent de ce fichier, daté du
2026-10-30, était périmé).

## 1. Règles du projet (voir `CLAUDE.md`)
- Interface et documents en **français** ; code et commits en anglais (Conventional Commits).
- **Aucune fonction IA/LLM dans le produit.** Logiciels **100 % open source** (liste des licences dans
  `CLAUDE.md`, décisions du 2026-11-02 incluses : MIT-0, PSF-2.0, ZPL-2.1, ClamAV en conteneur séparé).
- Stack : Django 5.2 + DRF (`backend/`), React 19 + TypeScript + Vite + Tailwind + shadcn (`frontend/`),
  PostgreSQL 16, Celery + Redis, docxtpl + Gotenberg, Meilisearch ; authentification interne (sessions Django,
  Argon2id, code à usage unique par courriel) : Keycloak a été retiré.
- Rôles : ADMIN, RAI, AUDITEUR, AUDITE, DG. Méthode IFACI en 18 étapes ; matrice des risques 5×5.

## 2. Ce qui est fait (dans `develop`)
`develop` (88da06b) contient, d'après `git branch --merged develop` :
- Lots 1 à 5 (socle, référentiel, missions, documents, analyse), lot utilisateurs, programme annuel
  (dont export PDF au modèle du client).
- Lots 6 (accomplissement, T1 à T13), 7 (communication et signatures, T1 à T16, plus PAdES : branche
  `feat/lot7-pades` fusionnée) et 8 (suivi, notifications, tableaux de bord, recherche, T1 à T16).
- Lot 9 fusionné : T1 à T21 (T13 inclus, via `journalisation.py`), T23, T26 à T29, T31, correctifs T9/T12, SEC-02 et SEC-04.
- Correctifs de recette : QA admin, cycle, limites, design/accessibilité ; logo officiel ; parcours guidé
  (tutoriel, état mémorisé par utilisateur) ; fonction du signataire sur l'ordre de mission ; destinataires
  internes de diffusion ; responsable d'entité sur les affectations d'audités.
- Documentation : manuels par rôle (`docs/manuels/`), scénarios de test et rapports QA (`docs/recette/`),
  runbook et checklist de mise en production (`docs/exploitation/`), revue ASVS niveau 2
  (`docs/securite/asvs-l2.md`), kit de formation (`docs/formation/`, branche `docs/finish-t35`).
- La branche `preview` (160bbd0) a un commit de retard sur `develop` (export PDF du programme).
- Versions affichées : encore `0.6.0` (backend, frontend) ; `0.9.0` est posée par la tâche T36.

### 2bis. Authentification interne (branche `feat/auth-interne`, **non fusionnée dans `develop`**)
Keycloak est remplacé par une authentification dans l'application : sessions Django (8 h au plus, 30 min
d'inactivité), mots de passe Argon2id, comptes créés par l'administrateur avec mot de passe temporaire (72 h,
changement obligatoire), « mot de passe oublié » par code envoyé par courriel, code de connexion par courriel
facultatif (activé par le titulaire seul), délégation de la gestion des comptes (créer, réinitialiser, rôles,
désactiver), import CSV avec fichier des mots de passe à téléchargement unique. Conception :
`docs/superpowers/specs/2026-11-03-authentification-interne-design.md` ; modèle de sécurité :
`docs/securite/auth-interne-modele.md` ; procédures : `docs/deploy.md` §5, `docs/exploitation/runbook.md`.
Le conteneur, la base, le thème, les secrets et les variables Keycloak/OIDC/SSO sont supprimés de la pile.
**Ce qui a été vérifié** (voir les comptes rendus de `.superpowers/sdd/2026-11-04-authentification-interne/`) : tests
du backend lancés **application par application** (le disque disponible ne permettait pas une exécution
unique de la suite complète), tests du frontend ciblés sur les dossiers touchés, `tsc`, `eslint`, `ruff`, `mypy`.
**Ce qui n'a pas été fait** : une suite complète back et front en une seule exécution, les specs Playwright
(`frontend/e2e/`, vérifiées au typage mais **non exécutées**), le parcours manuel sur le site de test, l'essai
avec un vrai relais SMTP.

**Revue de sécurité et corrections (2026-11-04)** : revue statique de l'authentification (constats AUTH-01 à
AUTH-20 : 3 élevés, 3 moyens, 7 faibles, 7 informations), corrections en commits `39163e0` à `ccd12f8`, relues
mais **non éprouvées sur une pile en fonctionnement**. Ce qui a changé : tous les courriels d'authentification
partent de `worker-auth` (file Celery `auth`, le `worker` principal la sert en secours ; le `web` met en file ; mot de passe temporaire chiffré en base 1 h, jamais dans Redis ;
« courriel envoyé » veut dire « mis en file ») ; un délégué ne gère plus que les comptes AUDITEUR et AUDITE ;
plafond de 15 codes de réinitialisation faux par compte et par 24 h et quota de 10 codes en base ; un compteur
par point d'entrée de l'authentification (connexion 60/min par adresse), plafonds d'échecs par adresse (30 par
15 min à la connexion, 30 par heure à la réinitialisation, ne comptant que les mauvais secrets et les comptes inconnus), CSRF vérifié avant les limites, IPv6 par /64,
`/admin/login/` sous les mêmes limites ; la production refuse les backends courriel console, fichier et mémoire
(`dummymail://` = sans courriel) ; en-tête `X-Onea-Arriere-Plan: 1` pour les requêtes d'arrière-plan ;
`/admin/password_change/` en 404 ; identifiants ASCII. Audit ASVS L2 **rejoué en statique** sur cette
authentification : `docs/securite/asvs-l2.md` (décompte et non-conformités restantes dans `docs/PRET-A-LIVRER.md`
B1 et B8). Suites du frontend : commit `8addfca` (rôles d'un délégué, en-tête d'arrière-plan, libellés, message
429). Second tour de re-revue (N1 à N9, commit `7f6b9dc`) : file `auth` et service `worker-auth` (tout worker lancé
à la main doit recevoir `-Q celery,auth`), plafond `AUTH_CODES_CONNEXION_MAX` (10 codes de connexion par compte
et 15 min), `AUTH_REINITIALISATION_ECHECS_MAX` et `AUTH_CODES_CONNEXION_MAX` transmis par la composition et validés,
code remplacé ne comptant pas comme échec, migration `users.0011`. **À surveiller en exploitation** : la ligne
`ERROR` « Mot de passe temporaire perdu (...) … Réinitialisez le mot de passe avec affichage. » (`onea.securite`).
Ces corrections sont relues statiquement, **non vérifiées sur une pile en fonctionnement**.
Restent ouverts : délai d'inactivité des sessions admin (AUTH-09), contraintes d'unicité insensibles à la casse (AUTH-11),
notifications au titulaire (AUTH-10) et liste de mots de passe compromis (AUTH-13) à arbitrer, TLS vers le
relais non exigé (AUTH-18), analyse dynamique (ZAP) à rejouer.

## 3. Décisions déjà prises (ne plus les redemander)
- Licences MIT-0, PSF-2.0 et ClamAV (conteneur séparé, GPL-2.0) autorisées : commit 6c982ec. ZPL-2.1 : 120ee1b.
- SEC-07 (confirmation horodatée en SHA-256 sans clé) : risque **accepté**, commit 52a5aba.
- Hypothèses métier des lots : toutes confirmées (2026-10-29) ; gabarits Word vierges provisoires acceptés.

## 4. Ce qui reste à faire (équipe projet)
0. **Authentification interne** : constats de sécurité encore ouverts (voir §2bis : AUTH-09, AUTH-11, AUTH-18 ; AUTH-10 et AUTH-13 à arbitrer), suites complètes, e2e Playwright à exécuter, parcours manuel sur
   le site de test (scénarios S4-29 à S4-41 : création, première connexion, oubli et plafond des codes, code de
   connexion, délégation et comptes RAI/DG, réponses 429, `worker-auth` arrêté, `worker` arrêté), analyse dynamique ZAP, puis fusion
   dans `develop` après accord (ni `develop` ni `preview` ne sont touchées à ce jour). À la mise à jour du site de test : donner un
   mot de passe temporaire aux comptes existants (`donner_mots_de_passe_temporaires`, `docs/deploy.md` §5.4).
1. **Lot 6 T14**, **lot 7 T17**, **lot 8 T17** : tests e2e Playwright (`frontend/e2e/` ne contient que
   connexion, référentiel, missions, accessibilité, clavier, impression), documentation de fin de lot.
2. **Lot 9** : T22 (revue
   visuelle), T24 et T25 (corrections d'interface), T30 (socle de documentation : entrée « Aide » du menu,
   PDF, captures), T32 à T34 (manuels : rédigés, **non rejoués**), T35 (kit de formation rédigé, **non
   rejoué**), T36 (vérification finale, version 0.9.0).
3. Suites complètes back et front, `sh scripts/check-api-fresh.sh`, e2e, recette depuis zéro : à relancer une
   seule fois à l'intégration (voir `docs/PRET-A-LIVRER.md`), puis avancer `main`.
4. Filtres de la file de décisions du RAI (reports en attente, relances en échec, sans adresse) : manque
   signalé au 2026-10-30, à revérifier.
5. Nettoyage : voir `docs/maintenance/nettoyage.md` (worktrees, branche orpheline, bases de test).

## 5. Décisions en attente de l'ONEA
| Sujet | Détail | Comportement par défaut |
|---|---|---|
| Sauvegarde hors serveur (U1) | destination (SFTP, NAS, disque chiffré, S3 interne) et détenteurs du mot de passe restic | sauvegardes locales seules ; `backup.sh --hors-serveur` refuse sans `RESTIC_REPOSITORY` |
| Hébergement, DNS, TLS (U2) | VPS ou site, **un seul nom** (application), autorité interne ou Let's Encrypt | recette avec AC jetable |
| SMTP (U3) | hôte, port, mode, compte, expéditeur, SPF/DKIM ; **désormais aussi nécessaire à l'authentification** (codes de connexion et « mot de passe oublié », courriel de bienvenue, tous envoyés par le `worker`) | la production refuse de démarrer sans `EMAIL_URL` ; en attendant le relais : `EMAIL_URL=dummymail://` (aucun courriel), et l'administrateur réinitialise les mots de passe avec affichage (`docs/deploy.md` §2.3 et §5.5) |
| Notifications de sécurité (AUTH-10) | courriel au titulaire après une réinitialisation par un administrateur, un changement d'adresse ou la désactivation de son code (et à l'ancienne adresse ?) | aucune notification |
| Mots de passe compromis (AUTH-13) | corpus hors ligne de mots de passe compromis (taille, licence, mise à jour) | liste de Django (environ 20 000 mots de passe courants) |
| Codes à 8 chiffres | passer les codes de 6 à 8 chiffres (résistance à un attaquant réparti) | 6 chiffres, plafond de 15 codes faux par compte et par 24 h |
| Réseau ONEA (U5) | proxy amont, réseau d'administration, supervision | aucun proxy |
| Formation (U6) | participants, dates, salle, postes | supports prêts, calendrier à fixer |
| 22 gabarits Word réels | `docs/documents/gabarits-manquants.md` | gabarits provisoires générés |
| Abréviations ONEA à confirmer | QPC, GST, QCI, MARC, FF, RO, PT, FCT, FDT, FIT, FO | libellés actuels conservés |
| Rôles OTP (D19) | quels comptes à privilèges devraient avoir le code de connexion par courriel obligatoire (aujourd'hui facultatif pour tous) | facultatif, activé par le titulaire (`docs/securite/auth-interne-modele.md`) |
| Libellé de la direction des participants | formulation sur l'ordre de mission | à trancher |
| Clôture de l'antivirus | réseau sortant vers `database.clamav.net` ou miroir local | contrôle des signatures d'octets seul si ClamAV non livré |

## 6. Lancer / tester en local
- Docker Desktop : conteneurs `onea-db-1`, `onea-redis-1` (et `mailpit`, http://127.0.0.1:8025, pour lire les codes
  envoyés par courriel). Plus de conteneur Keycloak. Les courriels d'authentification partent d'un worker Celery :
  sans `celery -A config worker -Q celery,auth` lancé (le `-Q celery,auth` est nécessaire : sans lui, le worker ne lit pas la file `auth`), aucun code ni courriel de bienvenue n'arrive dans Mailpit.
- API : `cd backend`, Python `C:\v\onea\Scripts\python.exe manage.py runserver 127.0.0.1:8000` avec
  `DATABASE_URL=postgres://onea:onea-dev-password@127.0.0.1:5432/onea`.
- Web : `cd frontend && npm run dev` (http://localhost:5173, utiliser `localhost`).
- Comptes de développement et de recette : `admin`, `rai`, `auditeur1`, `auditeur2`, `audite1`, `dg`. Il n'y a plus
  de mot de passe commun : `python manage.py creer_administrateur --identifiant admin --courriel admin@example.org`
  crée l'administrateur (mot de passe temporaire affiché une fois), et `donner_mots_de_passe_temporaires`
  en donne un aux comptes existants sans mot de passe ; chacun le change à sa première connexion. Jamais en
  production.
- Tests back : `unset DJANGO_SETTINGS_MODULE`, base dédiée (jamais `onea`), `pytest` ciblé. Tests front :
  `npx vitest run --maxWorkers=2 --testTimeout=30000`. Une suite complète prend 15 à 30 minutes.
- Données de démonstration : `python manage.py peupler_demo --profil formation --recette` sur base vide (comptes
  locaux à mot de passe temporaire ; le profil `volumetrie` affiche une fois celui des six comptes de test).

## 7. Méthode
- Une tâche à la fois, dans un worktree court, un commit par tâche, tests ciblés ; suite complète à l'intégration.
- Défauts récurrents à contrôler en revue : unicité conditionnelle (suppression logique), blocage des
  `update/bulk_*` sur modèles figés, ordre de verrouillage mission, étape, entité, preuves à écriture unique
  avec SHA-256, erreurs serveur liées aux champs côté front, aucune confirmation légale pré-cochée.
- `schema.d.ts` est toujours régénéré (jamais à la main). Conflits CRLF/LF fréquents sous Windows.
