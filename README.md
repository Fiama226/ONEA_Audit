# ONEA — Plateforme de digitalisation de l'audit interne

Digitalisation du processus de conduite des missions d'audit interne du Département Audit
Interne de l'ONEA, selon la méthodologie IFACI (18 étapes) et les Normes IIA 2024.
Projet IKA SOLUTION LTD, construit avec assistance IA (Claude Code), sans aucune
fonctionnalité IA dans le produit.

## État du projet

- [x] Analyse du recueil de besoins (`docs/domaine/`)
- [x] Stack technique validée (`CLAUDE.md`)
- [x] Harnais de développement : agents, skills, MCP (`.claude/`, `.mcp.json`)
- [x] Charte graphique (`docs/design/charte-graphique.md`)
- [x] Document de conception approuvé (`docs/superpowers/specs/`)
- [x] Plan d'implémentation (`docs/superpowers/plans/`)
- [x] Lot 1 : socle technique
- [x] Lot 2 : référentiel (processus, objets auditables, cartographie des risques, import, export)

## Démarrage rapide

```
cp .env.example .env
make up                      # ou : docker compose --env-file .env -f docker/compose.yml -f docker/compose.dev.yml up -d
make backend                 # voir backend/README.md (venv, migrations)
cp frontend/.env.example frontend/.env && make frontend
```

## Poste Windows

Le dépôt peut se trouver dans OneDrive ou dans un chemin avec espaces : le venv Python est donc créé hors du dépôt.

```
pwsh scripts/dev-setup.ps1   # uv venv + uv sync --frozen dans $env:ONEA_VENV (défaut %LOCALAPPDATA%\oneaenv) + npm ci
pwsh scripts/dev-up.ps1      # base, Valkey, Keycloak, API (8000), Vite (5173)
pwsh scripts/dev-down.ps1
```

`dev-up.ps1` cherche l'interpréteur dans `$env:ONEA_VENV`, puis `backend\.venv` ; à défaut il s'arrête (code 1) en indiquant `scripts/dev-setup.ps1`.

Le stockage des documents est sur disque (plus de service d'objets). Si l'ancien volume Docker orphelin du stockage objet existe, le repérer avec `docker volume ls -q -f name=onea_mini` puis le supprimer par `docker volume rm <nom>`.

## Tests de bout en bout (Playwright)

Les parcours e2e (`frontend/e2e/`) tournent sur la pile de développement : Keycloak (realm
`onea`), l'API Django et Vite (lancé par Playwright). Ils créent leurs données et les
retirent ensuite (la plateforme reste vide) ; le parcours RAI du référentiel utilise le
processus `ZZE` et les cartographies 2098 et 2099.

```
make up                # postgres, redis, keycloak, ...
make backend           # dans un second terminal (migrations appliquées au préalable)
make e2e               # = cd frontend && npx playwright test
```

Le nettoyage du parcours « référentiel » met à jour la base via `docker compose exec db psql`
(une cartographie validée ne peut pas être supprimée par l'API) : lancez-le depuis la machine
qui héberge la pile de développement. Chargement initial des listes de référence :
`backend/README.md`, section « Référentiel : chargement initial ».

## Démarrer avec Claude Code

```
cd onea-audit
claude
```

Puis, par exemple : « Utilise l'agent orchestrator pour exécuter le lot 1 du plan ».

Agents disponibles : `orchestrator`, `db-architect`, `backend-dev`, `frontend-dev`,
`ui-designer`, `test-engineer`, `reviewer`, `docs-writer`.
Skills projet : `django-conventions`, `react-conventions`, `charte-graphique`, `domaine-audit`.

Permissions Claude Code suggérées : copier `docs/settings.suggested.json` vers
`.claude/settings.json`.

## Stack

Django 5 + DRF, React 19 + TypeScript + shadcn/ui, PostgreSQL 16, Celery/Redis, docxtpl,
Gotenberg, Meilisearch, Keycloak, Docker Compose. Détail et justification dans `CLAUDE.md`.

## Licence

À définir (open source).
