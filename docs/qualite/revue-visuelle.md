# Revue d'interface (lot 9, T22/T24/T25) : revue de code, sans navigateur

Date : 2026-11-03. Périmètre : écrans du suivi (lot 8), conteneurs à défilement horizontal, écran
principal du RAI. **Limite : aucune revue visuelle en navigateur n'a été faite** (pas de captures,
pas de contrôle des alignements, de la densité ni du rendu aux largeurs 1280, 1024, 768 et 390 px).
`frontend/e2e/captures.spec.ts` et la grille complète du plan T22 restent à faire sur la pile de recette.
Ce document ne couvre que ce qui se vérifie dans le code, par test ou par lint.

## Constats corrigés

| Écran / composant | Défaut | Règle | Gravité | Correction | Vérification |
|---|---|---|---|---|---|
| 22 conteneurs `overflow-x-auto` (tableaux des lots 3 à 8, matrices, exemple CSV, tableau alternatif des graphiques) | `div` défilant non focusable : le défilement horizontal est impossible au clavier ; cinq tableaux imbriquaient en plus deux défileurs | WCAG 2.1.1, 1.4.10 ; axe `scrollable-region-focusable` | majeur | composant `ScrollRegion` (`role="group"`, nom accessible repris de la légende du tableau, `tabIndex=0`, anneau de focus de la charte) ; défileur redondant retiré autour de `<Table>` | `scroll-region.test.tsx` (axe + interdiction de tout nouveau `overflow-x-auto` hors liste) |
| Pastille de notifications non lues | texte à 10 px, hors échelle typographique (12 / 14 / 16 / 20 / 24 / 32) | charte, Typographie | mineur | `text-xs`, pastille 20 px | `NotificationBell.test.tsx` |
| Forces et faiblesses : badge | texte à 11 px | charte, Typographie | mineur | `text-xs` | revue de code |
| File de décisions du RAI | trois liens menaient au registre non filtré | cohérence lien / libellé | majeur | écrans `/recommandations/reports` et `/recommandations/relances` filtrés par `?statut=` | `Journaux.test.tsx`, `DashboardRAI.test.tsx` |
| Réunion non tenue (SEC-09) | déjà corrigé (T29) : `ReunionSerializer.to_representation` vide compte rendu et décisions pour l'audité | confidentialité | faible | aucune (vérifié) | `tests/missions/test_sec08_sec09.py` |

## Constats non corrigés (à traiter lors de la revue en navigateur)

- `PrintLayout` (en-tête et pied d'impression) utilise 10 et 11 px : acceptable en impression, à confirmer visuellement.
- `AuditPlanCalendar` garde son propre conteneur (déjà `role="region"`, nommé et focusable) : conforme, non migré.
- Contrastes réels, zébrage, hauteur de ligne de 44 px, en-têtes collants, lecture à 390 px : non vérifiables sans navigateur.

## Contrôles statiques effectués

Recherche dans `frontend/src` : aucune couleur brute (palette Tailwind ou hexadécimal) dans les `.tsx`,
aucun `any`, aucun `tabIndex` positif, toutes les `<img>` ont un `alt`, les `outline-none` sont tous
accompagnés d'un anneau `focus-visible` ou portent sur des titres ciblés par programme (`tabIndex=-1`).
