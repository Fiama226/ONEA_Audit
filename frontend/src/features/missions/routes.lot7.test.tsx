import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
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
const COMMUNICATION = {
  phase: "COMMUNICATION",
  statut: "EN_COMMUNICATION",
  etape_courante: { numero: 16, romain: "XVI" },
} as const;
const c = fr.communication;

describe("routes du lot 7", () => {
  it.each([
    [15, c.zoneXVTitle],
    [16, c.zoneXVITitle],
    [17, c.zoneXVIITitle],
    [18, c.zoneXVIIITitle],
  ])("l'étape %i affiche sa zone", async (numero, titre) => {
    renderMission(`/missions/${MISSION_ID}/etapes/${numero}`, "RAI", {
      handlers: [...missionHandlers(aMission(COMMUNICATION), allSteps()), ...empty],
    });
    expect(await screen.findByRole("heading", { name: titre })).toBeVisible();
  });

  it("l'audité voit « Rapport provisoire » et « Plan d'actions », pas « Rapport »", async () => {
    const mission = aMission({ ...COMMUNICATION, mes_droits: allRights(false) });
    renderMission(`/missions/${MISSION_ID}/reunions`, "AUDITE", {
      handlers: [...missionHandlers(mission, allSteps()), ...empty],
    });
    expect(await screen.findByRole("link", { name: c.tabDraftResponses })).toBeVisible();
    expect(screen.getByRole("link", { name: c.tabPlanActions })).toBeVisible();
    expect(screen.queryByRole("link", { name: c.tabReport })).not.toBeInTheDocument();
  });

  it("l'équipe voit « Rapport » et « Plan d'actions », pas « Rapport provisoire »", async () => {
    renderMission(`/missions/${MISSION_ID}/reunions`, "AUDITEUR", {
      handlers: [...missionHandlers(aMission(COMMUNICATION), allSteps()), ...empty],
    });
    expect(await screen.findByRole("link", { name: c.tabReport })).toBeVisible();
    expect(screen.getByRole("link", { name: c.tabPlanActions })).toBeVisible();
    expect(screen.queryByRole("link", { name: c.tabDraftResponses })).not.toBeInTheDocument();
  });

  it("n'ouvre ces onglets qu'à partir de la phase Communication", async () => {
    renderMission(`/missions/${MISSION_ID}/reunions`, "RAI", {
      handlers: [...missionHandlers(aMission(), allSteps()), ...empty],
    });
    expect(await screen.findByRole("link", { name: fr.missions.tabConstats })).toBeVisible();
    expect(screen.queryByRole("link", { name: c.tabReport })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: c.tabPlanActions })).not.toBeInTheDocument();
  });

  it.each([
    ["rapport", c.reportPageTitle],
    ["plan-actions", c.planActionsTitle],
    ["reponses-rapport", c.draftResponsesTitle],
  ])("la route %s existe", async (chemin, titre) => {
    renderMission(`/missions/${MISSION_ID}/${chemin}`, "RAI", {
      handlers: [...missionHandlers(aMission(COMMUNICATION), allSteps()), ...empty],
    });
    expect(await screen.findByRole("heading", { name: titre })).toBeVisible();
  });
});
