import type { ActionCorrective } from "./types";

export { MISSION_ID, pageOf, renderCommunication as renderPlan } from "../communication/testUtils";

export const ACTION_ID = "cccccccc-3333-4333-8333-cccccccccccc";
export const RECOMMANDATION_ID = "dddddddd-4444-4444-8444-dddddddddddd";

/** Action corrective à lancer, forme figée par le contrat du lot 7 (`Action`). */
export function anAction(overrides: Partial<ActionCorrective> = {}): ActionCorrective {
  return {
    id: ACTION_ID,
    mission: "11111111-1111-4111-8111-111111111111",
    recommandation: RECOMMANDATION_ID,
    constat_reference: "C-01",
    reference: "A-01",
    libelle: "Formaliser le rapprochement mensuel",
    responsable: 12,
    responsable_detail: null,
    echeance: "2026-12-31",
    indicateur: "Rapprochements signés",
    moyens: "",
    ordre: 0,
    statut: "A_LANCER",
    proposee_par: 12,
    actions_possibles: [],
    ...overrides,
  } as ActionCorrective;
}
