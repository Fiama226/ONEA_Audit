import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, type RequestHandler } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { aMission, aStep } from "@/features/missions/testUtils";
import { API_URL, server } from "@/test/msw";
import { aFramework, analyseRights, anObjective, ANALYSE_MISSION_ID } from "../testUtils";
import type { ObjectifAudit, RapportOrientation } from "../types";
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
  objectives = [anObjective({ libelle: "Vérifier les rapprochements" })],
}: {
  statut?: "BROUILLON" | "VALIDE";
  editable?: boolean;
  handlers?: RequestHandler[];
  rapport?: RapportOrientation;
  objectives?: ObjectifAudit[];
} = {}) {
  server.use(
    ...handlers,
    http.get(`${API_URL}/api/v1/audit-frameworks/${ANALYSE_MISSION_ID}/`, () =>
      HttpResponse.json(
        aFramework({
          statut,
          mes_droits: analyseRights({ voir_travaux: true, contribuer_vii: editable }),
        }),
      ),
    ),
    http.get(`${API_URL}/api/v1/audit-objectives/`, () => HttpResponse.json(page(objectives))),
    http.get(`${API_URL}/api/v1/orientation-reports/${ANALYSE_MISSION_ID}/`, () =>
      HttpResponse.json(rapport),
    ),
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

  it("restores a control with « Tester ce contrôle » and shows its error apart from the label", async () => {
    let body: unknown;
    let fail = true;
    const user = userEvent.setup();
    setup({
      objectives: [anObjective({ retenu: false, motif_non_test: "CONCEPTION_ADAPTEE" })],
      handlers: [
        http.patch(`${API_URL}/api/v1/audit-objectives/:id/`, async ({ request }) => {
          body = await request.json();
          if (fail) {
            return HttpResponse.json({ detail: "Refusé.", errors: {} }, { status: 422 });
          }
          return HttpResponse.json(anObjective());
        }),
      ],
    });
    expect(await screen.findByText("Non testé : Conception adaptée")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Tester le contrôle de OA-01" }));
    expect(await screen.findByText("Refusé.")).toBeInTheDocument();
    expect(screen.getByLabelText("Libellé de l'objectif OA-01")).not.toHaveAttribute(
      "aria-invalid",
      "true",
    );
    fail = false;
    await user.click(screen.getByRole("button", { name: "Tester le contrôle de OA-01" }));
    await waitFor(() => expect(body).toEqual({ retenu: true }));
  });

  it("renders « Non testé » without a trailing colon when the reason is missing", async () => {
    setup({ objectives: [anObjective({ retenu: false, motif_non_test: "" })] });
    const cell = await screen.findByText("Non testé");
    expect(cell.textContent).toBe("Non testé");
  });

  it("edits the label inline and shows a 422 on the input", async () => {
    const bodies: unknown[] = [];
    const user = userEvent.setup();
    setup({
      handlers: [
        http.patch(`${API_URL}/api/v1/audit-objectives/:id/`, async ({ request }) => {
          bodies.push(await request.json());
          return HttpResponse.json(
            { detail: "Données invalides.", errors: { libelle: ["Libellé trop long."] } },
            { status: 422 },
          );
        }),
      ],
    });
    const input = await screen.findByLabelText("Libellé de l'objectif OA-01");
    await user.clear(input);
    await user.type(input, "Nouveau libellé");
    await user.click(screen.getByRole("button", { name: "Enregistrer le libellé de OA-01" }));
    await waitFor(() => expect(bodies).toEqual([{ libelle: "Nouveau libellé" }]));
    expect(await screen.findByText("Libellé trop long.")).toBeInTheDocument();
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("Libellé trop long.");
  });

  it("shows server reasons when the atomic initialization fails", async () => {
    const user = userEvent.setup();
    setup({
      handlers: [
        http.post(`${API_URL}/api/v1/audit-objectives/initialize/`, () =>
          HttpResponse.json(
            { detail: "Aucun objectif créé.", errors: { ligne_marc: ["Contrôle clé incomplet."] } },
            { status: 422 },
          ),
        ),
      ],
    });
    await user.click(
      await screen.findByRole("button", { name: "Proposer un objectif par contrôle clé" }),
    );
    const alert = await screen.findByText(/Contrôle clé incomplet/);
    expect(alert).toHaveTextContent("Aucun objectif créé.");
  });

  it("lists the objectives of every page", async () => {
    setup({
      handlers: [
        http.get(`${API_URL}/api/v1/audit-objectives/`, ({ request }) => {
          const p = new URL(request.url).searchParams.get("page");
          return HttpResponse.json(
            p === "1"
              ? { count: 2, next: "x", previous: null, results: [anObjective({ id: "a" })] }
              : {
                  count: 2,
                  next: null,
                  previous: "x",
                  results: [anObjective({ id: "b", code: "OA-02", numero: 2 })],
                },
          );
        }),
      ],
    });
    expect(await screen.findByText("OA-02")).toBeInTheDocument();
    expect(screen.getByText("OA-01")).toBeInTheDocument();
  });

  it("shows a loading state then an error state, never an empty state", async () => {
    setup({
      handlers: [
        http.get(`${API_URL}/api/v1/audit-objectives/`, () =>
          HttpResponse.json({ detail: "x" }, { status: 500 }),
        ),
      ],
    });
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(await screen.findAllByRole("alert")).not.toHaveLength(0);
    expect(screen.queryByText("Aucun objectif d'audit")).not.toBeInTheDocument();
  });

  it("shows an error when the framework cannot be loaded", async () => {
    setup({
      handlers: [
        http.get(`${API_URL}/api/v1/audit-frameworks/${ANALYSE_MISSION_ID}/`, () =>
          HttpResponse.json({ detail: "x" }, { status: 500 }),
        ),
      ],
    });
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Impossible de charger les données de l'analyse.",
    );
  });

  it("shows a server 422 in the non-test dialog and has no axe violation while open", async () => {
    const user = userEvent.setup();
    setup({
      handlers: [
        http.patch(`${API_URL}/api/v1/audit-objectives/:id/`, () =>
          HttpResponse.json(
            { detail: "Données invalides.", errors: { justification: ["Justification refusée."] } },
            { status: 422 },
          ),
        ),
      ],
    });
    await user.click(
      await screen.findByRole("button", { name: "Ne pas tester le contrôle de OA-01" }),
    );
    const dialog = await screen.findByRole("dialog");
    expect((await axe(dialog, NO_CONTRAST)).violations).toEqual([]);
    await user.selectOptions(
      within(dialog).getByLabelText("Motif de non-test"),
      "CONCEPTION_ADAPTEE",
    );
    await user.type(within(dialog).getByLabelText("Justification"), "Oui");
    await user.click(within(dialog).getByRole("button", { name: "Confirmer le non-test" }));
    const field = within(dialog).getByLabelText("Justification");
    expect(await within(dialog).findByText("Justification refusée.")).toBeInTheDocument();
    await waitFor(() => expect(field).toHaveFocus());
    expect(field).toHaveAccessibleDescription("Justification refusée.");
  });

  it("clears the stale justification when the coverage returns to exact and resets « saved »", async () => {
    const bodies: Record<string, unknown>[] = [];
    const user = userEvent.setup();
    setup({
      rapport: report({ couverture_ordre: "PARTIELLE", justification_couverture: "Ancienne" }),
      handlers: [
        http.patch(
          `${API_URL}/api/v1/orientation-reports/${ANALYSE_MISSION_ID}/`,
          async ({ request }) => {
            bodies.push((await request.json()) as Record<string, unknown>);
            return HttpResponse.json(report());
          },
        ),
      ],
    });
    await user.selectOptions(
      await screen.findByLabelText("Couverture de l'ordre de mission"),
      "EXACTE",
    );
    await user.click(screen.getByRole("button", { name: "Enregistrer le rapport d'orientation" }));
    expect(await screen.findByText("Rapport d'orientation enregistré.")).toBeInTheDocument();
    expect(bodies[0]?.justification_couverture).toBe("");
    await user.type(screen.getByLabelText("Contexte"), "x");
    expect(screen.queryByText("Rapport d'orientation enregistré.")).not.toBeInTheDocument();
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
