import { describe, expect, it } from "vitest";
import { ROLES } from "@/auth/types";
import { canEditCartographie, canEditStructure } from "./permissions";

describe("referentiel permissions", () => {
  it("allows structure edits to RAI and ADMIN only", () => {
    expect(ROLES.filter(canEditStructure)).toEqual(["ADMIN", "RAI"]);
    expect(canEditStructure("ADMIN")).toBe(true);
    expect(canEditStructure(null)).toBe(false);
  });
  it("allows cartographie edits to RAI only", () => {
    expect(ROLES.filter(canEditCartographie)).toEqual(["RAI"]);
    expect(canEditCartographie("ADMIN")).toBe(false);
    expect(canEditCartographie(null)).toBe(false);
  });
});
