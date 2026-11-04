# Audit d'accessibilité automatisé et clavier (lot 9, tâche 21)

Statut : **outillage livré, exécution navigateur en attente.** Aucune violation n'est consignée
ci-dessous parce que le parcours axe et clavier n'a pas pu être exécuté dans cette session
(Playwright MCP indisponible, pile e2e + base peuplée non démarrée). Aucun constat n'est
inventé : les sections « Violations » et « Constats clavier » sont à remplir à partir des sorties
décrites au paragraphe « Exécution ».

## Ce qui est livré

| Élément | Rôle |
|---|---|
| `frontend/e2e/inventaire.ts` | Inventaire : 47 motifs de route avec rôles autorisés (miroir de `ROUTE_ROLES`), ressources à résoudre pour les pages de détail, comptes de démonstration, dialogues principaux. |
| `frontend/src/test/inventaire-a11y.test.ts` | `test_inventaire_complet` (Vitest, vert) : toute clé de `ROUTE_ROLES` et tout `path:` des fichiers de routes (racine, missions, programmation, référentiel, documents, administration) figure dans l'inventaire. Une route ajoutée sans inventaire fait échouer le test. |
| `frontend/e2e/a11y.spec.ts` | Par rôle (ADMIN, RAI, AUDITEUR, AUDITE, DG) et par route autorisée : axe (`wcag2a`, `wcag2aa`, `wcag21aa`) page chargée, puis chaque dialogue (déclencheurs listés + tout `aria-haspopup="dialog"`) ouvert, analysé, fermé par Échap. Sortie : `frontend/test-results/a11y-violations.json` (route, rôle, contexte, règle, gravité, élément). `A11Y_STRICT=0` (défaut) : rapport seul ; `A11Y_STRICT=1` : échec sur `serious`/`critical` (T24, T25). |
| `frontend/e2e/clavier.spec.ts` | Lien d'évitement (premier arrêt, visible, focus sur `#contenu`), ordre de tabulation et focus visible (style calculé : contour ou ombre), piège et retour du focus dans un dialogue, Échap, absence de piège clavier. Mêmes modes `A11Y_STRICT`. En mode rapport, les constats sont des annotations `constat-clavier`. |
| `@axe-core/playwright` 4.14.0 (exact) | Dépendance de développement, licence MPL-2.0 (autorisée), même version que `axe-core` déjà présent. `package.json` et `package-lock.json` mis à jour. |

Écart au plan : `npm install` n'a pas été exécuté (le `node_modules` de ce worktree est une
jonction vers le dépôt principal, à ne pas modifier) ; le verrou a été produit avec
`npm install --package-lock-only`. Faire `npm ci` avant la première exécution.

## Exécution (à faire avec un navigateur)

1. Pile e2e : `scripts/e2e.sh` (base jetable `onea_e2e_*` ; elle crée les comptes de test par `creer_comptes_e2e`).
2. Base peuplée : `python manage.py peupler_demo --profil formation` sur la base e2e, avec les
   comptes e2e créés par `creer_comptes_e2e` (mot de passe `E2E_PASSWORD`, voir `scripts/e2e.sh`).
3. `cd frontend && npm ci && npx playwright test e2e/a11y.spec.ts e2e/clavier.spec.ts` (le script
   e2e accepte ces arguments).
4. Lire `test-results/a11y-violations.json` et les annotations `constat-clavier`, puis remplir les
   tableaux ci-dessous.

Réserves connues du parcours, à confirmer à la première exécution :

- Les chemins d'API de résolution des identifiants (`LISTES` dans `a11y.spec.ts`) suivent le
  routeur DRF ; une route dont la ressource est absente est listée dans `nonResolues` (journal),
  pas ignorée en silence. Les gabarits sont adressés par `code`, supposé présent sur
  `document-types` (à vérifier).
- Les libellés de déclencheurs de `DIALOGUES` sont des expressions larges ; un déclencheur
  introuvable est sauté. Les dialogues déclenchés par un bouton sans `aria-haspopup` (état React)
  ne sont atteints que par ce biais.
- Les contrastes (`color-contrast`) ne sont fiables qu'en navigateur réel (jsdom ne calcule pas
  les couleurs) : c'est la catégorie la plus probable de violations.

## Violations axe

Colonnes attendues pour chaque violation `serious` ou `critical` (zone A = corrigée par T24,
zone B = corrigée par T25 ; voir ces tâches) :

| Route | Rôle | Règle axe | Élément | Gravité | Zone | Correction proposée |
|---|---|---|---|---|---|---|
| (à remplir après exécution) | | | | | | |

## Constats clavier

| Contrôle | Résultat | Écran | Correction proposée |
|---|---|---|---|
| Lien d'évitement | à vérifier (le lien existe : `AppShell`, `href="#contenu"`, `main#contenu` avec `tabIndex=-1`) | | |
| Ordre de tabulation | à vérifier | | |
| Focus visible | à vérifier | | |
| Piège et retour du focus (dialogues) | à vérifier (Radix Dialog attendu conforme) | | |
| Échap | à vérifier | | |
| Aucun piège clavier | à vérifier | | |

## Reliquats à traiter comme constats

- Programme T7, M9 et lot 3, T6 : **ordre des titres** (`heading-order`). Non vérifié ici ; la
  règle `heading-order` est de gravité « moderate » dans axe, donc absente du critère
  « serious/critical » : la relever explicitement dans `a11y-violations.json` (filtrer par règle)
  et la consigner dans le tableau ci-dessus avec sa zone.

## Relecture

Étape 4 du plan (relecture par `reviewer`) : non faite, rien à relire tant que le tableau est vide.
