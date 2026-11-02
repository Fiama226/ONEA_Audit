# Rapport QA design et accessibilité (2026-11-02)

Périmètre : 47 motifs de route (`frontend/e2e/inventaire.ts`) pour les 5 rôles (admin, rai, auditeur1, audite1, dg), 4 largeurs (1440, 1024, 768, 390 px), axe-core (wcag2a, wcag2aa, wcag21aa) à 1440 et 390, clavier, dialogues, impression A4, mouvement réduit, console. Outil : script Playwright dédié (contexte isolé). Aucune donnée existante modifiée. Branche `fix/qa-design`.

Limites : les routes de détail dépendent des données présentes (fiches de test et constats non résolus à la fin du passage). Les correctifs CSS ont été validés par tests unitaires, non revus visuellement sur le site actif (le Keycloak local refuse une origine de rechange). Le mode sombre n'est pas appliqué via `prefers-color-scheme` : non évalué.

## Défauts constatés

| Gravité | Écran / rôle / largeur | Constat | Statut |
|---|---|---|---|
| Haute | `/missions/:id/rapport`, AUDITE, toutes largeurs | URL directe : erreur d'écran (`StatusPill` reçoit un rapport diffusé sans `statut`) | Corrigé (5fb81c0), accès refusé proprement |
| Haute | Dialogues contrôlés (création de programme, cartographie, etc.), tous rôles | Après Échap ou Annuler, le focus retombe sur `<body>` (pas de retour au déclencheur, WCAG 2.4.3) | Corrigé (04f0295), test de non-régression |
| Haute | Tableaux (`DataTable`) : utilisateurs, programme, etc., 390 à 1440 | Colonnes et boutons d'en-tête tronqués, la page entière défile latéralement (`overflow-x-clip`) | Corrigé (7b7a88a) : le tableau défile seul et est atteignable au clavier |
| Moyenne | Pied de menu, tous écrans | « Version 0.5 · lot 5 » | Corrigé |
| Moyenne | Mission (zones, réunions, documents), tous rôles | Mentions « lot 4 », « lot 7 bis », « prochain lot » visibles | Corrigé (fr.ts) |
| Moyenne | Tableau de bord, liens de missions sans référence | Lien vide (axe link-name serious) | Corrigé (de12ebc) |
| Moyenne | Onglets inactifs (programme annuel, 1440 et 390) | Contraste 3,96:1 | Corrigé : `text-text-muted` |
| Moyenne | `/rapports` et `/rapports/:id`, tous rôles | Aucun h1 | Corrigé (e434856) |
| Moyenne | `/missions/:id/modifier` | Deux h1 | Corrigé : h2 en modification |
| Moyenne | `/documents/:id` 390, `/referentiel/cartographies/:id` 390 | Défilement horizontal de page (numéro long, grille sans `minmax(0,1fr)`) | Corrigé (non revu à l'écran) |
| Basse | Matrice de risques (1440) | Axe « Impact » et légende décentrés par rapport à la grille | Corrigé |
| Basse | Cartographie | « 1 risques au total » | Corrigé (singulier) |
| Basse | Recherche globale (1440, 390) | Placeholder tronqué (« …un constat, ur ») | Corrigé : « Rechercher dans la plateforme… » |
| Basse | Tables à `overflow-x-auto` (analyse, constats, suivi, entretiens, signatures, numérotation), 390 | axe `scrollable-region-focusable` | Corrigé pour `ui/table` et `DataTable` ; reste ~15 conteneurs `<div class="overflow-x-auto">` à traiter (ouvert) |
| Basse | `/missions/:id/etapes/:numero`, rai | Avertissement React « deux enfants avec la même clé » (un id d'étape) | Ouvert (cause non localisée) |
| Basse | Mission, audite1 : `/modifier`, `/etapes`, `/suivi`, `/plan-actions`, `/documents/:id` | Erreurs 403 en console (appels API non autorisés pour l'audité) | Ouvert |
| Basse | Utilisateurs, admin | « DAI (inconnue du référentiel) » : direction non présente au référentiel (donnée) | Ouvert (donnée) |

Validés sans défaut : lien d'évitement (premier Tab, cible `#contenu`), ordre de tabulation et focus visible (outline 2 px ou ring), tiroir mobile (rôle dialog, Échap, retour du focus), piège de focus des dialogues, menu utilisateur, page 403 « Accès refusé », impression A4 du programme (en-tête ONEA, menu masqué), mouvement réduit (aucune animation en cours), dates fr-FR (jj/mm/aaaa, « Lundi 2 novembre 2026 »). axe : plus de violation serious/critical hors points ouverts ci-dessus.

## Propositions (non réalisées)

- Référentiel : le h2 « Cartographies » répète l'onglet actif et le fil d'Ariane ; envisager de le retirer.
- Tableau de bord RAI : « Actions par direction » apparaît deux fois (carte puis graphique) ; fusionner.
- DataTable : l'en-tête n'est plus collant à la page (le conteneur défile) ; si le collant est requis, prévoir un défilement latéral uniquement sous 1024 px.
- Remplacer les `<div class="overflow-x-auto">` ad hoc par un composant unique focalisable.
- Mode sombre : jetons présents (`tokens.css`) mais non activés par la préférence système ; décider de l'exposer ou de les retirer.
- Page `/erreur` et URL inconnue hors session : renvoient à la connexion ; prévoir une page 404 dédiée pour l'utilisateur connecté (le comportement connecté n'a pas été capturé).

## Captures (docs/recette/captures-qa/)

Préfixe `avant-` : état avant correctif. `dialogue-creation-plan-1440.jpg`, `signatures-390.jpg`, `impression-programme-a4.jpg` : états conformes de référence.
