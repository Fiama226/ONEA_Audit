import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { aMission, allRights, allSteps, MISSION_ID, renderMission } from "../testUtils";

const m = fr.missionPilotage;
const HASH = "3f2a" + "0".repeat(56) + "9c1b";

describe("StepIZone", () => {
  it("issues the order after confirmation, then shows the issued banner", async () => {
    let issued = false;
    let posted = 0;
    const base = aMission({
      reference: "DAI/2026/M01",
      objectifs: "Évaluer la passation des marchés.",
      mes_droits: { ...allRights(false), emettre_ordre: true, modifier: true, voir_travaux: true },
    });
    const issuedMission = aMission({
      ...base,
      ordre_mission: {
        id: "c1",
        type_document: "ORDRE_MISSION",
        signataire: { id: 1, nom_complet: "Awa Ouedraogo" },
        confirme_le: "2026-03-05T09:30:00Z",
        empreinte: HASH,
      },
      mes_droits: { ...allRights(false), voir_travaux: true },
    });
    server.use(
      http.get(`${API_URL}/api/v1/missions/${MISSION_ID}/`, () =>
        HttpResponse.json(issued ? issuedMission : base),
      ),
      http.get(`${API_URL}/api/v1/mission-steps/`, () =>
        HttpResponse.json(allSteps((n) => (n === 1 ? { statut: "EN_COURS" } : {}))),
      ),
      http.post(`${API_URL}/api/v1/missions/${MISSION_ID}/issue-order/`, async ({ request }) => {
        // The API refuses the call without the explicit confirmation flag.
        expect(await request.json()).toEqual({ confirme: true });
        issued = true;
        posted += 1;
        return HttpResponse.json(issuedMission);
      }),
    );
    renderMission(`/missions/${MISSION_ID}/etapes/1`, "RAI");

    expect(await screen.findByText("Évaluer la passation des marchés.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: m.stepIEdit })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: m.issueOrder }));
    expect(await screen.findByText(/Je soussigné\(e\) Awa Ouedraogo/)).toBeInTheDocument();
    expect(posted).toBe(0);
    // dialogue ouvert compris (le contenu du dialogue est dans un portail du body)
    const results = await axe(document.body, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);

    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: m.issueOrderConfirm }));
    expect(
      await screen.findByText("Ordre de mission émis le 05/03/2026 par Awa Ouedraogo"),
    ).toBeInTheDocument();
    expect(posted).toBe(1);
    expect(screen.getByText("Empreinte : 3f2a…9c1b")).toBeInTheDocument();
    expect(screen.getByText(m.orderWordLater)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: m.issueOrder })).not.toBeInTheDocument();
  });

  it("offers no emission button without the server right", async () => {
    const mission = aMission({ mes_droits: { ...allRights(false), voir_travaux: true } });
    server.use(
      http.get(`${API_URL}/api/v1/missions/${MISSION_ID}/`, () => HttpResponse.json(mission)),
      http.get(`${API_URL}/api/v1/mission-steps/`, () => HttpResponse.json(allSteps())),
    );
    renderMission(`/missions/${MISSION_ID}/etapes/1`, "AUDITEUR");
    expect(await screen.findByText(m.issueOrderPending)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: m.issueOrder })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: m.stepIEdit })).not.toBeInTheDocument();
  });
});
