import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { API_URL, server } from "@/test/msw";
import { DRAFT, mockReferentiel, renderCarto, VALIDATED } from "../cartoFixtures";
import { RiskMapComparePage } from "./RiskMapComparePage";

const routes = [
  { path: "/referentiel/cartographies/:id/comparer", element: <RiskMapComparePage /> },
];
// VALIDATED (2025) est la plus ancienne : toujours la référence ; DRAFT (2026) la cible.
const newerFirst = `/referentiel/cartographies/${DRAFT.id}/comparer?avec=${VALIDATED.id}`;
const olderFirst = `/referentiel/cartographies/${VALIDATED.id}/comparer?avec=${DRAFT.id}`;
const ref = { id: VALIDATED.id, annee: 2025, libelle: VALIDATED.libelle, statut: "VALIDEE" };
const cible = { id: DRAFT.id, annee: 2026, libelle: DRAFT.libelle, statut: "BROUILLON" };

/** Simule le backend : la référence est la version de l'URL, la cible est `with`. */
function mockCompare(body: Record<string, unknown>) {
  const calls: string[] = [];
  server.use(
    http.get(`${API_URL}/api/v1/risk-maps/${VALIDATED.id}/compare/`, ({ request }) => {
      calls.push(new URL(request.url).search);
      return HttpResponse.json({ reference: ref, cible, ...body });
    }),
    http.get(`${API_URL}/api/v1/risk-maps/${DRAFT.id}/compare/`, () => {
      calls.push("WRONG-DIRECTION");
      return HttpResponse.json({}, { status: 500 });
    }),
  );
  return calls;
}

describe("RiskMapComparePage", () => {
  it.each([
    ["from the newer version", newerFirst],
    ["from the older version", olderFirst],
  ])("uses the older year as reference (URL id) and the newer as `with` %s", async (_, path) => {
    mockReferentiel();
    const calls = mockCompare({ ajoutes: [], retires: [], modifies: [] });
    renderCarto(routes, "AUDITEUR", path);
    expect(
      await screen.findByText("Aucune différence entre les deux cartographies."),
    ).toBeInTheDocument();
    expect(calls).toEqual([`?with=${DRAFT.id}`]);
  });

  it("lists added, removed and modified risks the right way round", async () => {
    mockReferentiel();
    mockCompare({
      ajoutes: [
        {
          id: "a",
          code: "12-FEP-R3",
          libelle: "Présent en 2026 seulement",
          score: 9,
          niveau: "MOYEN",
        },
      ],
      retires: [
        {
          id: "b",
          code: "12-FEP-R4",
          libelle: "Présent en 2025 seulement",
          score: 2,
          niveau: "FAIBLE",
        },
      ],
      modifies: [
        {
          code: "12-FEP-R1",
          changements: { probabilite: ["2", "3"], niveau: ["MOYEN", "ELEVE"] },
        },
      ],
    });
    const { container } = renderCarto(routes, "AUDITEUR", newerFirst);
    const added = (await screen.findByText(/Risques ajoutés/)).closest("section")!;
    expect(added).toHaveTextContent("Présent en 2026 seulement");
    const removed = screen.getByText(/Risques retirés/).closest("section")!;
    expect(removed).toHaveTextContent("Présent en 2025 seulement");
    expect(screen.getByRole("columnheader", { name: "Avant (2025)" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Après (2026)" })).toBeInTheDocument();
    expect(
      screen.getByText(/De Cartographie des risques 2025 à Cartographie des risques 2026/),
    ).toBeInTheDocument();
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });

  it("does not navigate on selection, only on the Comparer button", async () => {
    mockReferentiel();
    const user = userEvent.setup();
    const { router } = renderCarto(
      routes,
      "AUDITEUR",
      `/referentiel/cartographies/${DRAFT.id}/comparer`,
    );
    expect(await screen.findByText(/Choisissez une version/)).toBeInTheDocument();
    await user.selectOptions(await screen.findByLabelText("Version de comparaison"), VALIDATED.id);
    expect(router.state.location.search).toBe("");
    await user.click(screen.getByRole("button", { name: "Comparer" }));
    expect(router.state.location.search).toBe(`?avec=${VALIDATED.id}`);
  });

  it("shows an error state", async () => {
    mockReferentiel();
    server.use(
      http.get(`${API_URL}/api/v1/risk-maps/${VALIDATED.id}/compare/`, () =>
        HttpResponse.json({}, { status: 500 }),
      ),
    );
    renderCarto(routes, "AUDITEUR", newerFirst);
    expect(await screen.findByRole("alert")).toHaveTextContent("Impossible de comparer");
  });
});
