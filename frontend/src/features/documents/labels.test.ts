import { describe, expect, it } from "vitest";
import {
  gabaritLabel,
  isInProgress,
  STATUT_GABARIT_LABELS,
  STATUT_GENERATION_LABELS,
  STATUT_PDF_LABELS,
} from "./labels";

describe("document labels", () => {
  it("covers every enumeration with non-empty French text", () => {
    for (const map of [STATUT_GENERATION_LABELS, STATUT_PDF_LABELS, STATUT_GABARIT_LABELS]) {
      expect(Object.keys(map).length).toBeGreaterThan(0);
      for (const v of Object.values(map)) expect(v.length).toBeGreaterThan(0);
    }
    expect(STATUT_GENERATION_LABELS.EN_COURS).toBe("Génération en cours…");
  });

  it("formats the template version", () => {
    expect(gabaritLabel({ version: 3, provisoire: true })).toBe("v3 · provisoire");
    expect(gabaritLabel({ version: 4, provisoire: false })).toBe("v4");
  });

  it("detects in-progress versions", () => {
    expect(isInProgress({ statut: "EN_COURS", statut_pdf: "NON_DEMANDE" })).toBe(true);
    expect(isInProgress({ statut: "PRETE", statut_pdf: "EN_COURS" })).toBe(true);
    expect(isInProgress({ statut: "PRETE", statut_pdf: "PRET" })).toBe(false);
    expect(isInProgress({ statut: "ECHEC", statut_pdf: "NON_DEMANDE" })).toBe(false);
  });
});
