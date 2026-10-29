import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";
import type { Role } from "@/auth/types";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { MISSION_ID, pageOf, renderMission } from "../testUtils";
import type { MissionListe } from "../types";

const m = fr.missionPilotage;

const ROW = {
  id: MISSION_ID,
  reference: "DAI/2026/M01",
  titre: "Audit des achats",
  type: "ASSURANCE",
  statut: "EN_PLANIFICATION",
  phase: "PLANIFICATION",
  chef_mission: null,
  date_debut_prevue: "2026-03-02",
  date_fin_prevue: "2026-05-29",
  etape_courante: { numero: 2, romain: "II" },
  ma_declaration_en_attente: true,
} satisfies MissionListe;

function serve(results: MissionListe[], seen: string[] = []) {
  server.use(
    http.get(`${API_URL}/api/v1/missions/`, ({ request }) => {
      seen.push(new URL(request.url).search);
      return HttpResponse.json(pageOf(results));
    }),
  );
}

describe("MissionListPage", () => {
  it.each<[Role, string]>([
    ["RAI", m.emptyRai],
    ["AUDITEUR", m.emptyAuditeur],
    ["AUDITE", m.emptyAudite],
  ])("shows the empty state of %s", async (role, text) => {
    serve([]);
    renderMission("/missions", role);
    expect(await screen.findByText(text)).toBeInTheDocument();
    const create = screen.queryAllByRole("link", { name: m.createMission });
    expect(create.length > 0).toBe(role === "RAI");
  });

  it("lists missions with the pending-declaration badge", async () => {
    serve([ROW]);
    renderMission("/missions", "AUDITEUR");
    expect(await screen.findByRole("link", { name: "DAI/2026/M01" })).toBeInTheDocument();
    expect(screen.getByText(m.pendingDeclaration)).toBeInTheDocument();
    expect(screen.getByText("02/03/2026")).toBeInTheDocument();
    expect(screen.getByText("29/05/2026")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: m.createMission })).not.toBeInTheDocument();
  });

  it("reflects filters in the URL and the request, and debounces the search", async () => {
    const seen: string[] = [];
    serve([ROW], seen);
    const { router } = renderMission("/missions", "RAI");
    await screen.findByRole("link", { name: "DAI/2026/M01" });

    await userEvent.selectOptions(screen.getByLabelText(fr.missions.filterStatus), "SUSPENDUE");
    await userEvent.selectOptions(screen.getByLabelText(fr.missions.filterType), "CONSEIL");
    await waitFor(() => expect(router.state.location.search).toContain("statut=SUSPENDUE"));
    expect(router.state.location.search).toContain("type=CONSEIL");

    const before = seen.length;
    await userEvent.type(screen.getByLabelText(m.searchLabel), "achats");
    expect(router.state.location.search).not.toContain("q=");
    await waitFor(() => expect(router.state.location.search).toContain("q=achats"));
    // une seule requête pour toute la saisie, pas une par lettre
    await waitFor(() => expect(seen.at(-1)).toContain("q=achats"));
    expect(seen.length - before).toBeLessThanOrEqual(2);
    expect(seen.at(-1)).toContain("statut=SUSPENDUE");
  });

  it("shows an error alert instead of the empty state when loading fails", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/missions/`, () => HttpResponse.json({}, { status: 500 })),
    );
    renderMission("/missions", "RAI");
    expect(await screen.findByRole("alert")).toHaveTextContent(fr.missions.loadError);
  });

  it("has no accessibility violation", async () => {
    serve([ROW]);
    const { container } = renderMission("/missions", "RAI");
    await screen.findByRole("link", { name: "DAI/2026/M01" });
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
