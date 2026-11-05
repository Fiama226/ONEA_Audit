# Règles de gouvernance paramétrables

Branche `feat/regles-gouvernance`. Réponse aux décisions métier 1 à 8 de l'audit UX
(`corrections-audit-ux.md`, section 3) et aux écarts IIA 2.2, 9.4, 11.5 et IFACI D1 à D3.

## Principe

- Un service unique, `apps/gouvernance/regles_gouvernance.py`, porte les huit règles : clés et
  valeurs en anglais dans le code, libellés en français dans l'interface. Les autres applications
  ne lisent les règles que par ses accesseurs typés (`step_order_strict()`, `objectivity()`…).
- Stockage : `RegleGouvernance` (clé, valeur JSON, motif), une ligne par règle modifiée ; absence
  de ligne = valeur de référence. Une valeur stockée invalide retombe sur la référence (journalisé).
- Cache partagé (`django.core.cache`), invalidé immédiatement et à la validation de la transaction ;
  cache indisponible = lecture en base.
- Écriture : ADMIN actif seulement, relu en base (`delegation.est_administrateur`) ; aucune
  délégation ne donne ce droit. Validation stricte : champs inconnus, énumérations, bornes, escalade
  croissante avec le niveau de risque.
- Piste d'audit : django-auditlog (avant, après, acteur, date) + `additional_data` (motif,
  assouplissement). Le journal d'audit l'expose (filtre `categorie=gouvernance`) ; le DG n'y lit que
  ces entrées.
- Assouplissement : un champ passe à un contrôle plus faible (ordre de force par champ, les choix
  « neutres » n'en ont pas). Motif obligatoire, notification au DG et au RAI, bandeau permanent et
  encadré des tableaux de bord ADMIN et DG tant que la règle reste en deçà de sa référence. Les règles
  issues des normes (objectivité, approbation du programme) sont signalées comme telles.
- Non-rétroactivité : la règle est lue au moment de l'action ; l'autorité de validation d'une
  acceptation de risque est figée à sa création ; les missions closes sont figées par ailleurs.

## Règles et branchements

| Règle (clé) | Référence | Branchement |
|---|---|---|
| `program_approval` | DG puis Conseil ; exigée avant lancement | `ApprobationProgramme` (ajout seul) ; `lancer_mission` d'une mission « programme annuel » |
| `risk_acceptance_escalation` | faible, moyen : RAI ; élevé : DG | `AcceptationRisque.validation_requise` figée, `ValidationAcceptation` (ajout seul), contrôle XVI |
| `objectivity_check` | activé, blocage, 12 mois | `affecter`, `remplacer_chef`, `emettre_ordre_mission` ; `AffectationMission.alerte_objectivite` |
| `program_risk_link` | obligatoire | `Mission.risques_couverts` exigé à la création d'une mission « programme annuel » |
| `auditee_response` | 15 j ; dérogation RAI ; motif ; 3 contrôles | `AccordResultats` (XIII), positions sur constats (XIV), réponses au provisoire (XVI) ; dérogation = `EvenementEtape` DEROGATION |
| `step_order` | strict | `predecesseurs_ouverts` |
| `search_fallback` | missions | repli de `rechercher` (constats : mêmes droits que la revérification) |
| `auditee_step_read` | autorisée | `EtapeViewSet.initial` |

## Écarts assumés (minimum utile)

- **Conseil** : aucun compte ni rôle. Le DG enregistre la décision du Conseil (date et référence de
  la délibération) pour l'approbation du programme et pour une acceptation de risque.
- **Lien programme ↔ risque** : porté par la mission (« risques couverts »), pas par la ligne du
  programme (une ligne validée est figée en base) ; aucun lien mission ↔ ligne de programme.
- **Objectivité** : contrôles systématiques sur les données présentes (direction du compte,
  affectations antérieures) ; une responsabilité antérieure hors plateforme reste déclarative.
- **Dérogation du DG** : depuis son tableau de bord (file des étapes bloquées), le DG n'ayant pas
  accès aux missions. La dérogation vaut pour toute l'étape (tous ses contrôles « audité »).
- **Rapport final** : la mention « Sans réponse dans le délai » n'est pas ajoutée.
