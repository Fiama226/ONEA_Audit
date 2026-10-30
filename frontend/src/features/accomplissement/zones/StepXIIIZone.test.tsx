import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { aMission, aStep } from "@/features/missions/testUtils";
import { API_URL, server } from "@/test/msw";
import { renderWithAuth } from "@/test/shell";
import type { Fiche, TestPrevu } from "../types";
import { StepXIIIZone } from "./StepXIIIZone";

const NO_CONTRAST = { rules: { "color-contrast": { enabled: false } } };
const USER = { id: 1, nom_complet: "Awa Ouedraogo" };

function page<T>(results: T[]) {
  return { count: results.length, next: null, previous: null, results };
}

function aTest(overrides: Partial<TestPrevu> = {}): TestPrevu {
  return {
    id: "t1",
    code: "T-001",
    libelle: "Test 1",
    complementaire: false,
    statut: "PREVU",
    motif_abandon: "",
    fiche: null,
    ...overrides,
  } as TestPrevu;
}

const SUBMITTED = {
  id: "f1",
  statut: "SOUMIS",
  test_code: "T-001",
  test_libelle: "Test 1",
  auteur_detail: USER,
  conclusion: "ANOMALIE",
} as Fiche;

function setup(tests: TestPrevu[], sheets: Fiche[], evidenceStatus = 200) {
  server.use(
    http.get(`${API_URL}/api/v1/planned-tests/`, () => HttpResponse.json(page(tests))),
    http.get(`${API_URL}/api/v1/test-sheets/`, () => HttpResponse.json(page(sheets))),
    http.get(`${API_URL}/api/v1/evidence/`, () =>
      evidenceStatus === 200
        ? HttpResponse.json(page([{ id: "p1" }, { id: "p2" }]))
        : HttpResponse.json({ detail: "x" }, { status: evidenceStatus }),
    ),
  );
  return renderWithAuth(<StepXIIIZone mission={aMission()} step={aStep({ numero: 13 })} />, "RAI");
}

describe("StepXIIIZone", () => {
  it("liste les fiches soumises avec le nombre de pièces et le compteur d'avancement", async () => {
    setup(
      [
        aTest({ fiche: { id: "f0", statut: "VALIDE", conclusion: "SATISFAISANT" } }),
        aTest({ id: "t2", fiche: { id: "f1", statut: "SOUMIS", conclusion: "ANOMALIE" } }),
        aTest({ id: "t3", complementaire: true, code: "T-009", libelle: "Complément" }),
      ],
      [SUBMITTED],
    );
    const table = await screen.findByRole("table");
    expect(within(table).getByText("Awa Ouedraogo")).toBeVisible();
    expect(await within(table).findByText("2")).toBeVisible();
    expect(within(table).getByRole("link", { name: "Ouvrir T-001" })).toHaveAttribute(
      "href",
      expect.stringMatching(/\/fiches\/f1$/),
    );
    expect(screen.getByText("1 fiche validée sur 3")).toBeVisible();
    expect(screen.getByText(/T-009 · Complément/)).toBeVisible();
  });

  it("signale les tests abandonnés avec leur motif, hors du total", async () => {
    setup(
      [aTest(), aTest({ id: "t2", code: "T-002", statut: "ABANDONNE", motif_abandon: "Doublon" })],
      [],
    );
    expect(await screen.findByText("0 fiche validée sur 1")).toBeVisible();
    expect(screen.getByText(/T-002 · Test 1 — Motif : Doublon/)).toBeVisible();
    expect(screen.getByText("Aucune fiche n'attend de validation.")).toBeVisible();
  });

  it("n'affiche pas une erreur de pièces comme zéro pièce", async () => {
    setup([aTest()], [SUBMITTED], 500);
    const table = await screen.findByRole("table");
    expect(await within(table).findByTitle("Nombre de pièces indisponible")).toBeVisible();
  });

  it("signale une erreur de chargement", async () => {
    server.use(http.get(`${API_URL}/api/v1/planned-tests/`, () => HttpResponse.error()));
    server.use(http.get(`${API_URL}/api/v1/test-sheets/`, () => HttpResponse.json(page([]))));
    renderWithAuth(<StepXIIIZone mission={aMission()} step={aStep({ numero: 13 })} />, "RAI");
    expect(await screen.findByRole("alert")).toHaveTextContent("Impossible de charger");
  });

  it("n'a aucune violation axe", async () => {
    const { container } = setup([aTest()], [SUBMITTED]);
    await screen.findByRole("table");
    expect((await axe(container, NO_CONTRAST)).violations).toEqual([]);
  });
});
