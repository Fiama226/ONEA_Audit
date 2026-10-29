import { describe, expect, it } from "vitest";
import { ROLES } from "@/auth/types";
import { canEditAuditPlan, canReadAuditPlan } from "./permissions";

describe("programmation permissions", () => {
  it("only RAI can edit", () => {
    expect(canEditAuditPlan("ADMIN")).toBe(false);
    expect(canEditAuditPlan("RAI")).toBe(true);
    expect(canEditAuditPlan(null)).toBe(false);
    expect(ROLES.filter(canEditAuditPlan)).toEqual(["RAI"]);
  });

  it("ADMIN, RAI, AUDITEUR and DG can read; AUDITE and anonymous cannot", () => {
    expect(ROLES.filter(canReadAuditPlan).sort()).toEqual(["ADMIN", "AUDITEUR", "DG", "RAI"]);
    expect(canReadAuditPlan("AUDITE")).toBe(false);
    expect(canReadAuditPlan(null)).toBe(false);
  });
});
