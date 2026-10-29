import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { API_URL } from "@/test/msw";
import { aMission, MISSION_ID, missionHandlers, pageOf, renderMission } from "../testUtils";

const t = fr.missionTravaux;

describe("StepIIIZone", () => {
  it("requests the interviews attached to the step and announces lot 5", async () => {
    const queries: string[] = [];
    renderMission(`/missions/${MISSION_ID}/etapes/3`, "RAI", {
      handlers: [
        ...missionHandlers(aMission()),
        http.get(`${API_URL}/api/v1/interviews/`, ({ request }) => {
          queries.push(new URL(request.url).search);
          return HttpResponse.json(pageOf([]));
        }),
      ],
    });
    expect(await screen.findByText(t.stepIIILater)).toBeInTheDocument();
    expect(await screen.findByText(t.noInterview)).toBeInTheDocument();
    expect(queries[0]).toContain("etape=00000000-0000-4000-8000-000000000003");
    expect(queries[0]).toContain(`mission=${MISSION_ID}`);
  });
});
