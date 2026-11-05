/**
 * Textes de l'écran « Règles de gouvernance », du journal d'audit et des décisions de
 * gouvernance. Gardés dans la fonctionnalité (chargée à la demande) pour ne pas alourdir le
 * paquet d'entrée ; les libellés de navigation restent dans `i18n/fr.ts`.
 */

export type RuleKey =
  | "program_approval"
  | "risk_acceptance_escalation"
  | "objectivity_check"
  | "program_risk_link"
  | "auditee_response"
  | "step_order"
  | "search_fallback"
  | "auditee_step_read";

type FieldText = {
  label: string;
  help?: string;
  /** Libellés des valeurs d'une énumération ; absent pour un booléen ou un entier. */
  values?: Record<string, string>;
  /** Libellés d'un booléen (vrai, faux). */
  yes?: string;
  no?: string;
  unit?: string;
};

const VALIDATORS = {
  NONE: "Aucune validation",
  RAI: "Responsable de l'audit interne",
  DG: "Direction générale",
  BOARD: "Conseil (par le DG)",
};

export const FIELDS: Record<RuleKey, Record<string, FieldText>> = {
  program_approval: {
    approver: {
      label: "Approbateur du programme annuel",
      values: {
        NONE: "Aucun (validation du RAI seule)",
        DG: "Direction générale",
        DG_AND_BOARD: "Direction générale puis Conseil",
      },
    },
    required_before_launch: {
      label: "Approbation exigée avant de lancer une mission du programme",
      yes: "Oui",
      no: "Non",
    },
  },
  risk_acceptance_escalation: {
    low: { label: "Risque faible : validé par", values: VALIDATORS },
    medium: { label: "Risque moyen : validé par", values: VALIDATORS },
    high: { label: "Risque élevé : validé par", values: VALIDATORS },
  },
  objectivity_check: {
    enabled: { label: "Contrôle actif", yes: "Activé", no: "Désactivé" },
    mode: {
      label: "En cas de situation détectée",
      values: { BLOCK: "Bloquer l'affectation", WARN: "Avertir (affectation possible)" },
    },
    cooling_off_months: {
      label: "Durée de refroidissement",
      help: "Période pendant laquelle une responsabilité ou une mission de conseil antérieure sur la même entité est signalée (0 à 60 mois).",
      unit: "mois",
    },
  },
  program_risk_link: {
    required: {
      label: "Risques couverts à désigner à la création d'une mission du programme",
      yes: "Obligatoire",
      no: "Facultatif",
    },
  },
  auditee_response: {
    delay_days: {
      label: "Délai de réponse au rapport provisoire",
      help: "Délai proposé par défaut à la transmission (1 à 60 jours).",
      unit: "jours",
    },
    waiver_by: {
      label: "Qui peut déroger à l'absence de réponse",
      values: { RAI: "Responsable de l'audit interne", DG: "Direction générale" },
    },
    reason_required: { label: "Motif de dérogation obligatoire", yes: "Oui", no: "Non" },
    evidence_agreement: {
      label: "Étape XIII : position de l'entité sur les résultats des tests",
      yes: "Exigée",
      no: "Non exigée",
    },
    findings_agreed: {
      label: "Étape XIV : position de l'audité sur chaque constat validé",
      yes: "Exigée",
      no: "Non exigée",
    },
    response_or_deadline: {
      label: "Étape XVI : réponse au rapport provisoire ou délai échu",
      yes: "Exigée",
      no: "Non exigée",
    },
  },
  step_order: {
    mode: {
      label: "Enchaînement des étapes",
      values: {
        STRICT: "Strict (dérogation motivée du RAI)",
        FREE: "Libre",
      },
    },
  },
  search_fallback: {
    scope: {
      label: "Recherche quand le moteur est indisponible",
      values: { MISSIONS: "Missions seules", MISSIONS_AND_FINDINGS: "Missions et constats" },
    },
  },
  auditee_step_read: {
    allowed: {
      label: "L'audité lit les étapes de sa mission",
      yes: "Autorisé",
      no: "Non autorisé",
    },
  },
};

/** Valeur lisible d'un champ de règle. */
export function formatValue(rule: string, field: string, value: unknown): string {
  const text = FIELDS[rule as RuleKey]?.[field];
  if (typeof value === "boolean") return value ? (text?.yes ?? "Oui") : (text?.no ?? "Non");
  if (typeof value === "number") return text?.unit ? `${value} ${text.unit}` : String(value);
  if (typeof value === "string") return text?.values?.[value] ?? value;
  return "—";
}

export function fieldLabel(rule: string, field: string): string {
  return FIELDS[rule as RuleKey]?.[field]?.label ?? field;
}

export const t = {
  rules: {
    title: "Règles de gouvernance",
    help: "Règles métier paramétrées par l'administrateur. Les valeurs de référence sont les plus prudentes (Normes IIA 2024, fiches IFACI). Une règle ne s'applique qu'aux actions faites après son changement, jamais aux dossiers clos.",
    readOnly:
      "Lecture seule : seul l'administrateur de la plateforme modifie ces règles (droit non délégable).",
    loadError: "Impossible de charger les règles de gouvernance.",
    normBadge: "Issue des normes",
    relaxedBadge: "Assouplie",
    reference: "Référence",
    current: "Valeur en vigueur",
    defaultValue: "Valeur de référence",
    lastChange: (name: string, date: string) => `Modifiée le ${date} par ${name}`,
    neverChanged: "Valeur de référence, jamais modifiée",
    reasonOf: "Motif du dernier changement",
    edit: "Modifier",
    journalLink: "Voir le journal des changements",
    relaxedTitle: "Règles assouplies",
    relaxedNormWarning: (label: string) =>
      `La règle « ${label} », issue des normes, est assouplie : le contrôle prévu par les Normes IIA est affaibli tant qu'elle n'est pas rétablie.`,
    relaxedOther: (label: string) => `La règle « ${label} » est assouplie.`,
    dialogTitle: (label: string) => `Modifier : ${label}`,
    reasonLabel: "Motif du changement",
    reasonHelp:
      "Obligatoire si le changement assouplit un contrôle ; le DG et le RAI en sont alors notifiés.",
    weakeningNotice:
      "Ce changement assouplit un contrôle : le motif est obligatoire, et le DG et le RAI seront notifiés.",
    save: "Enregistrer",
    unchanged: "Aucune valeur n'a changé.",
    saved: "Règle enregistrée.",
  },
  relaxed: {
    title: "Règles de gouvernance assouplies",
    none: "Toutes les règles de gouvernance sont à leur valeur de référence.",
    link: "Voir les règles",
    loadError: "Impossible de lire l'état des règles de gouvernance.",
    norm: "issue des normes",
  },
  journal: {
    title: "Journal d'audit",
    help: "Historique des créations et modifications, en lecture seule (qui, quand, valeurs avant et après, motif).",
    helpDg: "Historique des changements des règles de gouvernance, en lecture seule.",
    category: "Catégorie",
    allCategories: "Toutes les entrées",
    governance: "Règles de gouvernance",
    from: "Du",
    to: "Au",
    colDate: "Date",
    colActor: "Auteur",
    colObject: "Objet",
    colAction: "Action",
    colChanges: "Changements",
    colReason: "Motif",
    weakening: "Assouplissement",
    empty: "Aucune entrée pour ces critères.",
    loadError: "Impossible de charger le journal d'audit.",
    caption: "Entrées du journal d'audit, de la plus récente à la plus ancienne",
    system: "Système",
    previous: "Page précédente",
    next: "Page suivante",
    page: (n: number) => `Page ${n}`,
    actions: {
      create: "Création",
      update: "Modification",
      delete: "Suppression",
      access: "Consultation",
      unknown: "Autre",
    } as Record<string, string>,
    ruleObject: (key: string) => `Règle : ${RULE_LABELS[key] ?? key}`,
  },
  decisions: {
    title: "Décisions de gouvernance attendues",
    none: "Aucune décision de gouvernance n'est attendue de vous.",
    loadError: "Impossible de charger les décisions attendues.",
    acceptances: "Acceptations de risque à valider",
    acceptanceLine: (constat: string, mission: string, niveau: string) =>
      `Constat ${constat} (mission ${mission}), risque ${niveau}`,
    validate: "Valider",
    refuse: "Refuser",
    validateTitle: (constat: string) => `Valider l'acceptation du risque : constat ${constat}`,
    refuseTitle: (constat: string) => `Refuser l'acceptation du risque : constat ${constat}`,
    refuseHelp: "Un refus retire l'acceptation : la direction devra proposer des actions.",
    boardReference: "Référence de la délibération du Conseil",
    reason: "Motif de la décision",
    justification: "Justification de la direction",
    boardNote: "Décision du Conseil, enregistrée par le DG.",
    waivers: "Étapes bloquées par l'absence de réponse de l'audité",
    waiverLine: (mission: string, step: string) => `Mission ${mission}, étape ${step}`,
    waive: "Déroger",
    waiveTitle: (mission: string, step: string) =>
      `Déroger à la réponse de l'audité : mission ${mission}, étape ${step}`,
    waiveHelp:
      "La dérogation est écrite au journal de l'étape avec son motif ; elle vaut jusqu'à la réouverture de l'étape.",
    reasonRequired: "Le motif est obligatoire.",
  },
  approval: {
    title: "Approbation du programme",
    required: (who: string) => `Approbation exigée par les règles de gouvernance : ${who}.`,
    notRequired: "Les règles de gouvernance ne prévoient pas d'approbation de ce programme.",
    approved: "Programme approuvé.",
    pending: (who: string) => `En attente : ${who}.`,
    draft: "L'approbation se fait une fois le programme validé par le RAI.",
    approvers: {
      NONE: "aucune",
      DG: "Direction générale",
      DG_AND_BOARD: "Direction générale puis Conseil",
    } as Record<string, string>,
    levels: { DG: "Direction générale", BOARD: "Conseil" } as Record<string, string>,
    recordDg: "Enregistrer l'approbation de la DG",
    recordBoard: "Enregistrer la décision du Conseil",
    dgTitle: "Approbation de la Direction générale",
    boardTitle: "Décision du Conseil",
    decisionDate: "Date de la décision",
    reference: "Référence de la délibération",
    comment: "Commentaire (facultatif)",
    confirm: "Enregistrer",
    line: (level: string, name: string, date: string) => `${level} : le ${date}, par ${name}`,
  },
};

export const RULE_LABELS: Record<string, string> = {
  program_approval: "Approbation du programme annuel",
  risk_acceptance_escalation: "Escalade d'une acceptation de risque",
  objectivity_check: "Contrôle d'objectivité",
  program_risk_link: "Lien programme ↔ risque",
  auditee_response: "Réponse de l'audité",
  step_order: "Ordre des étapes",
  search_fallback: "Repli de la recherche",
  auditee_step_read: "Lecture des étapes par l'audité",
};

export const RISK_LEVELS: Record<string, string> = {
  FAIBLE: "faible",
  MOYEN: "moyen",
  ELEVE: "élevé",
};
