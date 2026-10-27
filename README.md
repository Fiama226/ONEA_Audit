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
- [ ] Document de conception approuvé (`docs/superpowers/specs/`)
- [ ] Plan d'implémentation (`docs/superpowers/plans/`)
- [ ] Lot 1 : socle technique

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
Gotenberg, Meilisearch, MinIO, Keycloak, Docker Compose. Détail et justification dans `CLAUDE.md`.

## Licence

À définir (open source).
