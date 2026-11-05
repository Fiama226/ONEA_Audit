import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { API_URL, server } from "@/test/msw";
import { renderWithAuth } from "@/test/shell";
import { aPlan, PLAN_ID } from "../testUtils";
import { PlanApprovalPanel } from "./PlanApprovalPanel";

const validated = aPlan({
  statut: "VALIDE",
  valide_le: "2026-01-10T08:00:00Z",
  valide_par: { id: 3, username: "rai", nom_complet: "Responsable Audit" },
});

describe("PlanApprovalPanel", () => {
  it("lets the DG record his approval of a validated programme", async () => {
    let body: unknown = null;
    server.use(
      http.post(`${API_URL}/api/v1/audit-plans/${PLAN_ID}/approve/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(validated);
      }),
    );
    renderWithAuth(<PlanApprovalPanel plan={validated} />, "DG");
    expect(
      screen.getByText(
        "Approbation exigée par les règles de gouvernance : Direction générale puis Conseil.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("En attente : Direction générale, Conseil.")).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Enregistrer l'approbation de la DG" }),
    );
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Commentaire (facultatif)"), "Vu.");
    await userEvent.click(within(dialog).getByRole("button", { name: "Enregistrer" }));
    await screen.findByText("En attente : Direction générale, Conseil.");
    expect(body).toEqual({ niveau: "DG", date_decision: null, reference: "", commentaire: "Vu." });
  });

  it("asks the board reference once the DG has approved", async () => {
    const plan = aPlan({
      ...validated,
      approbation: {
        approbateur: "DG_AND_BOARD",
        requise: true,
        approuve: false,
        manquantes: ["BOARD"],
        approbations: [
          {
            niveau: "DG",
            niveau_libelle: "Direction générale",
            approuve_par: { id: 5, nom_complet: "Directeur Général" },
            approuve_le: "2026-01-12T08:00:00Z",
            date_decision: "2026-01-12",
            reference: "",
            commentaire: "",
          },
        ],
      },
    });
    renderWithAuth(<PlanApprovalPanel plan={plan} />, "DG");
    expect(
      screen.getByText(/Direction générale : le 12\/01\/2026, par Directeur Général/),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Enregistrer la décision du Conseil" }),
    );
    expect(
      within(await screen.findByRole("dialog")).getByLabelText("Référence de la délibération"),
    ).toBeInTheDocument();
  });

  it("shows the state without any action to the RAI", () => {
    renderWithAuth(<PlanApprovalPanel plan={validated} />, "RAI");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.getByText("En attente : Direction générale, Conseil.")).toBeInTheDocument();
  });
});
