# Gabarits Word ONEA non reçus

Au 28/10/2026, 22 fichiers du recueil de besoins ne sont pas parvenus à IKA SOLUTION : ils
correspondent aux 20 documents « à récupérer » ci-dessous (le rapport d'orientation et le
programme de vérification ont chacun deux variantes, soit 20 + 2 = 22 fichiers). Ce fichier
est le suivi de ces gabarits, jusqu'à leur téléchargement depuis OneDrive.

Écart de comptage : `docs/domaine/documents-mission.md` recense 23 documents (20 « à
récupérer » et 3 « disponibles »), soit 25 fichiers avec les variantes, et non 27 comme
l'indiquent le plan et la décision D15 du lot 4. Les deux fichiers manquants dans le décompte
sont à identifier avec l'ONEA ; la liste ci-dessous fait foi pour les 22 fichiers à récupérer.

Tant que le modèle officiel n'est pas déposé, la plateforme génère un **gabarit provisoire**
construit depuis le contrat de balises du type (bandeau « GABARIT PROVISOIRE — en attente du
modèle officiel ONEA »). Le maître d'ouvrage accepte ces gabarits provisoires (ou vierges)
jusqu'à la récupération des 22 fichiers réels.

Liste de référence : `docs/domaine/documents-mission.md`. Les codes de contrat des documents
dont le lot consommateur n'est pas encore réalisé sont indicatifs et seront confirmés à la
création du contrat.

| N° | Document | Variantes | Contrat (code) | Lot consommateur | Statut |
|---|---|---|---|---|---|
| 1 | Ordre de mission | 1 | `ORDRE_MISSION` | 4 | provisoire livré (contrat v1, `gabarits_provisoires --installer`) |
| 2 | Déclaration d'indépendance collaborateur | 1 | `DECLARATION_INDEPENDANCE` | 5 | provisoire |
| 3 | Fiche de suivi de la mission | 1 | `FICHE_SUIVI` | 5 | provisoire |
| 4 | PV d'ouverture | 1 | `PV_OUVERTURE` | 4 | provisoire livré (contrat v1, `gabarits_provisoires --installer`) |
| 5 | Questionnaire de prise de connaissance | 1 | `QUESTIONNAIRE_PRISE_CONNAISSANCE` | 5 | provisoire |
| 6 | Planning des entretiens | 1 | `PLANNING_ENTRETIENS` | 5 | provisoire |
| 7 | Note de synthèse entretiens | 1 | `NOTE_SYNTHESE_ENTRETIENS` | 5 | provisoire |
| 8 | Grille de séparation des tâches | 1 | `GRILLE_SEPARATION_TACHES` | 5 | provisoire |
| 9 | Questionnaire de contrôle interne (QCI) | 1 | `QCI` | 5 | provisoire |
| 10 | Matrice d'analyse des risques et contrôles (MARC) | 1 | `MARC` | 5 | provisoire |
| 11 | Tableau des forces et faiblesses | 1 | `FORCES_FAIBLESSES` | 5 | provisoire |
| 12 | Rapport d'orientation | 2 | `RAPPORT_ORIENTATION` | 6 | provisoire |
| 13 | Programme de travail | 1 | `PROGRAMME_TRAVAIL` | 6 | provisoire |
| 14 | Programme de vérification | 2 | `PROGRAMME_VERIFICATION` | 6 | provisoire |
| 15 | Feuille de couverture de test | 1 | `FEUILLE_COUVERTURE` | 7 | provisoire |
| 16 | Feuille de travail | 1 | `FEUILLE_TRAVAIL` | 7 | provisoire |
| 17 | PV de clôture | 1 | `PV_CLOTURE` | 8 | provisoire |
| 18 | Plan d'actions de mise en œuvre des recommandations | 1 | `PLAN_ACTIONS` | 8 | provisoire |
| 19 | Rapport | 1 | `RAPPORT` | 8 | provisoire |
| 20 | Note synthétique | 1 | `NOTE_SYNTHETIQUE` | 8 | provisoire |

Statuts possibles : « provisoire » (gabarit généré par la plateforme) ou « officiel reçu »
(modèle ONEA déposé et activé).

## Procédure de substitution d'un gabarit provisoire par le modèle officiel

1. Ouvrir la page du contrat dans `docs/documents/contrats/<CODE>.md` : elle liste toutes
   les balises autorisées avec leur description.
2. Dans le modèle officiel ONEA (Word ou LibreOffice, enregistré au format `.docx`),
   poser les balises du contrat : `{{ mission.titre }}` pour une valeur, trois lignes de
   tableau `{%tr for l in liste %}` / `{{ l.champ }}` / `{%tr endfor %}` pour une liste.
   Chaque balise doit être saisie d'un seul trait, sans changement de mise en forme au milieu.
3. Se connecter en tant qu'administrateur, déposer le fichier pour le type de document
   concerné : la plateforme vérifie le format, l'absence de macros, la syntaxe, les balises
   connues et un rendu d'essai avec des données d'exemple. Corriger le fichier selon les
   erreurs affichées, puis le déposer à nouveau.
4. Activer la version déposée : elle remplace le gabarit provisoire, qui est archivé.
   Les documents déjà générés ne changent pas ; les générations suivantes utilisent le
   modèle officiel.
5. Passer le statut du document de ce tableau à « officiel reçu ».
