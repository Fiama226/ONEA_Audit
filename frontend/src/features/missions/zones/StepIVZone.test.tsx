import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, type RequestHandler } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { risk } from "@/features/referentiel/cartoFixtures";
import { API_URL } from "@/test/msw";
import {
  aMission,
  allRights,
  allSteps,
  missionHandlers,
  MISSION_ID,
  pageOf,
  renderMission,
} from "../testUtils";
import type { MatriceMission, Mission, RisqueMission, StatutEtape } from "../types";

const NO_CONTRAST = { rules: { "color-contrast": { enabled: false } } };
const CARTO = "33333333-3333-4333-8333-333333333333";
const PROCESS = { id: "p-1", code: "12-FEP", libelle: "Facturation et encaissement" };

function missionRisk(overrides: Partial<RisqueMission> = {}): RisqueMission {
  return {
    id: "mr-1",
    mission: MISSION_ID,
    mission_reference: "DAI/2026/M01",
    risque_source: null,
    code_source: "",
    nouveau: true,
    processus: PROCESS.id,
    processus_code: PROCESS.code,
    libelle: "Risque ajouté par la mission",
    description: "",
    probabilite: 3,
    impact: 5,
    score: 15,
    niveau: "ELEVE",
    commentaire: "",
    probabilite_reference: null,
    impact_reference: null,
    ...overrides,
  } satisfies RisqueMission;
}

const SELECTED = missionRisk({
  id: "mr-2",
  risque_source: "src-1",
  code_source: "12-FEP-R1",
  nouveau: false,
  libelle: "Fraude sur les encaissements",
  probabilite: 3,
  impact: 5,
  probabilite_reference: 4,
  impact_reference: 2,
});
const LOW = missionRisk({
  id: "mr-3",
  libelle: "Retard de facturation",
  probabilite: 2,
  impact: 2,
  score: 4,
  niveau: "FAIBLE",
});

const MATRIX = {
  mission: MISSION_ID,
  total: 2,
  par_niveau: { FAIBLE: 1, MOYEN: 0, ELEVE: 1 },
  cellules: [
    { probabilite: 3, impact: 5, score: 15, niveau: "ELEVE", nombre: 1, codes: ["12-FEP-R1"] },
    { probabilite: 2, impact: 2, score: 4, niveau: "FAIBLE", nombre: 1, codes: [] },
  ],
} satisfies MatriceMission;

type Options = {
  statut?: StatutEtape;
  mission?: Partial<Mission>;
  risks?: RisqueMission[];
  handlers?: RequestHandler[];
};

function setup({
  statut = "EN_COURS",
  mission,
  risks = [SELECTED, LOW],
  handlers = [],
}: Options = {}) {
  const m = aMission({
    cartographie: { id: CARTO, annee: 2026 },
    processus_detail: [PROCESS],
    ...mission,
  });
  const steps = allSteps((n) => (n === 4 ? { statut } : {}));
  return renderMission(`/missions/${MISSION_ID}/etapes/4`, "AUDITEUR", {
    handlers: [
      ...missionHandlers(m, steps),
      http.get(`${API_URL}/api/v1/mission-risks/`, () => HttpResponse.json(pageOf(risks))),
      http.get(`${API_URL}/api/v1/missions/${MISSION_ID}/risk-matrix/`, () =>
        HttpResponse.json(MATRIX),
      ),
      ...handlers,
    ],
  });
}

/** Deux pages MSW : 201 risques de cartographie (page 1 = 200, page 2 = 1). */
function cartographyPages(): RequestHandler {
  const all = Array.from({ length: 201 }, (_, i) =>
    risk({
      id: `src-${i + 1}`,
      version: CARTO,
      code: `12-FEP-R${i + 1}`,
      libelle: `Risque de cartographie ${i + 1}`,
    }),
  );
  return http.get(`${API_URL}/api/v1/risks/`, ({ request }) => {
    const page = Number(new URL(request.url).searchParams.get("page") ?? "1");
    return HttpResponse.json(
      page === 1
        ? {
            count: 201,
            next: `${API_URL}/api/v1/risks/?page=2`,
            previous: null,
            results: all.slice(0, 200),
          }
        : { count: 201, next: null, previous: null, results: all.slice(200) },
    );
  });
}

describe("StepIVZone", () => {
  it("lists the mission risks with their reference assessment when re-evaluated", async () => {
    setup();
    const table = await screen.findByRole("table", { name: "Risques retenus pour la mission" });
    const fraud = within(table).getByRole("row", { name: /Fraude sur les encaissements/ });
    expect(within(fraud).getByText("12-FEP-R1")).toBeInTheDocument();
    expect(within(fraud).getByText("4×2")).toBeInTheDocument();
    const added = within(table).getByRole("row", { name: /Retard de facturation/ });
    expect(within(added).getByText("Nouveau")).toBeInTheDocument();
    expect(within(added).getByText("Faible")).toBeInTheDocument();
  });

  it("lists all 201 cartography risks over two pages and posts the selection with risque_source", async () => {
    const bodies: unknown[] = [];
    const user = userEvent.setup();
    setup({
      risks: [SELECTED],
      handlers: [
        cartographyPages(),
        http.post(`${API_URL}/api/v1/mission-risks/`, async ({ request }) => {
          bodies.push(await request.json());
          return HttpResponse.json(missionRisk({ id: "new" }), { status: 201 });
        }),
      ],
    });
    await user.click(
      await screen.findByRole("button", {
        name: "Sélectionner des risques de la cartographie 2026",
      }),
    );
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByLabelText(/Risque de cartographie 201[^0-9]/);
    expect(within(dialog).getAllByRole("checkbox")).toHaveLength(201);
    expect(within(dialog).getByLabelText(/Risque de cartographie 1[^0-9]/)).toBeDisabled();
    await user.click(within(dialog).getByLabelText(/Risque de cartographie 201[^0-9]/));
    await user.click(within(dialog).getByLabelText(/Risque de cartographie 5[^0-9]/));
    await user.click(within(dialog).getByRole("button", { name: "Ajouter la sélection" }));
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies).toEqual(
      expect.arrayContaining([
        { mission: MISSION_ID, risque_source: "src-201" },
        { mission: MISSION_ID, risque_source: "src-5" },
      ]),
    );
  });

  it("previews « Score 15 · Élevé » for a new risk P 3 × I 5 and posts it without a source", async () => {
    const bodies: unknown[] = [];
    const user = userEvent.setup();
    setup({
      handlers: [
        http.post(`${API_URL}/api/v1/mission-risks/`, async ({ request }) => {
          bodies.push(await request.json());
          return HttpResponse.json(missionRisk({ id: "new" }), { status: 201 });
        }),
      ],
    });
    await user.click(await screen.findByRole("button", { name: "Ajouter un risque nouveau" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Libellé du risque"), "Risque de fraude interne");
    await user.selectOptions(within(dialog).getByLabelText("Probabilité"), "3");
    await user.selectOptions(within(dialog).getByLabelText("Impact"), "5");
    expect(within(dialog).getByText("Score 15 · Élevé")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Enregistrer" }));
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toEqual({
      mission: MISSION_ID,
      processus: PROCESS.id,
      libelle: "Risque de fraude interne",
      description: "",
      probabilite: 3,
      impact: 5,
    });
    expect(bodies[0]).not.toHaveProperty("risque_source");
  });

  it("re-evaluates a risk with P, I and a comment", async () => {
    const bodies: unknown[] = [];
    const user = userEvent.setup();
    setup({
      handlers: [
        http.patch(`${API_URL}/api/v1/mission-risks/mr-2/`, async ({ request }) => {
          bodies.push(await request.json());
          return HttpResponse.json(SELECTED);
        }),
      ],
    });
    await user.click(
      await screen.findByRole("button", { name: "Réévaluer Fraude sur les encaissements" }),
    );
    const dialog = await screen.findByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText("Impact"), "4");
    await user.type(within(dialog).getByLabelText("Commentaire"), "Contrôle renforcé");
    expect(within(dialog).getByText("Score 12 · Moyen")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Enregistrer" }));
    await waitFor(() =>
      expect(bodies).toEqual([{ probabilite: 3, impact: 4, commentaire: "Contrôle renforcé" }]),
    );
  });

  it("filters the table from a matrix cell and reflects it in the URL", async () => {
    const user = userEvent.setup();
    const { router } = setup();
    await screen.findByText("Retard de facturation");
    await user.click(await screen.findByRole("button", { name: /Probabilité 3, impact 5/i }));
    await waitFor(() =>
      expect(screen.queryByText("Retard de facturation")).not.toBeInTheDocument(),
    );
    expect(screen.getByText("Fraude sur les encaissements")).toBeInTheDocument();
    expect(router.state.location.search).toContain("probabilite=3");
    expect(router.state.location.search).toContain("impact=5");
    await user.click(screen.getByRole("button", { name: "Effacer le filtre" }));
    expect(await screen.findByText("Retard de facturation")).toBeInTheDocument();
  });

  it.each<[string, Options]>([
    ["a closed step", { statut: "TERMINEE" }],
    ["a validated step", { statut: "VALIDEE" }],
    ["a user without the contribute right", { mission: { mes_droits: allRights(false) } }],
  ])("is read-only for %s", async (_, options) => {
    setup(options);
    await screen.findByText("Retard de facturation");
    expect(
      screen.queryByRole("button", { name: /Sélectionner des risques/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Ajouter un risque nouveau" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Réévaluer/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Retirer/ })).not.toBeInTheDocument();
    expect(screen.getByText(/ne sont plus modifiables/)).toBeInTheDocument();
  });

  it("has no axe violation, dialogs open included", async () => {
    const user = userEvent.setup();
    const { container } = setup({ handlers: [cartographyPages()] });
    await screen.findByText("Retard de facturation");
    expect((await axe(container, NO_CONTRAST)).violations).toEqual([]);

    await user.click(screen.getByRole("button", { name: "Ajouter un risque nouveau" }));
    expect((await axe(await screen.findByRole("dialog"), NO_CONTRAST)).violations).toEqual([]);
    await user.click(screen.getByRole("button", { name: "Annuler" }));

    await user.click(
      screen.getByRole("button", { name: "Sélectionner des risques de la cartographie 2026" }),
    );
    const select = await screen.findByRole("dialog");
    await within(select).findByLabelText(/Risque de cartographie 1[^0-9]/);
    expect((await axe(select, NO_CONTRAST)).violations).toEqual([]);
  });
});
