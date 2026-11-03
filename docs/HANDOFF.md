# Passation — plateforme d'audit interne ONEA

Dernière mise à jour : **2026-11-03**. Rien n'est poussé : tout est local (Git). Sources de vérité de cet
état : `git log --oneline` et `git branch --merged develop` (le texte précédent de ce fichier, daté du
2026-10-30, était périmé).

## 1. Règles du projet (voir `CLAUDE.md`)
- Interface et documents en **français** ; code et commits en anglais (Conventional Commits).
- **Aucune fonction IA/LLM dans le produit.** Logiciels **100 % open source** (liste des licences dans
  `CLAUDE.md`, décisions du 2026-11-02 incluses : MIT-0, PSF-2.0, ZPL-2.1, ClamAV en conteneur séparé).
- Stack : Django 5.2 + DRF (`backend/`), React 19 + TypeScript + Vite + Tailwind + shadcn (`frontend/`),
  PostgreSQL 16, Celery + Redis, docxtpl + Gotenberg, Keycloak (OIDC), Meilisearch.
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

## 3. Décisions déjà prises (ne plus les redemander)
- Licences MIT-0, PSF-2.0 et ClamAV (conteneur séparé, GPL-2.0) autorisées : commit 6c982ec. ZPL-2.1 : 120ee1b.
- SEC-07 (confirmation horodatée en SHA-256 sans clé) : risque **accepté**, commit 52a5aba.
- Hypothèses métier des lots : toutes confirmées (2026-10-29) ; gabarits Word vierges provisoires acceptés.

## 4. Ce qui reste à faire (équipe projet)
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
| Hébergement, DNS, TLS (U2) | VPS ou site, deux noms (application, SSO), autorité interne ou Let's Encrypt | recette avec AC jetable |
| SMTP (U3) | hôte, port, mode, compte, expéditeur, SPF/DKIM | la production refuse de démarrer sans `EMAIL_URL` |
| Réseau ONEA (U5) | proxy amont, réseau d'administration, supervision | aucun proxy, console Keycloak fermée |
| Formation (U6) | participants, dates, salle, postes | supports prêts, calendrier à fixer |
| 22 gabarits Word réels | `docs/documents/gabarits-manquants.md` | gabarits provisoires générés |
| Abréviations ONEA à confirmer | QPC, GST, QCI, MARC, FF, RO, PT, FCT, FDT, FIT, FO | libellés actuels conservés |
| Rôles OTP (D19) | quels comptes à privilèges exigent un second facteur ; liste de mots de passe interdits | documenté dans `deploy.md` §5 étape 8 |
| Libellé de la direction des participants | formulation sur l'ordre de mission | à trancher |
| Clôture de l'antivirus | réseau sortant vers `database.clamav.net` ou miroir local | contrôle des signatures d'octets seul si ClamAV non livré |

## 6. Lancer / tester en local
- Docker Desktop : conteneurs `onea-db-1`, `onea-keycloak-1`, `onea-redis-1`.
- API : `cd backend`, Python `C:\v\onea\Scripts\python.exe manage.py runserver 127.0.0.1:8000` avec
  `DATABASE_URL=postgres://onea:onea-dev-password@127.0.0.1:5432/onea`.
- Web : `cd frontend && npm run dev` (http://localhost:5173, utiliser `localhost`). Keycloak
  http://127.0.0.1:8180. Clé `KEYCLOAK_ADMIN_API_CLIENT_SECRET` à placer dans `.env` pour la synchronisation.
- Comptes de développement et de recette (mot de passe `onea2026`) : `admin`, `rai`, `auditeur1`,
  `auditeur2`, `audite1`, `dg`. Jamais en production.
- Tests back : `unset DJANGO_SETTINGS_MODULE`, base dédiée (jamais `onea`), `pytest` ciblé. Tests front :
  `npx vitest run --maxWorkers=2 --testTimeout=30000`. Une suite complète prend 15 à 30 minutes.
- Données de démonstration : `python manage.py peupler_demo --profil formation --recette` sur base vide.

## 7. Méthode
- Une tâche à la fois, dans un worktree court, un commit par tâche, tests ciblés ; suite complète à l'intégration.
- Défauts récurrents à contrôler en revue : unicité conditionnelle (suppression logique), blocage des
  `update/bulk_*` sur modèles figés, ordre de verrouillage mission, étape, entité, preuves à écriture unique
  avec SHA-256, erreurs serveur liées aux champs côté front, aucune confirmation légale pré-cochée.
- `schema.d.ts` est toujours régénéré (jamais à la main). Conflits CRLF/LF fréquents sous Windows.
