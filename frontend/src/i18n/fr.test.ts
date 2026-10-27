import { describe, expect, it } from "vitest";
import { fr, t } from "./fr";

describe("t", () => {
  it("resolves a dotted key to its French label", () => {
    expect(t("common.save")).toBe(fr.common.save);
    expect(t("nav.missions")).toBe("Missions");
  });
});
