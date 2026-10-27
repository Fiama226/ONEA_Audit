---
name: charte-graphique
description: Charte graphique et règles de design de la plateforme ONEA Audit (institutionnel, sobre, moderne). À lire avant toute maquette, tout composant UI ou toute revue visuelle.
---

# Charte graphique (résumé opérationnel)

Document complet : `docs/design/charte-graphique.md`. Tokens CSS : `frontend/src/styles/tokens.css`.

## Les cinq règles
1. **Institutionnel d'abord** : l'écran doit pouvoir être projeté devant un Directeur
   Général sans faire amateur. Grille stricte, alignements parfaits, pas de décoration.
2. **Couleur = information** : bleu primaire pour agir, cyan pour l'état courant, vert /
   orange / rouge uniquement pour des statuts. Tout le reste est neutre.
3. **Densité maîtrisée** : un auditeur consulte des tableaux longs ; lignes 44 px, en-têtes
   collants, chiffres tabulaires, colonnes masquables.
4. **Tout s'imprime** : documents, rapports, matrices ont un style print propre.
5. **Français exact** : vocabulaire IFACI/IIA, vouvoiement, boutons à l'infinitif.

## Check-list avant livraison d'un écran
- [ ] tokens uniquement, aucune couleur en dur
- [ ] contraste AA vérifié
- [ ] états vide / chargement / erreur présents
- [ ] navigation clavier et focus visibles
- [ ] responsive 1280 / 1024 / tablette ; mobile en lecture seule acceptable
- [ ] style print si l'écran est un document
- [ ] revue par `ui-designer`
