import type { GovernanceRule } from "./api";

const VALUES: Record<string, Record<string, unknown>> = {
  program_approval: { approver: "DG_AND_BOARD", required_before_launch: true },
  risk_acceptance_escalation: { low: "RAI", medium: "RAI", high: "DG" },
  objectivity_check: { enabled: true, mode: "BLOCK", cooling_off_months: 12 },
  program_risk_link: { required: true },
  auditee_response: {
    delay_days: 15,
    waiver_by: "RAI",
    reason_required: true,
    evidence_agreement: true,
    findings_agreed: true,
    response_or_deadline: true,
  },
  step_order: { mode: "STRICT" },
  search_fallback: { scope: "MISSIONS" },
  auditee_step_read: { allowed: true },
};

const LABELS: Record<string, string> = {
  program_approval: "Approbation du programme annuel",
  risk_acceptance_escalation: "Escalade d'une acceptation de risque",
  objectivity_check: "Contrôle d'objectivité",
  program_risk_link: "Lien programme ↔ risque",
  auditee_response: "Réponse de l'audité",
  step_order: "Ordre des étapes",
  search_fallback: "Repli de la recherche",
  auditee_step_read: "Lecture des étapes par l'audité",
};

/** Une règle à sa valeur de référence ; `valeur` partielle surcharge les champs donnés. */
export function aRule(
  cle: string,
  overrides: Partial<Omit<GovernanceRule, "valeur">> & { valeur?: Record<string, unknown> } = {},
): GovernanceRule {
  const defaut = VALUES[cle] ?? {};
  const { valeur, ...rest } = overrides;
  return {
    cle,
    libelle: LABELS[cle] ?? cle,
    description: `Description de ${cle}.`,
    reference: "Normes IIA 2024",
    issue_des_normes: cle === "program_approval" || cle === "objectivity_check",
    valeur: { ...defaut, ...valeur },
    defaut,
    assouplie: false,
    modifie_le: null,
    modifie_par: null,
    motif: "",
    ...rest,
  };
}

export function allRules(changes: Record<string, Partial<GovernanceRule>> = {}): GovernanceRule[] {
  return Object.keys(VALUES).map((cle) => aRule(cle, changes[cle] as Parameters<typeof aRule>[1]));
}
