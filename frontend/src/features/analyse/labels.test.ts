import { describe, expect, it } from "vitest";
import {
  COUVERTURE_ORDRE_LABELS,
  ROLE_TACHE_CODES,
  STATUT_REFERENTIEL_LABELS,
  TYPE_QUESTIONNAIRE_LABELS,
} from "./labels";

describe("analyse labels", () => {
  it("covers every enum value with a non-empty French label", () => {
    for (const map of [
      COUVERTURE_ORDRE_LABELS,
      STATUT_REFERENTIEL_LABELS,
      TYPE_QUESTIONNAIRE_LABELS,
    ]) {
      for (const label of Object.values(map)) expect(label.length).toBeGreaterThan(0);
    }
    expect(Object.keys(STATUT_REFERENTIEL_LABELS)).toEqual([
      "BROUILLON",
      "SOUMIS",
      "RENVOYE",
      "VALIDE",
      "A_REVALIDER",
    ]);
  });

  it("codes the task roles E, A, En, C", () => {
    expect(Object.values(ROLE_TACHE_CODES)).toEqual(["E", "A", "En", "C"]);
  });
});
