import { describe, expect, it } from "vitest";
import { StepVIIZone } from "@/features/analyse/zones/StepVIIZone";
import { StepVIZone } from "@/features/analyse/zones/StepVIZone";
import { StepVZone } from "@/features/analyse/zones/StepVZone";
import { GenericZone } from "./GenericZone";
import { ZONE_COMPLEMENTS, ZONES } from "./index";

describe("zone registry", () => {
  it("registers the analysis zones for steps V to VII", () => {
    expect(ZONES[5]).toBe(StepVZone);
    expect(ZONES[6]).toBe(StepVIZone);
    expect(ZONES[7]).toBe(StepVIIZone);
  });

  it("registers the step III complement", () => {
    expect(ZONE_COMPLEMENTS[3]).toBeDefined();
    expect(ZONE_COMPLEMENTS[4]).toBeUndefined();
  });

  it("registers the accomplishment zones", () => {
    for (const numero of [8, 9, 10, 12, 13, 14]) expect(ZONES[numero]).toBeDefined();
  });

  it("leaves other steps to the generic zone", () => {
    expect(ZONES[11] ?? GenericZone).toBe(GenericZone);
    expect(ZONES[15] ?? GenericZone).toBe(GenericZone);
  });
});
