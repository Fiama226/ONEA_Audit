import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { API_URL } from "@/test/msw";
import { aMission, MISSION_ID, missionHandlers, pageOf, renderMission } from "../testUtils";
import type { Entretien } from "../types";

const t = fr.missionTravaux;

function handlers(pendingCount: number, interviews: Entretien[] = []) {
  return [
    ...missionHandlers(aMission()),
    http.get(`${API_URL}/api/v1/meetings/`, () => HttpResponse.json(pageOf([]))),
    http.get(`${API_URL}/api/v1/interviews/`, () => HttpResponse.json(pageOf(interviews))),
    http.get(`${API_URL}/api/v1/independence-declarations/`, () =>
      HttpResponse.json({ count: pendingCount, next: null, previous: null, results: [] }),
    ),
  ];
}

const PATH = `/missions/${MISSION_ID}/etapes/2`;

describe("StepIIZone", () => {
  it("shows the opening meeting, the interviews calendar and pending declarations", async () => {
    renderMission(PATH, "RAI", { handlers: handlers(2) });
    expect(await screen.findByRole("heading", { name: t.stepIIInterviews })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Réunion d'ouverture" })).toBeInTheDocument();
    expect(
      await screen.findByText("2 déclaration(s) en attente de confirmation."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: t.declarationsLink })).toHaveAttribute(
      "href",
      `/missions/${MISSION_ID}/equipe`,
    );
  });

  it("says when every declaration is confirmed", async () => {
    renderMission(PATH, "RAI", { handlers: handlers(0) });
    expect(await screen.findByText(t.declarationsDone)).toBeInTheDocument();
  });
});
