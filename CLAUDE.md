# ONEA — Plateforme de digitalisation de l'audit interne

Application web pour le Département Audit Interne (DAI) de l'ONEA (Office National de l'Eau
et de l'Assainissement, Burkina Faso). Elle digitalise le processus de conduite des missions
d'audit interne tel que décrit par les fiches méthodologiques IFACI (18 étapes, 3 phases)
et les Normes internationales d'audit interne IIA 2024.

Maître d'œuvre : IKA SOLUTION LTD. Langue de travail et de l'interface : **français**.

## Règles absolues

1. **Aucune fonctionnalité IA dans le produit.** Pas d'appel LLM, pas d'embedding, pas de
   « génération assistée », pas de chatbot. L'IA sert uniquement à construire le logiciel.
2. **100 % open source.** Toute dépendance doit être sous licence MIT, BSD, Apache 2.0,
   PostgreSQL, LGPL, AGPL ou MPL-2.0 (mozilla-django-oidc). Licences permissives équivalentes
   acceptées : ISC, OFL-1.1, 0BSD, BlueOak, CC0, CC-BY-4.0, Python-2.0. Aucun SaaS payant, aucun service propriétaire.
3. **Français partout** dans l'interface, les messages, les documents générés et la doc
   fonctionnelle. Le code (identifiants, commits) est en anglais.
4. **Piste d'audit complète** : toute création, modification, validation est historisée
   (qui, quand, quoi). Jamais de suppression physique sur les objets métier (soft delete).
5. **Design institutionnel et soigné** : voir `docs/design/charte-graphique.md`. Pas de
   gadgets, pas d'animations gratuites, lisibilité et densité d'information maîtrisée.

## Stack (figée)

| Couche | Choix |
|---|---|
| Backend | Python 3.12, Django 5.x, Django REST Framework, django-fsm, django-auditlog, django-filter |
| Frontend | React 19, TypeScript strict, Vite, React Router, TanStack Query, TanStack Table, shadcn/ui (Radix + Tailwind), react-hook-form + zod |
| Base de données | PostgreSQL 16 |
| Tâches de fond | Celery + Redis (Valkey) |
| Documents | docxtpl (remplissage des gabarits Word ONEA), Gotenberg (docx → PDF) |
| Recherche | Meilisearch |
| Fichiers | Système de fichiers du serveur (volume Docker), via l'interface de stockage ; S3 en option future |
| Auth | Keycloak (OIDC) via mozilla-django-oidc ; la SPA n'utilise que Keycloak (pas d'auth Django locale ; admin Django en session, hors SPA) |
| Tests | pytest + pytest-django + factory_boy ; Vitest + Testing Library ; Playwright (e2e) |
| Qualité | ruff, mypy, ESLint, Prettier, pre-commit |
| Infra | Docker Compose, Nginx, Gitea Actions (ou GitHub Actions) |

## Structure du dépôt

```
backend/          Django (apps: core, missions, risques, documents, recommandations, referentiel, users)
frontend/         React + Vite
docs/             spécifications, plans, charte graphique, domaine métier
docs/superpowers/specs/   documents de conception approuvés
docs/superpowers/plans/   plans d'implémentation
docker/           Dockerfiles, compose, nginx
.claude/agents/   agents spécialisés (orchestration)
.claude/skills/   connaissances projet (domaine audit, conventions, charte)
```

## Workflow de développement (obligatoire)

1. **Conception** : `superpowers:brainstorming` → document dans `docs/superpowers/specs/`.
2. **Plan** : `superpowers:writing-plans` → `docs/superpowers/plans/`.
3. **Exécution** : `superpowers:subagent-driven-development`. L'agent `orchestrator`
   découpe le plan et délègue aux agents spécialisés (voir `.claude/agents/`).
4. **TDD** : tests d'abord (`superpowers:test-driven-development`). Rien ne passe en revue
   sans tests verts.
5. **Revue** : chaque tâche terminée est relue par `reviewer` (indépendant de l'auteur).
6. **Vérification** : `superpowers:verification-before-completion` avant de déclarer terminé.

## Routage des modèles

| Travail | Modèle | Pourquoi |
|---|---|---|
| Orchestration, architecture, conception, revue de code, design UI | **opus** | raisonnement long, jugement |
| Implémentation backend/frontend, tests, migrations | **sonnet** | rapide, fiable sur du code cadré par un plan |
| Documentation, renommages, formatage, commits, tâches mécaniques | **haiku** | coût minimal |

Les agents fixent déjà leur modèle dans leur frontmatter ; ne pas le surcharger sans raison.

## Commandes

```
make up            # docker compose up (postgres, redis, meilisearch, gotenberg, keycloak)
make backend       # python manage.py runserver
make frontend      # npm run dev
make test          # pytest + vitest
make e2e           # playwright
make lint          # ruff + mypy + eslint + prettier
```

## Conventions

- Branches : `feat/<sujet>`, `fix/<sujet>`, `docs/<sujet>`. Commits Conventional Commits en anglais.
- Backend : une app Django par domaine ; logique métier dans `services.py`, jamais dans les vues.
  Sérialiseurs DRF explicites (pas de `fields = "__all__"`). Migrations toujours commitées.
- Frontend : composants dans `src/components/ui` (shadcn) et `src/features/<domaine>/`.
  Pas de `any`. Toute donnée serveur passe par TanStack Query. Formulaires via react-hook-form + zod.
- Noms métier en français dans le modèle de données (Mission, Constat, Recommandation,
  ProgrammeDeTravail), identifiants techniques en anglais (`created_at`, `status`).
- Dates : stockées en UTC, affichées en `Africa/Ouagadougou`, format `JJ/MM/AAAA`.

## Références métier

- `docs/domaine/processus-ifaci.md` : les 18 étapes et 16 outils de conduite de mission.
- `docs/domaine/cartographie-risques-onea.md` : processus ONEA, matrice 5×5, scoring.
- `docs/domaine/documents-mission.md` : liste des gabarits Word à produire.
- Normes IIA 2024 : `docs/domaine/normes-iia-sommaire.md`.
