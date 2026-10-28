import { describe, expect, it } from "vitest";
import { INTERVENTION_TYPE_LABELS, MONTH_LABELS, PLAN_STATUS_LABELS, quarterLabel } from "./labels";

describe("programmation labels", () => {
  it("formats quarters in French", () => {
    expect(quarterLabel(1)).toBe("1er trimestre");
    expect(quarterLabel(2)).toBe("2e trimestre");
    expect(quarterLabel(4)).toBe("4e trimestre");
  });

  it("labels statuses and intervention types", () => {
    expect(PLAN_STATUS_LABELS).toEqual({ BROUILLON: "Brouillon", VALIDE: "Validé" });
    expect(INTERVENTION_TYPE_LABELS).toEqual({ ASSURANCE: "Assurance", CONSEIL: "Conseil" });
  });

  it("has twelve month labels", () => {
    expect(MONTH_LABELS).toHaveLength(12);
    expect(MONTH_LABELS[0]).toBe("janv.");
    expect(MONTH_LABELS[11]).toBe("déc.");
  });
});
