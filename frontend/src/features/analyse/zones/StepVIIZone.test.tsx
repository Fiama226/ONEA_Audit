import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, type RequestHandler } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { aMission, aStep } from "@/features/missions/testUtils";
import { API_URL, server } from "@/test/msw";
import { aFramework, analyseRights, anObjective, ANALYSE_MISSION_ID } from "../testUtils";
import type { RapportOrientation } from "../types";
import { StepVIIZone } from "./StepVIIZone";

const NO_CONTRAST = { rules: { "color-contrast": { enabled: false } } };

function report(overrides: Partial<RapportOrientation> = {}): RapportOrientation {
  return {
    mission: ANALYSE_MISSION_ID,
    variante: "COMPLET",
    contexte: "",
    approche: "",
    observations: "",
    couverture_ordre: "",
    justification_couverture: "",
    rappel_ordre: {
      objectifs: "Évaluer les achats",
      perimetre: "Direction générale",
      exclusions: "",
      clients: "",
      livrables_attendus: "",
    },
    etape_close: false,
    ...overrides,
  } satisfies RapportOrientation;
}

function page<T>(results: T[]) {
  return { count: results.length, next: null, previous: null, results };
}

function setup({
  statut = "VALIDE",
  editable = true,
  handlers = [],
  rapport = report(),
}: {
  statut?: "BROUILLON" | "VALIDE";
  editable?: boolean;
  handlers?: RequestHandler[];
  rapport?: RapportOrientation;
} = {}) {
  server.use(
    http.get(`${API_URL}/api/v1/audit-frameworks/${ANALYSE_MISSION_ID}/`, () =>
      HttpResponse.json(
        aFramework({
          statut,
          mes_droits: analyseRights({ voir_travaux: true, contribuer_vii: editable }),
        }),
      ),
    ),
    http.get(`${API_URL}/api/v1/audit-objectives/`, () =>
      HttpResponse.json(page([anObjective({ libelle: "Vérifier les rapprochements" })])),
    ),
    http.get(`${API_URL}/api/v1/orientation-reports/${ANALYSE_MISSION_ID}/`, () =>
      HttpResponse.json(rapport),
    ),
    ...handlers,
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <StepVIIZone mission={aMission({ id: ANALYSE_MISSION_ID })} step={aStep({ numero: 7 })} />
    </QueryClientProvider>,
  );
}

describe("StepVIIZone", () => {
  it("shows only the alert when the framework is not validated", async () => {
    setup({ statut: "BROUILLON" });
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Le référentiel d'audit doit être validé (jalon VI) avant de sélectionner les objectifs d'audit.",
    );
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByText("Rapport d'orientation")).not.toBeInTheDocument();
  });

  it("initializes the objectives with POST audit-objectives/initialize/", async () => {
    let body: unknown;
    const user = userEvent.setup();
    setup({
      handlers: [
        http.post(`${API_URL}/api/v1/audit-objectives/initialize/`, async ({ request }) => {
          body = await request.json();
          return HttpResponse.json([], { status: 201 });
        }),
      ],
    });
    await user.click(
      await screen.findByRole("button", { name: "Proposer un objectif par contrôle clé" }),
    );
    await waitFor(() => expect(body).toEqual({ mission: ANALYSE_MISSION_ID }));
  });

  it("sends the non-test decision and blocks an empty justification", async () => {
    let body: unknown;
    const user = userEvent.setup();
    setup({
      handlers: [
        http.patch(`${API_URL}/api/v1/audit-objectives/:id/`, async ({ request }) => {
          body = await request.json();
          return HttpResponse.json(anObjective({ retenu: false }));
        }),
      ],
    });
    await user.click(
      await screen.findByRole("button", { name: "Ne pas tester le contrôle de OA-01" }),
    );
    const dialog = await screen.findByRole("dialog");
    await user.selectOptions(
      within(dialog).getByLabelText("Motif de non-test"),
      "AUTRES_CONTROLES",
    );
    await user.click(within(dialog).getByRole("button", { name: "Confirmer le non-test" }));
    expect(
      await within(dialog).findByText("La justification est obligatoire."),
    ).toBeInTheDocument();
    expect(body).toBeUndefined();
    await user.type(within(dialog).getByLabelText("Justification"), "Couvert par la DAF");
    await user.click(within(dialog).getByRole("button", { name: "Confirmer le non-test" }));
    await waitFor(() =>
      expect(body).toEqual({
        retenu: false,
        motif_non_test: "AUTRES_CONTROLES",
        justification: "Couvert par la DAF",
      }),
    );
  });

  it("blocks a partial coverage without justification", async () => {
    let called = false;
    const user = userEvent.setup();
    setup({
      handlers: [
        http.patch(`${API_URL}/api/v1/orientation-reports/${ANALYSE_MISSION_ID}/`, () => {
          called = true;
          return HttpResponse.json(report());
        }),
      ],
    });
    await user.selectOptions(
      await screen.findByLabelText("Couverture de l'ordre de mission"),
      "PARTIELLE",
    );
    await user.click(screen.getByRole("button", { name: "Enregistrer le rapport d'orientation" }));
    expect(
      await screen.findByText(/Une justification est obligatoire hors couverture exacte/),
    ).toBeInTheDocument();
    expect(called).toBe(false);
  });

  it("puts a server 422 on the field and focuses it", async () => {
    const user = userEvent.setup();
    setup({
      handlers: [
        http.patch(`${API_URL}/api/v1/orientation-reports/${ANALYSE_MISSION_ID}/`, () =>
          HttpResponse.json(
            {
              detail: "Données invalides.",
              errors: { justification_couverture: ["Justification refusée."] },
            },
            { status: 422 },
          ),
        ),
      ],
    });
    await user.click(
      await screen.findByRole("button", { name: "Enregistrer le rapport d'orientation" }),
    );
    const field = await screen.findByLabelText("Justification de la couverture");
    await waitFor(() => expect(field).toHaveFocus());
    expect(field).toHaveAccessibleDescription("Justification refusée.");
  });

  it("is read-only without the contribuer_vii right", async () => {
    setup({ editable: false });
    await screen.findByRole("table");
    expect(screen.queryByRole("button", { name: /Ne pas tester/ })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Proposer un objectif par contrôle clé" }),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("Contexte")).toBeDisabled();
  });

  it("has no axe violation", async () => {
    const { container } = setup();
    await screen.findByRole("table");
    expect((await axe(container, NO_CONTRAST)).violations).toEqual([]);
  });
});
