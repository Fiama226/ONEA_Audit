# Maquettes du lot 1 : shell applicatif et tableaux de bord

Spécification d'implémentation pour la tâche 9 (`AppShell`, `Sidebar`, `Header`,
`Breadcrumbs`, `PrintLayout`, `DashboardPage`, `EmptyState`). Les maquettes font foi pour
les mesures ; ce document fait foi pour les règles.

| Fichier | Contenu |
|---|---|
| `shell.html` | Shell en clair (ADMIN, menu utilisateur ouvert, grille), sombre, barre repliée, tablette 768 px (fermé / tiroir ouvert), impression A4 |
| `dashboards.html` | Tableaux de bord RAI, AUDITEUR, AUDITE, DG à l'état « aucune mission » |
| `screens/*.png` | Captures 1:1 de chaque variante |

Les maquettes sont autonomes (CSS en ligne, aucune ressource externe). Elles utilisent les
variables de `frontend/src/styles/tokens.css` recopiées telles quelles. Police : Inter
(chargée par `@fontsource` dans l'application ; repli système dans les maquettes).

## 1. Inventaire des composants

| Élément | Composant | shadcn / Radix | Remarques |
|---|---|---|---|
| Barre latérale | `Sidebar` | `Sidebar` (bloc shadcn) ou `aside` + `nav` maison | `collapsible="icon"` ; état persistant (`localStorage`, clé `onea.sidebar`) |
| Entrée de menu | `SidebarMenuButton` | `Sidebar` | `NavLink` de React Router, `aria-current="page"` |
| Infobulle (barre repliée) | `Tooltip` | `Tooltip` | côté droit, décalage 12 px, délai 300 ms |
| Tiroir < 1024 px | `Sheet` | `Sheet` `side="left"` | largeur 280 px ; même contenu que la barre |
| En-tête | `Header` | — | `header` natif |
| Fil d'Ariane | `Breadcrumbs` | `Breadcrumb` | `nav aria-label="Fil d'Ariane"` (`t("common.breadcrumb")`) |
| Recherche désactivée | — | `Input` `disabled` | placeholder « Recherche disponible au lot 8 » |
| Menu utilisateur | `UserMenu` | `DropdownMenu` + `Avatar` | « Se déconnecter » (`t("auth.logout")`) |
| Badge de rôle | — | `Badge` `variant="outline"` | coins 4 px (ce n'est pas un statut, donc pas de pilule) |
| Bouton | — | `Button` (`default`, `ghost`, `outline`) | |
| État vide | `EmptyState` | — | titre, phrase, une action, illustration |
| Carte | — | `Card` | jamais imbriquée |
| Tableau | — | `Table` (TanStack Table plus tard) | |
| Squelette | — | `Skeleton` | sans animation `pulse` (charte : aucune animation) |
| Matrice 5 × 5 | `RiskScaleLegend` | — | grille CSS |

## 2. Mesures

Base 4 px. Rythme 8 / 12 / 16 / 24 / 32 / 48. Corps 14 px, interligne 1.5.

### Barre latérale
- Largeur 260 px ; repliée 64 px. Fond `surface`, filet droit 1 px `border`.
- Bloc marque : hauteur **56 px** (aligné sur l'en-tête), marge latérale 20 px, filet bas.
  Pictogramme 28 × 28, coins 6 px ; « ONEA » 16 px, graisse 700, interlettrage 0,08 em ;
  « Audit interne » 12 px `text-muted`. Écart de 12 px entre pictogramme et texte.
- Navigation : marge interne 12 px. Libellés de groupe 12 px, graisse 600, majuscules,
  interlettrage 0,06 em, `text-muted`, marge interne 12 / 12 / 6 px.
  Groupes : (sans titre) Tableau de bord · **Conduite des missions** : Missions, Référentiel ·
  **Suivi** : Recommandations, Documents · **Paramétrage** : Administration.
- Entrée : hauteur 36 px, marge interne 0 12 px, coins 6 px, écart icône/texte 12 px,
  icône 20 px trait 1,5 px, texte 14 px graisse 500, espacement vertical 2 px.
- Pied : hauteur 56 px, filet haut ; « Version 0.1 · lot 1 » 12 px `text-muted` et bouton
  icône 36 × 36 « Replier le menu ».
- Repliée : entrées 40 × 40 centrées, titres de groupe remplacés par un filet 1 px
  (marge 4 / 8 / 10 px) et conservés en `sr-only` ; libellés conservés en `sr-only` ;
  bouton « Déplier le menu ».

### Visibilité par rôle
| Entrée | ADMIN | RAI | AUDITEUR | AUDITE | DG |
|---|---|---|---|---|---|
| Tableau de bord, Missions, Recommandations, Documents | oui | oui | oui | oui | oui |
| Référentiel | oui | oui | oui | non | non |
| Administration | oui | non | non | non | non |

Un groupe dont toutes les entrées sont masquées disparaît avec son titre.

### En-tête
- Hauteur 56 px, fond `surface`, filet bas `border`. Marges 32 px à gauche (alignement sur
  le titre de page) et 24 px à droite ; écart 16 px.
- Fil d'Ariane 14 px : niveaux parents `text-muted` (soulignés au survol), séparateur
  chevron 16 px `text-muted`, niveau courant `foreground` graisse 500 et
  `aria-current="page"`. Sur le tableau de bord, un seul niveau.
- Recherche : 320 × 36 px, coins 6 px, fond `surface-subtle`, sans bordure visible,
  icône 16 px, placeholder `text-muted`, curseur `not-allowed`, `disabled`.
- Séparateur vertical 1 × 24 px `border`.
- Déclencheur utilisateur : hauteur 40 px, coins 6 px ; avatar 32 px rond (initiales
  12 px graisse 600, texte `primary`, fond `primary` à 10 %, contour intérieur `primary`
  à 18 %) ; nom 14 px graisse 500 ; badge de rôle court (Administrateur, RAI, Auditeur,
  Audité, DG) 20 px de haut, 12 px, coins 4 px, fond `background`, bordure `border` ;
  chevron 16 px `text-muted`.
- Menu ouvert : largeur 296 px, à 4 px sous l'en-tête, aligné à droite ; coins 8 px,
  bordure `border`, ombre `--shadow-floating`, marge interne 4 px. Contenu : avatar 40 px,
  nom (600), adresse électronique (12 px `text-muted`) ; ligne « Rôle » + libellé long ;
  séparateur ; « Se déconnecter » (36 px, icône `log-out`) ; séparateur ; « Dernière
  connexion le JJ/MM/AAAA à HH:MM » 12 px `text-muted` (heure `Africa/Ouagadougou`).

### Zone principale
- Marges 32 px (24 px sous 1024 px), bas 48 px. Conteneur 1280 px maximum, centré.
- Grille 12 colonnes, gouttière 24 px. Cartes alignées en haut (`items-start`).
- En-tête de page : titre 24 px graisse 600, interligne 1,25, interlettrage −0,012 em ;
  sous-titre 14 px `text-muted` (« {rôle long} · Programme {année} ») ; à droite la date
  du jour 12 px `text-muted` avec icône calendrier. Marge basse 24 px.

### Tableaux de bord (état « aucune mission »)
- `EmptyState` : carte `surface`, bordure `border`, coins 8 px, marge interne 40 / 48 px,
  grille `1fr 320px`, écart 48 px. Titre 20 px graisse 600 « Aucune mission pour le
  moment » (identique pour les quatre rôles) ; phrase 14 px `text-muted`, 58 caractères
  de mesure maximum ; une seule action.
- Action principale désactivée + pastille « Disponible au lot N » (24 px, 12 px graisse
  500, bordure pointillée `border`, coins 4 px, fond `background`, icône horloge),
  reliée au bouton par `aria-describedby`. Une `Tooltip` au survol est facultative : la
  pastille reste visible car une infobulle sur bouton désactivé n'est pas accessible au
  clavier ni au toucher.

| Rôle | Titre de page | Action | Lot |
|---|---|---|---|
| RAI | Pilotage de l'audit interne | Créer une mission | 3 |
| AUDITEUR | Mes travaux d'audit | Consulter mes missions | 3 |
| AUDITE | Mes constats et actions | Consulter mes recommandations | 8 |
| DG | Synthèse de l'audit interne | Consulter les rapports diffusés | 7 |

- Illustration : SVG monochrome `primary` 320 × 176 (goutte et quatre ondes
  concentriques, opacités de trait 0,5 / 0,32 / 0,18 / 0,09), `aria-hidden`. Masquée sous
  1024 px. À placer dans `src/components/illustrations/WaterRipple.tsx`.
- Aperçu structurel « Ce que vous suivrez ici » (titre de section 16 px graisse 600, note
  12 px `text-muted` à droite) : cartes transparentes (fond de page) avec bordure, en-tête
  de carte 52 px, `aria-hidden="true"`. Valeurs affichées « — » en `text-muted`, chiffres
  tabulaires. Squelettes 8 px de haut, coins 2 px, `border` à 75 % ; lignes 2 et 3 des
  tableaux à 70 % et 40 % d'opacité.
  - RAI : Missions par phase (8 col., trois phases avec une graduation par étape, jalons
    plus foncés) ; Jalons à valider (4 col., VI, X, XIII, XVIII) ; Recommandations en
    retard (8 col.) ; Échelle de criticité 5 × 5 (4 col., réelle, non estompée).
  - AUDITEUR : bandeau de trois indicateurs ; « Mes étapes en cours » avec la frise des
    18 étapes (cercle = étape, losange = jalon validé par le RAI) et un tableau.
  - AUDITE : bandeau de trois indicateurs ; « Mes constats et actions » (8 col.) ;
    « Votre rôle dans le suivi » (4 col., trois étapes numérotées, contenu réel).
  - DG : bandeau de trois indicateurs ; « Taux de mise en œuvre » (5 col., valeur 32 px,
    barre segmentée 8 px aux teintes de statut à 32 %) ; « Derniers rapports diffusés »
    (7 col.).
- Bandeau d'indicateurs : une seule carte à trois cellules séparées par des filets
  (pas trois cartes identiques). Libellé 12 px 500, valeur 24 px 600, pied 12 px.
- Tableaux : en-tête 40 px (12 px graisse 600 `text-muted`), lignes 44 px, filets
  `border`, marges de cellule 20 px, colonnes numériques alignées à droite.
- Matrice : cellules carrées, écart 3 px, coins 3 px, score 12 px graisse 500 tabulaire
  en `--risk-foreground` ; axes 12 px `text-muted` ; « Probabilité » vertical, « Impact »
  horizontal ; largeur maximale 272 px ; légende Faible 1 à 7, Moyen 8 à 14, Élevé 15 à 25.

### Rayons, filets, ombres
- 6 px : boutons, champs, entrées de menu. 8 px : cartes, menus déroulants, `EmptyState`.
  4 px : badges de rôle, codes d'étape, pastilles. Pilule : badges de statut et avatar.
- Filets : 1 px `border` partout. Aucune bordure latérale colorée de plus de 1 px, sauf
  l'indicateur d'entrée active (3 × 20 px).
- Ombre : `--shadow-floating` uniquement sur menus, infobulles, tiroir, dialogues.

## 3. Utilisation des tokens

| Élément | Token(s) |
|---|---|
| Fond d'application | `background` |
| Barre latérale, en-tête, cartes pleines, menus | `surface` + `border` |
| Texte principal | `foreground` |
| Texte secondaire, libellés, icônes au repos | `text-muted` |
| Survol neutre, recherche désactivée, bouton désactivé | `surface-subtle` |
| Entrée active : fond / texte et icône | `primary` à 10 % (`bg-primary/10`) / `primary` |
| Indicateur d'entrée active | `brand-accent` (3 × 20 px, jamais du texte) |
| Bouton principal | `primary` / `primary-foreground` ; survol `primary` mêlé à 12 % de `foreground` |
| Anneau de focus | `ring` (= `primary`) |
| Avatar | `primary` sur `primary` à 10 % |
| Infobulle | fond `foreground`, texte `surface` |
| Matrice | `risk-low`, `risk-medium`, `risk-high`, texte `--risk-foreground` |
| Statuts (pastille + point) | `success`, `warning`, `danger` à 14 % pour le fond, point plein, texte `foreground` |
| Voile du tiroir | `--overlay` |

## 4. États

| État | Règle |
|---|---|
| Survol | entrée de menu, bouton fantôme, déclencheur utilisateur : fond `surface-subtle` ; icône de menu passe à `foreground` ; liens du fil d'Ariane soulignés (décalage 3 px) |
| Focus clavier | `outline` 2 px `ring`, décalage 2 px, sur tout élément focalisable (`focus-visible` uniquement) |
| Actif (page courante) | fond `primary` 10 %, texte `primary` graisse 600, indicateur `brand-accent` collé au bord gauche de la barre |
| Désactivé | fond `surface-subtle`, bordure `border`, texte `text-muted`, curseur `not-allowed`, pas d'opacité globale |
| Transitions | 150 ms sur `background-color`, `color`, `border-color` ; rien d'autre |

## 5. Responsive

| Largeur | Barre latérale | En-tête |
|---|---|---|
| ≥ 1280 px | dépliée par défaut (choix utilisateur mémorisé) | complet |
| 1024 à 1279 px | repliée par défaut (64 px) | recherche réduite à 240 px |
| < 1024 px | masquée ; `Sheet` 280 px ouvert par le bouton menu, voile `--overlay`, fermeture par « Fermer le menu », Échap ou clic sur le voile | bouton menu + marque compacte ; recherche en bouton icône désactivé ; avatar seul (nom et rôle dans `aria-label`) ; fil d'Ariane masqué |

Sous 1024 px : toutes les cartes passent sur 12 colonnes, l'illustration de l'état vide est
masquée, la frise des étapes s'empile par phase, les tableaux défilent horizontalement.
Mobile : lecture seule acceptable (charte).

## 6. Impression (`PrintLayout`)

- `@page { size: A4 portrait; margin: 20mm 20mm 16mm; }`.
- Masquer barre latérale, en-tête, actions et éléments `aria-hidden` décoratifs
  (`print:hidden`). Noir sur blanc : `foreground` sur `surface`, aucun fond coloré
  sauf la matrice (`print-color-adjust: exact`).
- En-tête répété : pictogramme ONEA monochrome 24 px, « ONEA » 12 px graisse 700, ligne
  « Office National de l'Eau et de l'Assainissement · Département Audit Interne » 11 px ;
  à droite, référence de mission, type de document, version et statut (11 px, chiffres
  tabulaires) ; filet bas 1 px `foreground`.
- Pied : filet haut 1 px `border`, 10 px ; à gauche « CONFIDENTIEL · USAGE INTERNE ONEA »
  (graisse 600, majuscules) ; au centre « Imprimé le JJ/MM/AAAA à HH:MM par {initiale}.
  {nom} » ; à droite « Page N sur M » via `counter(page)` / `counter(pages)` dans
  `@page { @bottom-right { … } }`. Si le navigateur ne prend pas en charge les marges de
  page, en-tête et pied en `position: fixed` et pagination omise à l'écran.

## 7. Tokens proposés (absents de `tokens.css`, à valider)

| Nom | Clair | Sombre | Pourquoi |
|---|---|---|---|
| `--shadow-floating` | `0 1px 2px rgb(16 24 40 / .06), 0 12px 32px -8px rgb(16 24 40 / .18)` | `0 1px 2px rgb(0 0 0 / .5), 0 12px 32px -8px rgb(0 0 0 / .6)` | la charte prévoit « une seule ombre » sans la définir |
| `--risk-foreground` | `#1B2733` | `#1B2733` | les teintes de risque restent claires en sombre : le texte des cellules doit rester foncé (10,2:1 sur `risk-high`) |
| `--overlay` | `rgb(15 23 32 / .48)` | `rgb(0 0 0 / .6)` | voile du tiroir et des dialogues |
| `--input-border` | `#7F8F9E` | `#5F7385` | `border` (1,32:1) est insuffisant pour délimiter un champ actif (WCAG 1.4.11 : 3:1). Valeurs : 3,32:1 sur `surface` clair, 3,32:1 sur `surface` sombre |
| `--success-text` | `#16794C` | (= `success`) | `success` sur blanc = 4,14:1, insuffisant pour du texte ; proposé : 5,42:1 |
| `--warning-text` | `#8F5A00` | (= `warning`) | `warning` sur blanc = 3,43:1 ; proposé : 5,78:1 |

Les deux derniers ne servent pas au lot 1 ; ils seront nécessaires aux badges de statut.

## 8. Contrastes vérifiés (texte, AA 4,5:1)

Mesurés dans le navigateur sur toutes les variantes (aucun échec) et recalculés à partir
des tokens :

| Couple | Clair | Sombre |
|---|---|---|
| `foreground` / `background` | 14,37 | 15,27 |
| `foreground` / `surface` | 15,17 | 13,80 |
| `text-muted` / `background` | 5,20 | 6,99 |
| `text-muted` / `surface` | 5,48 | 6,31 |
| `text-muted` / `surface-subtle` (recherche, bouton désactivé) | 4,78 | 5,50 |
| `primary` / `surface` | 8,40 | 6,13 |
| `primary-foreground` / `primary` (bouton) | 8,40 | 5,93 |
| `primary` / entrée active (`primary` 10 %) | 7,12 | 5,21 |
| `surface` / `foreground` (infobulle) | 15,17 | 13,80 |
| `foreground` / `risk-low`, `risk-medium`, `risk-high` | 11,69 / 12,60 / 10,21 | idem via `--risk-foreground` |

`brand-accent` sur clair = 2,96:1 : jamais utilisé pour du texte, seulement pour
l'indicateur actif et la vague du pictogramme.
