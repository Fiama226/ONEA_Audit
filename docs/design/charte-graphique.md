# Charte graphique — Plateforme Audit Interne ONEA

Positionnement : outil institutionnel d'une société d'État, utilisé quotidiennement par
des auditeurs. Il doit inspirer rigueur et confiance, rester agréable et moderne, et
s'imprimer proprement. Référence d'ambiance : interfaces de type gouvernement numérique
(design systems de l'État français, GOV.UK) mais avec la couleur de l'eau.

Hypothèse à valider avec l'ONEA : les couleurs ci-dessous sont dérivées de l'identité
visuelle publique (bleu eau). Si une charte officielle existe, ses valeurs remplacent celles-ci.

## Couleurs (tokens)

| Token | Clair | Sombre | Usage |
|---|---|---|---|
| `--primary` | #0B4F8A (bleu eau profond) | #5BA4E6 | actions principales, liens, en-têtes actifs |
| `--primary-foreground` | #FFFFFF | #06243F | texte sur primaire |
| `--brand-accent` | #0EA5B7 (cyan eau) | #22C3D6 | accents, graphiques, étape courante |
| `--background` | #F7F9FB | #0F1720 | fond de page |
| `--surface` | #FFFFFF | #16212C | cartes, tableaux |
| `--foreground` | #1B2733 | #E6EDF3 | texte principal |
| `--text-muted` | #5B6B7A | #93A3B3 | texte secondaire, libellés |
| `--surface-subtle` | #EBF0F4 | #1F2C39 | survol, sélection, squelettes (mappé sur `--accent`/`--muted` de shadcn) |
| `--border` | #D9E1E8 | #2A3745 | bordures, séparateurs |
| `--success` | #1E8E5A | #3CCB86 | validé, clôturé |
| `--warning` | #C47A00 | #F0B23C | en attente, échéance proche |
| `--danger` | #B42318 | #F0655C | rejeté, en retard, risque élevé |
| `--risk-low` | #CFE8D8 | — | cellules matrice, score 1–7 |
| `--risk-medium` | #FFE8B3 | — | score 8–14 |
| `--risk-high` | #F8C9C4 | — | score 15–25 |
| `--risk-foreground` | #1B2733 | #1B2733 | texte des cellules de risque (les teintes restent claires en sombre) |
| `--input-border` | #7F8F9E | #5F7385 | contour des champs de saisie (3:1, WCAG 1.4.11) |
| `--success-text` | #16794C | = `--success` | texte de statut « succès » (4,5:1 sur blanc) |
| `--warning-text` | #8F5A00 | = `--warning` | texte de statut « alerte » (4,5:1 sur blanc) |
| `--shadow-floating` | 0 1px 2px / 0 12px 32px -8px, noir 6 % / 18 % | noir 50 % / 60 % | unique ombre : menus, infobulles, tiroir, dialogues |
| `--overlay` | rgb(15 23 32 / .48) | rgb(0 0 0 / .6) | voile du tiroir et des dialogues |

Contraste minimum AA (4.5:1) pour tout texte. Le cyan n'est jamais utilisé pour du texte sur fond clair.

## Typographie
- Famille : **Inter** (SIL Open Font License), fallback system-ui. Chiffres tabulaires
  dans les tableaux et scores.
- Échelle : 12 / 14 (corps) / 16 / 20 / 24 / 32. Titres de page 24 semi-bold, titres de
  section 16 semi-bold majuscules espacées pour les en-têtes de fiche.
- Interligne 1.5 pour le corps, 1.25 pour les titres.

## Espacement et grille
Base 4 px. Rythme : 8 / 12 / 16 / 24 / 32 / 48. Conteneur 1280 px max, marges 24 px.
Sidebar 260 px fixe (repliable à 64 px), header 56 px.

## Composants et motifs
- **Coins** : 6 px (boutons, champs), 8 px (cartes). Jamais de pilule sauf badges de statut.
- **Ombres** : une seule, très légère, sur les surfaces flottantes (menus, dialogues).
- **Badges de statut** : fond teinté + texte foncé, point coloré à gauche, libellé en français.
- **Stepper de mission** : les 18 étapes IFACI groupées par phase, étape courante en accent,
  étapes validées avec coche, étapes verrouillées grisées.
- **Matrice des risques 5×5** : grille carrée, axes « Probabilité » / « Impact »,
  cellules teintées par niveau, codes de risque cliquables.
- **Tableaux** : lignes 44 px, en-tête collant, zébrage très léger, actions en fin de ligne.
- **Formulaires** : labels au-dessus, aide sous le champ, erreurs en rouge sous le champ,
  sections séparées par un titre et une ligne. Bouton principal unique par formulaire.
- **Documents** : prévisualisation A4 dans un cadre blanc sur fond gris, en-tête ONEA,
  numéro de version et statut dans un bandeau.
- **Vide / erreur** : illustration sobre monochrome, une phrase, une action.

## Graphiques
Primitives dans `frontend/src/components/charts` (aucune bibliothèque de graphique).
- **Palette** : `--chart-1` (série unique, bleu primaire), `--chart-done` (clôturé), `--chart-open` (ouvert, gris neutre),
  `--chart-late` (en retard), en clair et en sombre. Clair : #0B4F8A, #1E8E5A, #8A99A7, #B42318.
  Sombre : #5BA4E6, #2FA36B, #55606B, #E5544B. `--chart-texture` : hachures du statut « en retard ».
- **Jamais la couleur seule** : chaque série a un libellé et une icône (CheckCircle2, Circle, AlertTriangle) dans la légende,
  « en retard » est hachuré, les valeurs et totaux sont écrits en `text-foreground`, et chaque graphique offre
  un bouton « Afficher le tableau » (vrai `<table>` avec `caption`).
- **Contraste** : texte ≥ 4,5:1 ; `--chart-1`, `--chart-done`, `--chart-late` ≥ 3:1 sur `--surface` (testé).
  Le gris `--chart-open` est volontairement neutre (≈ 2,8:1) : valeurs en texte et tableau sont donc obligatoires.
- **Tracé** : marques fines (12 px), extrémité arrondie 4 px, ligne de base nette, 2 px de surface entre segments.
  Mode contraste forcé : segments bordés, « en retard » hachuré.
- **Interaction** : lignes focalisables (lien si destination), info-bulle au survol et au focus.

## Iconographie
Lucide (ISC), trait 1.5 px, taille 16 ou 20. Jamais d'emoji dans l'interface.

## Mouvement
Transitions 150 ms sur hover/focus uniquement. Aucune animation d'entrée, aucun parallaxe.

## Impression
Chaque page de document et de rapport a un style print : marges 20 mm, noir sur blanc,
en-tête avec logo ONEA et référence de mission, pied avec pagination et mention de confidentialité.

## Ton rédactionnel
Vouvoiement, phrases courtes, vocabulaire IFACI/IIA exact (constat, recommandation,
plan d'actions, référentiel d'audit). Boutons à l'infinitif (« Valider le rapport »).
