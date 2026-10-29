import { describe, expect, it } from "vitest";
import {
  ACTION_LABELS,
  PHASE_LABELS,
  ROLE_MISSION_LABELS,
  STATUT_DECLARATION_LABELS,
  STATUT_ENTRETIEN_LABELS,
  STATUT_ETAPE_LABELS,
  STATUT_MISSION_LABELS,
  TYPE_MISSION_LABELS,
  TYPE_REUNION_LABELS,
} from "./labels";

describe("labels", () => {
  it("covers every enumeration with non-empty French text", () => {
    const maps = [
      STATUT_MISSION_LABELS,
      STATUT_ETAPE_LABELS,
      PHASE_LABELS,
      ACTION_LABELS,
      TYPE_MISSION_LABELS,
      ROLE_MISSION_LABELS,
      STATUT_DECLARATION_LABELS,
      STATUT_ENTRETIEN_LABELS,
      TYPE_REUNION_LABELS,
    ];
    for (const map of maps) {
      for (const label of Object.values(map)) expect(label.length).toBeGreaterThan(0);
    }
    expect(Object.keys(STATUT_MISSION_LABELS)).toHaveLength(10);
    expect(Object.keys(STATUT_ETAPE_LABELS)).toHaveLength(7);
  });

  it("uses the prescribed step action wording", () => {
    expect(ACTION_LABELS.DEMARRER).toBe("Commencer l'étape");
    expect(ACTION_LABELS.TERMINER).toBe("Terminer l'étape");
    expect(ACTION_LABELS.VALIDER).toBe("Valider le jalon");
    expect(ACTION_LABELS.RENVOYER).toBe("Renvoyer");
    expect(ACTION_LABELS.ROUVRIR).toBe("Rouvrir l'étape");
    expect(ACTION_LABELS.NON_APPLICABLE).toBe("Marquer non applicable");
    expect(ACTION_LABELS.RETABLIR).toBe("Rétablir l'étape");
  });
});
