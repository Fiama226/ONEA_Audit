import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { API_URL } from "@/test/msw";
import {
  allRights,
  allSteps,
  aMission,
  missionHandlers,
  MISSION_ID,
  pageOf,
  renderMission,
} from "./testUtils";

const empty = ["interviews", "independence-declarations", "meetings"].map((path) =>
  http.get(`${API_URL}/api/v1/${path}/`, () => HttpResponse.json(pageOf([]))),
);

describe("routes du lot 6", () => {
  it("l'étape 12 affiche la zone des tests complémentaires", async () => {
    renderMission(`/missions/${MISSION_ID}/etapes/12`, "RAI", {
      handlers: [...missionHandlers(aMission(), allSteps()), ...empty],
    });
    expect(await screen.findByRole("heading", { name: "Tests complémentaires" })).toBeVisible();
  });

  it("l'étape 14 affiche la zone des constats", async () => {
    renderMission(`/missions/${MISSION_ID}/etapes/14`, "RAI", {
      handlers: [...missionHandlers(aMission(), allSteps()), ...empty],
    });
    expect(await screen.findByRole("heading", { name: "Constats" })).toBeVisible();
  });

  it("l'audité voit l'onglet Constats et pas Étapes", async () => {
    const mission = aMission({ mes_droits: allRights(false) });
    renderMission(`/missions/${MISSION_ID}/reunions`, "AUDITE", {
      handlers: [...missionHandlers(mission, allSteps()), ...empty],
    });
    expect(await screen.findByRole("link", { name: "Constats" })).toBeVisible();
    expect(screen.queryByRole("link", { name: "Étapes" })).not.toBeInTheDocument();
  });

  it("la route constats/:id et fiches/:id existent", async () => {
    renderMission(`/missions/${MISSION_ID}/fiches/abc`, "RAI", {
      handlers: [...missionHandlers(aMission(), allSteps()), ...empty],
    });
    expect(await screen.findByRole("heading", { name: "Fiche de test" })).toBeVisible();
  });
});
