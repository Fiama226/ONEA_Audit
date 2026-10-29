import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import {
  allSteps,
  aMission,
  missionHandlers,
  MISSION_ID,
  pageOf,
  renderMission,
} from "@/features/missions/testUtils";
import { API_URL } from "@/test/msw";
import { aFramework, aMarcLine, analyseRights } from "../testUtils";
import type { ForceFaiblesse } from "../types";

const NO_CONTRAST = { rules: { "color-contrast": { enabled: false } } };
const RISK_ID = "44444444-4444-4444-8444-444444444444";

function aForce(overrides: Partial<ForceFaiblesse> = {}): ForceFaiblesse {
  return {
    id: "99999999-9999-4999-8999-999999999999",
    mission: MISSION_ID,
    type: "FAIBLESSE",
    ligne_marc: "33333333-3333-4333-8333-333333333333",
    liee: true,
    processus: null,
    processus_code: null,
    libelle: "Contrôle absent sur la facturation",
    consequence: "",
    commentaire: "",
    ordre: 0,
    ...overrides,
  };
}

function handlers(
  opts: {
    contribuer?: boolean;
    uncovered?: string[];
    forces?: ForceFaiblesse[];
    posts?: unknown[];
  } = {},
) {
  const lines = Array.from({ length: 201 }, (_, i) =>
    aMarcLine({
      id: `00000000-0000-4000-8000-${String(i).padStart(12, "0")}`,
      controle_existant: `Contrôle n°${i + 1}`,
    }),
  );
  return [
    ...missionHandlers(aMission(), allSteps()),
    http.get(`${API_URL}/api/v1/audit-frameworks/${MISSION_ID}/`, () =>
      HttpResponse.json(
        aFramework({
          risques_non_couverts: opts.uncovered ?? [],
          mes_droits: analyseRights({
            voir_travaux: true,
            voir_referentiel: true,
            contribuer_v: opts.contribuer ?? true,
          }),
        }),
      ),
    ),
    http.get(`${API_URL}/api/v1/marc-lines/`, ({ request }) => {
      const page = Number(new URL(request.url).searchParams.get("page") ?? "1");
      const slice = page === 1 ? lines.slice(0, 200) : lines.slice(200);
      return HttpResponse.json({
        count: 201,
        next: page === 1 ? `${API_URL}/api/v1/marc-lines/?page=2` : null,
        previous: null,
        results: slice,
      });
    }),
    http.post(`${API_URL}/api/v1/marc-lines/initialize/`, async ({ request }) => {
      opts.posts?.push(await request.json());
      return HttpResponse.json([]);
    }),
    http.post(`${API_URL}/api/v1/marc-lines/`, async ({ request }) => {
      opts.posts?.push(await request.json());
      return HttpResponse.json(aMarcLine(), { status: 201 });
    }),
    http.get(`${API_URL}/api/v1/strengths-weaknesses/`, () =>
      HttpResponse.json(pageOf(opts.forces ?? [])),
    ),
    http.get(`${API_URL}/api/v1/mission-risks/`, () =>
      HttpResponse.json(
        pageOf([
          {
            id: RISK_ID,
            mission: MISSION_ID,
            code_source: "R-001",
            libelle: "Fraude à la facturation",
            processus: "88888888-8888-4888-8888-888888888888",
            niveau: "ELEVE",
          },
        ]),
      ),
    ),
    http.get(`${API_URL}/api/v1/auditable-objects/tree/`, () => HttpResponse.json([])),
  ];
}

const url = `/missions/${MISSION_ID}/etapes/5`;

describe("StepVZone", () => {
  it("shows all 201 MARC lines loaded over two pages", async () => {
    renderMission(url, "AUDITEUR", { handlers: handlers({ uncovered: ["R-007", "R-009"] }) });
    expect(await screen.findByText("Contrôle n°201")).toBeInTheDocument();
    expect(screen.getByText("Contrôle n°1")).toBeInTheDocument();
    expect(
      screen.getByText("Risques moyens ou élevés sans contrôle analysé : R-007, R-009"),
    ).toBeInTheDocument();
  });

  it("initializes the matrix from the mission risks", async () => {
    const posts: unknown[] = [];
    const user = userEvent.setup();
    renderMission(url, "AUDITEUR", { handlers: handlers({ posts }) });
    await user.click(
      await screen.findByRole("button", { name: "Initialiser depuis les risques de la mission" }),
    );
    await waitFor(() => expect(posts).toEqual([{ mission: MISSION_ID }]));
  });

  it("blocks a key control with an absent control on the client", async () => {
    const posts: unknown[] = [];
    const user = userEvent.setup();
    renderMission(url, "AUDITEUR", { handlers: handlers({ posts }) });
    await user.click(await screen.findByRole("button", { name: "Ajouter un contrôle" }));
    const dialog = await screen.findByRole("dialog");
    await user.selectOptions(await within(dialog).findByLabelText("Risque de la mission"), RISK_ID);
    await user.selectOptions(
      within(dialog).getByLabelText("Évaluation de la conception"),
      "ABSENTE",
    );
    await user.click(within(dialog).getByLabelText("Contrôle clé"));
    await user.click(within(dialog).getByRole("button", { name: "Enregistrer" }));
    expect(
      await within(dialog).findByText("Un contrôle absent ne peut pas être un contrôle clé."),
    ).toBeInTheDocument();
    expect(posts).toEqual([]);
  });

  it("requires the existing control when the design is evaluated", async () => {
    const user = userEvent.setup();
    renderMission(url, "AUDITEUR", { handlers: handlers() });
    await user.click(await screen.findByRole("button", { name: "Ajouter un contrôle" }));
    const dialog = await screen.findByRole("dialog");
    await user.selectOptions(await within(dialog).findByLabelText("Risque de la mission"), RISK_ID);
    await user.selectOptions(
      within(dialog).getByLabelText("Évaluation de la conception"),
      "ADEQUATE",
    );
    await user.click(within(dialog).getByRole("button", { name: "Enregistrer" }));
    expect(
      await within(dialog).findByText(
        "Le contrôle existant est obligatoire quand la conception est évaluée.",
      ),
    ).toBeInTheDocument();
  });

  it("marks a linked weakness as coming from the MARC without a removal button", async () => {
    renderMission(url, "AUDITEUR", { handlers: handlers({ forces: [aForce()] }) });
    expect(await screen.findByText("Issue de la MARC")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Retirer la ligne : Contrôle absent sur la facturation" }),
    ).toBeDisabled();
    expect(
      screen.getByText("Cette ligne suit la matrice MARC : modifiez la ligne MARC."),
    ).toBeInTheDocument();
  });

  it("offers no write action without the contribuer_v right", async () => {
    renderMission(url, "AUDITEUR", { handlers: handlers({ contribuer: false }) });
    await screen.findByText("Contrôle n°201");
    expect(screen.queryByRole("button", { name: "Ajouter un contrôle" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Modifier le contrôle/ })).not.toBeInTheDocument();
  });

  it("has no axe violation with the control dialog open", async () => {
    const user = userEvent.setup();
    const { container } = renderMission(url, "AUDITEUR", { handlers: handlers() });
    await user.click(await screen.findByRole("button", { name: "Ajouter un contrôle" }));
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByRole("option", { name: /R-001/ });
    expect((await axe(container, NO_CONTRAST)).violations).toEqual([]);
    expect((await axe(dialog, NO_CONTRAST)).violations).toEqual([]);
  });
});
