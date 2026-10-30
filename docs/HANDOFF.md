# Passation (Kilo Code) — plateforme d'audit interne ONEA

Dernière mise à jour : 2026-10-30. Rien n'est poussé. Tout est local (Git).

## 1. Règles du projet (voir aussi `CLAUDE.md`)
- Réponses et interface en **français**. Logiciels **open source uniquement** (licences listées dans CLAUDE.md).
- **Aucune fonction IA/LLM dans le produit.**
- Stack : Django 5.2 + DRF (`backend/`), React 19 + TS + Vite + Tailwind 4 + shadcn (`frontend/`), PostgreSQL 16, Celery + Redis, docxtpl + Gotenberg, Keycloak 26 (OIDC). Fichiers sur disque du VPS (jamais dans Git).
- Rôles : ADMIN, RAI, AUDITEUR, AUDITE, DG. Méthode IFACI 18 étapes ; carte des risques 5×5.
- Les hypothèses métier sont **toutes confirmées** par l'utilisateur ; gabarits Word vierges provisoires (`docs/documents/gabarits-manquants.md` : 22 vrais gabarits à récupérer).

## 2. État des branches (dépôt `onea-audit/`)
| Branche | Contenu |
|---|---|
| `main` (927795c) | Lots 1–5 (socle, référentiel, missions, documents, analyse back), utilisateurs, programme annuel. 1689 tests back + 571 vitest verts |
| `develop` (worktree `C:/tmp-dev`) | main + écrans lot 4/5, lot 9 T1,2,3,4,5,6,8,9,12,13,14. **Suites complètes non relancées** |
| `preview` | = develop, extraite dans le checkout principal pour tester le site |
| `feat/lot6-accomplissement` (`C:/tmp-l6`, 279d609) | Lot 6 API T1–T7, T9 + corrections T7. **Pas encore fusionnée dans develop** |
| `worktree-agent-a6bb9c469ea3220f4` (cd9b928) | **WIP non terminé** lot 6 T8 (API constats), non testé — à reprendre |
| `docs/plan-lot6..9`, `docs/plan-*` | Plans détaillés (`docs/superpowers/plans/*.md`), un par lot |

Plans : `2026-10-28-lot6-accomplissement.md` (14 tâches), `2026-10-29-lot7-communication.md` (17+T18), `2026-10-29-lot8-suivi.md` (17), `2026-10-29-lot9-durcissement.md` (36). Journaux d'avancement (git-ignorés) : `.superpowers/sdd/<plan>/progress.md`, rapports `task-N-report.md` / `task-N-review.md`.

## 2bis. Mise à jour 2026-10-30 (session Kilo)
- Fait dans `develop` (7a09a1b) : lot 9 T9/T12 corrigés (ip_range web, access_log par server, 50r/s, API admin Keycloak, portées import/annuaire, THROTTLE_RATE_* dans le compose) ; lot 6 T8 terminé (API constats, 90 tests ciblés verts) ; `feat/lot6-accomplissement` fusionnée ; `schema.d.ts` régénéré, `check-api-fresh` OK ; peuplements démo enregistrés (core, accomplissement, constats).
- Non fait : `test_api_contrat_lot6` (JSON exact figé, consommé par T13) ; bancs réseau lot 9 non lancés (revue statique seulement) ; suites complètes non relancées ; `main` non avancée.
- Lot 6 T10 fait (d6030df) : upload XHR/download authentifiés, hooks accomplissement et constats, badges, EvidenceUploader/List, zones VIII–XIV en squelettes, routes `fiches/:id`, `constats`, onglet Constats ; typecheck, eslint, prettier et tests ciblés verts.`n- Lot 6 T11, T12, T13 faits en parallèle (sous-agents) et fusionnés dans develop ; volume `onea-fichiers` ajouté (T14 partiel) ; `test_api_contrat_lot6` créé ; 251 vitest ciblés verts. Revue visuelle ui-designer non faite.`n- Reste lot 6 T14 : e2e Playwright `accomplissement.spec.ts` (banc Docker+Keycloak), `test_contrat_stockage` lot 4, README back, versions 0.6.0. Puis lots 7, 8, reste du lot 9, suites complètes, avancer `main`.
- Les sous-agents Kilo (Sonnet 5.5) ont échoué : crédits Kilo insuffisants (solde négatif).

## 3. Reste à faire (ordre conseillé)
1. **Lot 9 T9 + T12 : appliquer les corrections de revue** (`.superpowers/sdd/2026-10-29-lot9-durcissement/task-9-review.md`, `task-12-review.md`) :
   - C1 `docker/compose.prod.yml` : ajouter `ip_range` au réseau `web` (nginx ne démarrerait pas).
   - I1 `access_log` par bloc `server` (l'ancien journal fuit la query string OIDC) ; I2 limites nginx 50r/s rafale 100 ; I3 endpoint logout inexistant dans `scripts/recette/tests/reseaux.sh` ; I4 `location` pour l'API admin Keycloak depuis le sous-réseau `web`.
   - T12 : limiter `apps/users/account_views.py` (import-csv, import_directory, directory_search) ; transmettre `THROTTLE_RATE_*` dans `compose.prod.yml`.
2. **Lot 6 T8** (reprendre le WIP `cd9b928`), puis fusionner `feat/lot6-accomplissement` dans `develop`, régénérer `frontend/src/api/schema.d.ts` (jamais à la main), relancer `check-api-fresh`.
3. Lot 6 T10–T14 (écrans accomplissement, e2e, branchement du stockage lot 4).
4. Lot 7 (communication/signatures, puis 7bis PAdES), lot 8 (suivi, notifications, tableaux de bord, recherche), lot 9 restant (T7 e2e isolé, T10, T11, T15–T36).
5. À l'intégration : suites complètes back + front **une seule fois**, puis avancer `main`.
6. Points ouverts (utilisateur) : ajouter MIT-0 et PSF-2.0 aux licences autorisées ? ; sauvegarde hors serveur, DNS/TLS, SMTP, ClamAV ; 22 gabarits Word ; abréviations ONEA à confirmer ; Keycloak : `KEYCLOAK_ADMIN_API_CLIENT_SECRET=onea-dev-sync-secret` dans `.env` + recréer le conteneur.

## 4. Lancer / tester en local
- Docker : conteneurs `onea-db-1`, `onea-keycloak-1`, `onea-redis-1` (Docker Desktop doit tourner).
- API : `cd backend` puis Python `C:\v\onea\Scripts\python.exe manage.py runserver 127.0.0.1:8000` avec `DATABASE_URL=postgres://onea:onea-dev-password@127.0.0.1:5432/onea`.
- Web : `cd frontend && npm run dev` → http://localhost:5173 (utiliser `localhost`). Keycloak http://127.0.0.1:8180 (admin / admin-dev-password).
- Comptes (mot de passe `onea2026`) : admin, rai, auditeur1, auditeur2, audite1, dg.
- Tests back : `unset DJANGO_SETTINGS_MODULE`, base dédiée (ex. `onea_test1`), `pytest` ciblé. Tests front : `npx vitest run --maxWorkers=2 --testTimeout=30000`. Machine lente : une suite complète = 15–30 min.
- Ne jamais lancer de tests sur la base `onea` du site de dev.

## 5. Méthode de travail recommandée (économie de jetons)
- Une tâche du plan à la fois, dans un worktree Git court (`git worktree add C:/tmp-x -b feat/...`) ; commit par tâche ; **tests ciblés seulement**, suite complète à l'intégration.
- Choix de modèle : planification/revue de sécurité/arbitrage = **le plus capable** ; implémentation depuis un plan détaillé = **milieu de gamme** ; docs, renommages, corrections mécaniques = **le moins cher**. Relire seulement le brief de la tâche (`docs/superpowers/plans/…` section Task N), pas tout le plan.
- Défauts récurrents à vérifier à chaque revue : contraintes d'unicité conditionnelles (suppression logique) ; blocage des `update/bulk_*` sur modèles figés ; fenêtre d'écriture dans chaque service d'écriture ; ordre de verrouillage mission → étape → entité ; preuves en écriture unique avec SHA-256 vérifié à la lecture ; côté front : erreurs serveur liées aux champs (aria-describedby + focus), chargement/erreur jamais rendus comme « vide », aucune confirmation légale pré-cochée, `removeQueries` après suppression.
- Conflits CRLF/LF fréquents sous Windows ; `schema.d.ts` toujours régénéré.
- Nettoyage à faire plus tard : ~97 worktrees/enregistrements, bases `onea_*` de tests.
