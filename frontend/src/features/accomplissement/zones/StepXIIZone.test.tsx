import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { allRights, aMission, aStep } from "@/features/missions/testUtils";
import { API_URL, server } from "@/test/msw";
import { renderWithAuth } from "@/test/shell";
import type { ProgrammeTravail, TestPrevu } from "../types";
import { StepXIIZone } from "./StepXIIZone";

const NO_CONTRAST = { rules: { "color-contrast": { enabled: false } } };
const USER = {
  id: 1,
  username: "a",
  nom_complet: "Awa Ouedraogo",
  role: "AUDITEUR",
  direction_code: "DAI",
  fonction: "",
} as const;
const OTHER = { ...USER, id: 9, nom_complet: "Issa Traoré" };

function aTest(overrides: Partial<TestPrevu> = {}): TestPrevu {
  return {
    id: "t1",
    mission: "m",
    programme: "p1",
    code: "T-001",
    libelle: "Rapprocher les factures",
    auditeur: 1,
    auditeur_detail: USER,
    complementaire: false,
    statut: "PREVU",
    motif_abandon: "",
    fiche: null,
    actions_possibles: ["ABANDONNER"],
    ...overrides,
  } as TestPrevu;
}

function page<T>(results: T[]) {
  return { count: results.length, next: null, previous: null, results };
}

const PROGRAM = {
  id: "p1",
  objectif_detail: { id: "o1", code: "OA-01", libelle: "Achats" },
  actions_possibles: ["AJOUTER_COMPLEMENTAIRE"],
} as ProgrammeTravail;

function setup(tests: TestPrevu[], role: "AUDITEUR" | "RAI" = "AUDITEUR", programs = [PROGRAM]) {
  server.use(
    http.get(`${API_URL}/api/v1/planned-tests/`, () => HttpResponse.json(page(tests))),
    http.get(`${API_URL}/api/v1/work-programs/`, () => HttpResponse.json(page(programs))),
  );
  return renderWithAuth(
    <StepXIIZone
      mission={aMission({ mes_droits: allRights(true) })}
      step={aStep({ numero: 12 })}
    />,
    role,
  );
}

describe("StepXIIZone", () => {
  it("filtre « Mes tests » par défaut pour un auditeur", async () => {
    setup([aTest(), aTest({ id: "t2", code: "T-002", auditeur: 9, auditeur_detail: OTHER })]);
    expect(await screen.findByText("T-001")).toBeVisible();
    expect(screen.queryByText("T-002")).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Tous les tests" }));
    expect(await screen.findByText("T-002")).toBeVisible();
  });

  it("affiche l'état de la fiche et la conclusion", async () => {
    setup([
      aTest({ fiche: { id: "f1", statut: "VALIDE", conclusion: "ANOMALIE" } }),
      aTest({ id: "t2", code: "T-002" }),
    ]);
    const table = await screen.findByRole("table");
    expect(within(table).getByText("Validée")).toBeVisible();
    expect(within(table).getByText("Anomalie")).toBeVisible();
    expect(within(table).getByText("À documenter")).toBeVisible();
  });

  it("n'affiche pas un échec de chargement comme une liste vide", async () => {
    server.use(http.get(`${API_URL}/api/v1/planned-tests/`, () => HttpResponse.error()));
    renderWithAuth(<StepXIIZone mission={aMission()} step={aStep({ numero: 12 })} />, "RAI");
    expect(await screen.findByRole("alert")).toHaveTextContent("Impossible de charger");
    expect(screen.queryByText("Aucun test à afficher.")).not.toBeInTheDocument();
  });

  it("« Documenter le test » crée la fiche", async () => {
    let body: unknown;
    server.use(
      http.post(`${API_URL}/api/v1/test-sheets/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ id: "f9", mission: "m" }, { status: 201 });
      }),
    );
    setup([aTest()]);
    await userEvent
      .setup()
      .click(await screen.findByRole("button", { name: /Documenter le test/ }));
    await waitFor(() => expect(body).toEqual({ test: "t1" }));
  });

  it("abandonne un test avec motif obligatoire", async () => {
    let body: unknown;
    server.use(
      http.post(`${API_URL}/api/v1/planned-tests/t1/abandon/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(aTest({ statut: "ABANDONNE" }));
      }),
    );
    const user = userEvent.setup();
    setup([aTest()]);
    await user.click(await screen.findByRole("button", { name: /Abandonner le test/ }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Abandonner" }));
    expect(await within(dialog).findByRole("alert")).toBeVisible();
    expect(body).toBeUndefined();
    await user.type(within(dialog).getByRole("textbox"), "Doublon avec T-004");
    await user.click(within(dialog).getByRole("button", { name: "Abandonner" }));
    await waitFor(() => expect(body).toEqual({ motif: "Doublon avec T-004" }));
  });

  it("ajoute un test complémentaire via le dialogue", async () => {
    let body: Record<string, unknown> | undefined;
    server.use(
      http.post(`${API_URL}/api/v1/planned-tests/`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(aTest(), { status: 201 });
      }),
    );
    const user = userEvent.setup();
    setup([aTest()], "RAI");
    await user.click(await screen.findByRole("button", { name: "Ajouter un test complémentaire" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Ajouter le test" }));
    expect(await within(dialog).findByText("Le libellé est obligatoire.")).toBeVisible();
    expect(within(dialog).getByLabelText("Libellé du test")).toHaveFocus();
    expect(body).toBeUndefined();
    await user.type(within(dialog).getByLabelText("Libellé du test"), "Contrôle des avoirs");
    await user.click(within(dialog).getByRole("button", { name: "Ajouter le test" }));
    await waitFor(() =>
      expect(body).toMatchObject({ programme: "p1", libelle: "Contrôle des avoirs" }),
    );
  });

  it("n'a aucune violation axe", async () => {
    const { container } = setup([aTest()]);
    await screen.findByText("T-001");
    expect((await axe(container, NO_CONTRAST)).violations).toEqual([]);
  });
});
