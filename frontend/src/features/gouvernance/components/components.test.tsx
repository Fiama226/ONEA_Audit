import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { API_URL, server } from "@/test/msw";
import { renderWithAuth } from "@/test/shell";
import type { PendingAcceptance, PendingWaiver } from "../api";
import { allRules } from "../testUtils";
import { GovernanceDecisions } from "./GovernanceDecisions";
import { RelaxedRulesCard } from "./RelaxedRulesCard";

const RULES = `${API_URL}/api/v1/governance-rules/`;
const ACCEPTANCES = `${API_URL}/api/v1/risk-acceptance-validations/`;
const WAIVERS = `${API_URL}/api/v1/auditee-response-waivers/`;

const acceptance: PendingAcceptance = {
  id: "a1",
  mission_id: "m1",
  mission_reference: "DAI/2026/M03",
  mission_titre: "Audit des achats",
  constat_reference: "C-02",
  constat_titre: "Rapprochements absents",
  recommandation: "Mettre en place un rapprochement mensuel",
  niveau_risque: "ELEVE",
  justification: "Coût disproportionné",
  auteur: {
    id: 9,
    username: "audite1",
    nom_complet: "Issa Kaboré",
    role: "AUDITE",
    direction_code: "DAF",
    fonction: "",
  },
  acceptee_le: "2026-10-01T08:00:00Z",
  validation_requise: "BOARD",
};

const waiver: PendingWaiver = {
  etape: "e14",
  numero: 14,
  romain: "XIV",
  mission_id: "m1",
  mission_reference: "DAI/2026/M03",
  mission_titre: "Audit des achats",
  manquants: ["L'audité n'a pas donné sa position sur le constat C-01."],
};

describe("RelaxedRulesCard", () => {
  it("says when every rule is at its reference value", async () => {
    server.use(http.get(RULES, () => HttpResponse.json(allRules())));
    renderWithAuth(<RelaxedRulesCard />, "DG");
    expect(
      await screen.findByText("Toutes les règles de gouvernance sont à leur valeur de référence."),
    ).toBeInTheDocument();
  });

  it("lists relaxed rules, norm-derived first, with the reason", async () => {
    server.use(
      http.get(RULES, () =>
        HttpResponse.json(
          allRules({
            step_order: { assouplie: true, motif: "Pilote" },
            program_approval: { assouplie: true, motif: "Conseil non réuni" },
          } as never),
        ),
      ),
    );
    renderWithAuth(<RelaxedRulesCard />, "ADMIN");
    const items = await screen.findAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Approbation du programme annuel (issue des normes)");
    expect(items[0]).toHaveTextContent("Conseil non réuni");
    expect(items[1]).toHaveTextContent("Ordre des étapes");
  });
});

describe("GovernanceDecisions", () => {
  it("lets the DG record the board decision on a risk acceptance", async () => {
    let body: unknown = null;
    server.use(
      http.get(ACCEPTANCES, () => HttpResponse.json([acceptance])),
      http.get(WAIVERS, () => HttpResponse.json([])),
      http.post(`${ACCEPTANCES}a1/decide/`, async ({ request }) => {
        body = await request.json();
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderWithAuth(<GovernanceDecisions />, "DG");
    expect(
      await screen.findByText("Constat C-02 (mission DAI/2026/M03), risque élevé"),
    ).toBeInTheDocument();
    expect(screen.getByText("Décision du Conseil, enregistrée par le DG.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Valider" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(
      within(dialog).getByLabelText("Référence de la délibération du Conseil"),
      "Délibération 7",
    );
    await userEvent.type(within(dialog).getByLabelText("Motif de la décision"), "Risque toléré");
    await userEvent.click(within(dialog).getByRole("button", { name: "Valider" }));
    await screen.findByText("Constat C-02 (mission DAI/2026/M03), risque élevé");
    expect(body).toEqual({
      decision: "VALIDEE",
      motif: "Risque toléré",
      reference_conseil: "Délibération 7",
    });
  });

  it("lets the RAI waive a step blocked by a missing auditee response", async () => {
    let body: unknown = null;
    server.use(
      http.get(ACCEPTANCES, () => HttpResponse.json([])),
      http.get(WAIVERS, () => HttpResponse.json([waiver])),
      http.post(`${WAIVERS}e14/waive/`, async ({ request }) => {
        body = await request.json();
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderWithAuth(<GovernanceDecisions />, "RAI");
    expect(await screen.findByText(/Mission DAI\/2026\/M03, étape XIV/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Déroger" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Motif de la décision"), "Audité absent");
    await userEvent.click(within(dialog).getByRole("button", { name: "Déroger" }));
    await screen.findByText(/Mission DAI\/2026\/M03, étape XIV/);
    expect(body).toEqual({ motif: "Audité absent" });
  });

  it("renders nothing for other roles", () => {
    const { container } = renderWithAuth(<GovernanceDecisions />, "AUDITEUR");
    expect(container).toBeEmptyDOMElement();
  });
});
