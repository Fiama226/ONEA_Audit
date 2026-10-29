import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { MISSION_ID, pageOf } from "@/features/missions/testUtils";
import type { RisqueMission } from "@/features/missions/types";
import { API_URL, server } from "@/test/msw";
import { DRAFT, mockReferentiel, renderCarto, VALIDATED } from "../cartoFixtures";
import { RiskMapDetailPage } from "../pages/RiskMapDetailPage";

const routes = [{ path: "/referentiel/cartographies/:id", element: <RiskMapDetailPage /> }];

const PROPOSED = {
  id: "mr-9",
  mission: MISSION_ID,
  mission_reference: "DAI/2026/M01",
  risque_source: null,
  code_source: "",
  nouveau: true,
  processus: "p-1",
  processus_code: "12-FEP",
  libelle: "Risque de fraude interne",
  description: "",
  probabilite: 3,
  impact: 5,
  score: 15,
  niveau: "ELEVE",
  commentaire: "",
  probabilite_reference: null,
  impact_reference: null,
} satisfies RisqueMission;

function proposeRisks(seen: string[] = []) {
  server.use(
    http.get(`${API_URL}/api/v1/mission-risks/`, ({ request }) => {
      seen.push(new URL(request.url).search);
      return HttpResponse.json(pageOf([PROPOSED]));
    }),
  );
  return seen;
}

describe("ProposedRisksPanel", () => {
  it("lists the risks proposed by missions on a draft map, read-only, with a link to the mission", async () => {
    mockReferentiel();
    const seen = proposeRisks();
    const { container } = renderCarto(routes, "RAI", `/referentiel/cartographies/${DRAFT.id}`);
    const panel = await screen.findByRole("region", {
      name: "Risques proposés par les missions (1)",
    });
    const row = within(panel).getByRole("row", { name: /Risque de fraude interne/ });
    expect(within(row).getByRole("link", { name: "DAI/2026/M01" })).toHaveAttribute(
      "href",
      `/missions/${MISSION_ID}`,
    );
    expect(within(row).getByText("12-FEP")).toBeInTheDocument();
    expect(within(row).getByText("3×5")).toBeInTheDocument();
    expect(within(row).getByText("Élevé")).toBeInTheDocument();
    expect(within(panel).queryByRole("button")).not.toBeInTheDocument();
    expect(seen.some((s) => s.includes("nouveau=true"))).toBe(true);
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });

  it("is absent on a validated map", async () => {
    mockReferentiel({ map: VALIDATED });
    proposeRisks();
    renderCarto(routes, "RAI", `/referentiel/cartographies/${VALIDATED.id}`);
    await screen.findByText(/Cartographie.*2025/);
    expect(screen.queryByText(/Risques proposés par les missions/)).not.toBeInTheDocument();
  });

  it("is absent for a role that cannot edit the map", async () => {
    mockReferentiel();
    proposeRisks();
    renderCarto(routes, "AUDITEUR", `/referentiel/cartographies/${DRAFT.id}`);
    await screen.findByText(/Cartographie.*2026/);
    expect(screen.queryByText(/Risques proposés par les missions/)).not.toBeInTheDocument();
  });
});
