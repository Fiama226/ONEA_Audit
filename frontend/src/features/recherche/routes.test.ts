import { describe, expect, it } from "vitest";
import { routeFor } from "./routes";

const base = { objet_id: "obj", mission_id: "mid", etape: null };

describe("routeFor", () => {
  it("mène une mission à sa fiche", () => {
    expect(routeFor({ ...base, type: "MISSION" })).toBe("/missions/obj");
  });
  it("mène un constat à sa page dans la mission", () => {
    expect(routeFor({ ...base, type: "CONSTAT" })).toBe("/missions/mid/constats/obj");
  });
  it("mène une recommandation au registre filtré", () => {
    expect(routeFor({ ...base, type: "RECOMMANDATION" })).toBe(
      "/recommandations?recommandation=obj",
    );
  });
  it("mène une action à sa page de suivi", () => {
    expect(routeFor({ ...base, type: "ACTION" })).toBe("/recommandations/actions/obj");
  });
  it("mène un document à l'étape de la mission", () => {
    expect(routeFor({ ...base, type: "DOCUMENT", etape: 14 })).toBe("/missions/mid/etapes/14");
  });
  it("ne produit jamais de chemin invalide sans mission", () => {
    expect(routeFor({ ...base, type: "CONSTAT", mission_id: null })).toBe("/missions");
    expect(routeFor({ ...base, type: "DOCUMENT", mission_id: null })).toBe("/documents");
  });
});
