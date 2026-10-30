import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import type { Etape } from "@/features/missions/types";
import { aMission, allSteps, missionHandlers } from "@/features/missions/testUtils";
import { API_URL, server } from "@/test/msw";
import { renderRoutes } from "@/test/shell";
import {
  ACCEPTATION_ID,
  aLigne,
  anAcceptance,
  aSummary,
  planHandlers,
  RESPONSABLE,
} from "../planTestUtils";
import { anAction, MISSION_ID } from "../testUtils";
import { PlanActionsPage } from "./PlanActionsPage";

function setup(
  options: Parameters<typeof planHandlers>[0],
  role: "AUDITEUR" | "AUDITE" | "RAI",
  statut = "EN_COURS",
) {
  const steps = allSteps((n) => (n === 16 ? { statut: statut as Etape["statut"] } : {}));
  server.use(...missionHandlers(aMission(), steps), ...planHandlers(options));
  return renderRoutes(
    [{ path: "/missions/:id/plan-actions", element: <PlanActionsPage /> }],
    role,
    {
      path: `/missions/${MISSION_ID}/plan-actions`,
    },
  );
}

describe("PlanActionsPage", () => {
  it("affiche une carte par recommandation avec ses actions", async () => {
    setup(
      {
        summary: aSummary({
          recommandations: [aLigne({ nb_actions: 1, statut_derive: "A_LANCER" })],
        }),
        actions: [anAction({ responsable_detail: RESPONSABLE, actions_possibles: ["MODIFIER"] })],
      },
      "AUDITEUR",
    );
    const card = await screen.findByRole("article", { name: "Recommandation C-01-0" });
    const table = within(card).getByRole("table");
    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((h) => h.textContent),
    ).toEqual([
      "Réf.",
      "Mesure",
      "Responsable",
      "Échéance",
      "Indicateur",
      "Moyens",
      "Statut",
      "Actions",
    ]);
    expect(within(table).getByText("Fanta Sawadogo")).toBeInTheDocument();
    expect(within(table).getByText("31/12/2026")).toBeInTheDocument();
    expect(within(card).getAllByText("À lancer")).toHaveLength(2);
  });

  it("montre à l'équipe l'engagement de chaque responsable et les avertissements", async () => {
    setup(
      {
        summary: aSummary({
          responsables: [
            {
              utilisateur: RESPONSABLE,
              nb_actions: 2,
              prochaine_echeance: "2026-12-31",
              engagement: "A_RENOUVELER",
            },
          ],
          recommandations_sans_suite: ["C-02-0"],
          engagements_manquants: ["Fanta Sawadogo"],
        }),
      },
      "AUDITEUR",
    );
    const table = await screen.findByRole("table", { name: "Engagement par responsable" });
    expect(within(table).getByText("À renouveler")).toBeInTheDocument();
    expect(screen.getByText("Recommandations sans suite : C-02-0")).toBeInTheDocument();
    expect(
      screen.getByText("Engagements manquants ou à renouveler : Fanta Sawadogo"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Confirmer mon engagement" }),
    ).not.toBeInTheDocument();
  });

  it("retire l'acceptation du risque après confirmation (RAI)", async () => {
    const user = userEvent.setup();
    let withdrawn = false;
    server.use(
      http.post(`${API_URL}/api/v1/risk-acceptances/${ACCEPTATION_ID}/withdraw/`, () => {
        withdrawn = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    setup(
      {
        summary: aSummary({
          recommandations: [
            aLigne({
              statut_derive: "RISQUE_ACCEPTE",
              acceptation: {
                id: ACCEPTATION_ID,
                auteur: 12,
                justification: "Coût disproportionné.",
              },
            }),
          ],
        }),
        acceptances: [anAcceptance()],
      },
      "RAI",
    );
    await user.click(await screen.findByRole("button", { name: "Retirer l'acceptation" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Retirer l'acceptation" }));
    await screen.findByRole("article");
    expect(withdrawn).toBe(true);
  });

  it("n'écrit rien quand l'étape XVI est terminée", async () => {
    setup({ summary: aSummary() }, "AUDITEUR", "TERMINEE");
    expect(await screen.findByText(/lecture seule/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ajouter une action" })).not.toBeInTheDocument();
  });

  it("montre l'erreur de chargement des acceptations, jamais un plan vide", async () => {
    setup({}, "AUDITEUR");
    server.use(
      http.get(`${API_URL}/api/v1/risk-acceptances/`, () =>
        HttpResponse.json({ detail: "x" }, { status: 500 }),
      ),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("Impossible de charger le plan");
  });
});
