/**
 * Force des contrôles, pour avertir avant d'enregistrer un assouplissement. Reprend l'ordre du
 * service `regles_gouvernance` (le serveur reste seul juge : il exige le motif et notifie).
 * Valeurs d'une énumération : de la plus faible à la plus forte ; booléen : vrai est plus fort ;
 * entier : plus grand est plus fort. Champ absent : sans effet sur la force du contrôle.
 */
const ORDERS: Record<string, Record<string, readonly string[] | "bool" | "int">> = {
  program_approval: {
    approver: ["NONE", "DG", "DG_AND_BOARD"],
    required_before_launch: "bool",
  },
  risk_acceptance_escalation: {
    low: ["NONE", "RAI", "DG", "BOARD"],
    medium: ["NONE", "RAI", "DG", "BOARD"],
    high: ["NONE", "RAI", "DG", "BOARD"],
  },
  objectivity_check: { enabled: "bool", mode: ["WARN", "BLOCK"], cooling_off_months: "int" },
  program_risk_link: { required: "bool" },
  auditee_response: {
    delay_days: "int",
    waiver_by: ["RAI", "DG"],
    reason_required: "bool",
    evidence_agreement: "bool",
    findings_agreed: "bool",
    response_or_deadline: "bool",
  },
  step_order: { mode: ["FREE", "STRICT"] },
};

function rank(order: readonly string[] | "bool" | "int", value: unknown): number {
  if (order === "bool") return value === true ? 1 : 0;
  if (order === "int") return typeof value === "number" ? value : 0;
  return order.indexOf(String(value));
}

/** Vrai si au moins un champ passe à un contrôle plus faible. */
export function weakens(
  rule: string,
  before: Record<string, unknown>,
  after: Record<string, unknown>,
): boolean {
  const orders = ORDERS[rule] ?? {};
  return Object.entries(orders).some(
    ([field, order]) => rank(order, after[field]) < rank(order, before[field]),
  );
}
