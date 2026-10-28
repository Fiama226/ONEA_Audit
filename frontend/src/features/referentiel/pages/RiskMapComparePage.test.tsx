import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { API_URL, server } from "@/test/msw";
import { DRAFT, mockReferentiel, renderCarto, VALIDATED } from "../cartoFixtures";
import { RiskMapComparePage } from "./RiskMapComparePage";

const routes = [
  { path: "/referentiel/cartographies/:id/comparer", element: <RiskMapComparePage /> },
];
const path = `/referentiel/cartographies/${DRAFT.id}/comparer?avec=${VALIDATED.id}`;
const ref = { id: VALIDATED.id, annee: 2025, libelle: VALIDATED.libelle, statut: "VALIDEE" };
const cible = { id: DRAFT.id, annee: 2026, libelle: DRAFT.libelle, statut: "BROUILLON" };

describe("RiskMapComparePage", () => {
  it("shows the empty state when there is no difference", async () => {
    mockReferentiel();
    let withParam = "";
    server.use(
      http.get(`${API_URL}/api/v1/risk-maps/${DRAFT.id}/compare/`, ({ request }) => {
        withParam = new URL(request.url).searchParams.get("with") ?? "";
        return HttpResponse.json({ reference: ref, cible, ajoutes: [], retires: [], modifies: [] });
      }),
    );
    renderCarto(routes, "AUDITEUR", path);
    expect(
      await screen.findByText("Aucune différence entre les deux cartographies."),
    ).toBeInTheDocument();
    expect(withParam).toBe(VALIDATED.id);
  });

  it("lists added, removed and modified risks", async () => {
    mockReferentiel();
    server.use(
      http.get(`${API_URL}/api/v1/risk-maps/${DRAFT.id}/compare/`, () =>
        HttpResponse.json({
          reference: ref,
          cible,
          ajoutes: [
            { id: "a", code: "12-FEP-R3", libelle: "Nouveau risque", score: 9, niveau: "MOYEN" },
          ],
          retires: [
            { id: "b", code: "12-FEP-R4", libelle: "Ancien risque", score: 2, niveau: "FAIBLE" },
          ],
          modifies: [
            {
              code: "12-FEP-R1",
              changements: { probabilite: ["2", "3"], niveau: ["MOYEN", "ELEVE"] },
            },
          ],
        }),
      ),
    );
    const { container } = renderCarto(routes, "AUDITEUR", path);
    expect(await screen.findByText(/Risques ajoutés/)).toBeInTheDocument();
    expect(screen.getByText("Nouveau risque")).toBeInTheDocument();
    expect(screen.getByText(/Risques retirés/)).toBeInTheDocument();
    expect(screen.getByText(/Risques modifiés/)).toBeInTheDocument();
    expect(screen.getByText("Élevé")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Avant" })).toBeInTheDocument();
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });

  it("asks to pick a version when none is selected", async () => {
    mockReferentiel();
    renderCarto(routes, "AUDITEUR", `/referentiel/cartographies/${DRAFT.id}/comparer`);
    expect(await screen.findByText(/Choisissez une version/)).toBeInTheDocument();
  });

  it("shows an error state", async () => {
    mockReferentiel();
    server.use(
      http.get(`${API_URL}/api/v1/risk-maps/${DRAFT.id}/compare/`, () =>
        HttpResponse.json({}, { status: 500 }),
      ),
    );
    renderCarto(routes, "AUDITEUR", path);
    expect(await screen.findByRole("alert")).toHaveTextContent("Impossible de comparer");
  });
});
