import { describe, expect, it } from "vitest";
import { safeReturnPath } from "./safePath";

describe("safeReturnPath", () => {
  it.each(["//evil.com", "/\\evil.com", "https://evil.com", "javascript:alert(1)", "/\t/evil.com"])(
    "rejette %s",
    (bad) => {
      expect(safeReturnPath(bad)).toBe("/");
    },
  );

  it("conserve un chemin relatif valide", () => {
    expect(safeReturnPath("/missions?x=1")).toBe("/missions?x=1");
  });
});
