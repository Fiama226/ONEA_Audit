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

Les parcours e2e (`frontend/e2e/`) tournent sur une **base PostgreSQL jetable** : la base
`onea` de développement n'est jamais écrite (aucun SQL de nettoyage dans les specs).

```
make up                        # pile de dev : au minimum db et keycloak
make e2e                       # = sh scripts/e2e.sh   (Windows : pwsh scripts/e2e.ps1)
sh scripts/e2e.sh e2e/login.spec.ts   # arguments transmis à Playwright
```

`scripts/e2e.sh` crée `onea_e2e_<horodatage>`, la migre, lance l'API sur `127.0.0.1:8010`
(documents dans un dossier temporaire) et Vite sur `5174`, exécute Playwright, puis arrête les
serveurs et supprime la base et le dossier temporaire. La pile de dev (8000/5173, base `onea`)
continue de tourner ; le script affiche les comptes de `missions_mission` et
`referentiel_cartographieversion` de `onea` avant et après et échoue (code 4) s'ils diffèrent.
Garde : un nom de base (`E2E_DB_NAME`) hors `^onea_e2e_[0-9]+$` est refusé avec le code 2, avant
toute écriture. Les données de test portent l'identifiant d'exécution (`E2E_RUN_ID`).
La recherche (Meilisearch) et la file Celery de la pile de dev ne sont pas utilisées (URL
inerte, base Redis 14).

Prérequis Keycloak : le client `onea-frontend` doit autoriser `http://localhost:5174/*`
(redirection, origine et déconnexion), ce que fait `docker/keycloak/realm-onea.json`. Le realm
n'est importé qu'à la création du volume : sur une pile existante, ajouter ces URI dans la
console Keycloak (client `onea-frontend`) ou recréer le volume Keycloak.

Nettoyage unique du lot 3 : la base orpheline `onea_e2e3` est supprimée par le script si elle
existe (à la main sinon : `docker compose exec db dropdb -U onea onea_e2e3`). Chargement
initial des listes de référence : `backend/README.md`, section « Référentiel : chargement
initial ».
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
