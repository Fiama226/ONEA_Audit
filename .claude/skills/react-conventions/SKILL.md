---
name: react-conventions
description: Conventions frontend du projet ONEA Audit (React 19, TypeScript, Vite, shadcn/ui, TanStack Query/Table, react-hook-form, zod). À lire avant d'écrire ou relire du code frontend.
---

# Conventions frontend

## Arborescence
```
frontend/src/
  api/            client fetch typé, schema.d.ts (openapi-typescript), hooks génériques
  components/ui/  composants shadcn générés (ne pas modifier à la main sauf tokens)
  components/     composants partagés métier (StatutBadge, MatriceRisques, EtapeStepper)
  features/
    missions/     pages, components, hooks, api
    referentiel/
    programme/
    constats/
    actions/
    documents/
  layouts/        AppShell (sidebar, header, fil d'Ariane), PrintLayout
  i18n/fr.ts      tous les libellés
  lib/            utils (dates Africa/Ouagadougou, formatage), zod schemas partagés
  routes.tsx
```

## Données
- `useQuery` / `useMutation` de TanStack Query, clés `['missions', id]`, invalidation ciblée.
- Client API unique `api/client.ts` : base URL, token OIDC, gestion 401/403/422.
- Types générés : `npm run gen:api` (openapi-typescript sur `/api/schema/`).

## Formulaires
react-hook-form + zodResolver. Schéma zod par formulaire dans le dossier de la feature.
Erreurs 422 du serveur mappées sur les champs (`setError`). Libellés et messages via `fr.ts`.

## Tableaux
TanStack Table + composant `DataTable` partagé : tri, filtres, pagination serveur,
export CSV, colonnes masquables, état persisté dans l'URL (nuqs ou searchParams).

## États d'écran
Chaque page gère explicitement : chargement (skeleton), vide (message + action),
erreur (message + réessayer), succès. Pas de spinner plein écran.

## Permissions UI
Hook `useRole()` ; les actions interdites sont masquées, pas seulement désactivées,
sauf quand l'utilisateur doit comprendre pourquoi (alors désactivée + tooltip).

## Style
Tailwind avec tokens CSS de la charte (`--primary`, `--accent`, …) déclarés dans
`styles/tokens.css`. Jamais de couleur hexadécimale dans un composant. Lucide pour les icônes.
Impression : classes `print:` et `PrintLayout` pour les documents consultables à l'écran.

## Tests
Vitest + Testing Library + MSW pour mocker l'API. Tester le comportement utilisateur
(`getByRole`, `getByLabelText`), jamais les détails d'implémentation.

## Qualité
`tsc --noEmit` strict, ESLint (typescript-eslint, react-hooks, jsx-a11y), Prettier.
