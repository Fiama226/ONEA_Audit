import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { StepActions } from "@/features/missions/components/StepActions";
import { aStep } from "@/features/missions/testUtils";
import { API_URL } from "@/test/msw";
import {
  aMission,
  aProgramme,
  aTest,
  baseHandlers,
  OBJECTIVE_ID,
  PROGRAM_ID,
  renderWithClient,
} from "../testUtils";
import { StepVIIIZone } from "./StepVIIIZone";

const NO_CONTRAST = { rules: { "color-contrast": { enabled: false } } };
const open = aStep({ numero: 8, statut: "EN_COURS" });

describe("StepVIIIZone", () => {
  it("shows the programme card with its tests", async () => {
    renderWithClient(<StepVIIIZone mission={aMission()} step={open} />, baseHandlers());
    expect(await screen.findByText(/OA-01 : Vérifier les rapprochements/)).toBeInTheDocument();
    expect(screen.getByText("Extraction du journal des achats")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "T-01" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Examen documentaire" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "25 · Aléatoire" })).toBeInTheDocument();
  });

  it("creates a planned test with the exact request body", async () => {
    let body: unknown;
    const user = userEvent.setup();
    renderWithClient(<StepVIIIZone mission={aMission()} step={open} />, [
      http.post(`${API_URL}/api/v1/planned-tests/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(aTest(), { status: 201 });
      }),
      ...baseHandlers(),
    ]);
    await user.click(
      await screen.findByRole("button", { name: "Ajouter un test à l'objectif OA-01" }),
    );
    const dialog = await screen.findByRole("dialog");
    await user.type(
      screen.getByLabelText("Libellé du test"),
      "Rapprochement des bons de commande et des factures",
    );
    await user.selectOptions(screen.getByLabelText("Nature du test"), "EXAMEN_DOCUMENTAIRE");
    await user.type(screen.getByLabelText("Procédure"), "Rapprocher chaque facture");
    await user.type(screen.getByLabelText("Population"), "Bons de commande 2025");
    await user.type(screen.getByLabelText("Taille de l'échantillon"), "25");
    await user.selectOptions(screen.getByLabelText("Méthode de sélection"), "ALEATOIRE");
    await user.click(screen.getByRole("button", { name: "Enregistrer le test" }));
    await waitFor(() =>
      expect(body).toEqual({
        programme: PROGRAM_ID,
        libelle: "Rapprochement des bons de commande et des factures",
        nature: "EXAMEN_DOCUMENTAIRE",
        procedure: "Rapprocher chaque facture",
        population: "Bons de commande 2025",
        taille_echantillon: 25,
        methode_selection: "ALEATOIRE",
      }),
    );
    await waitFor(() => expect(dialog).not.toBeInTheDocument());
  });

  it("blocks an empty label and links a server field error to its input", async () => {
    const user = userEvent.setup();
    renderWithClient(<StepVIIIZone mission={aMission()} step={open} />, [
      http.post(`${API_URL}/api/v1/planned-tests/`, () =>
        HttpResponse.json(
          { detail: "Données invalides.", errors: { libelle: ["Ce libellé existe déjà."] } },
          { status: 422 },
        ),
      ),
      ...baseHandlers(),
    ]);
    await user.click(
      await screen.findByRole("button", { name: "Ajouter un test à l'objectif OA-01" }),
    );
    await user.click(screen.getByRole("button", { name: "Enregistrer le test" }));
    expect(await screen.findByText("Le libellé du test est obligatoire.")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Libellé du test"), "Test");
    await user.selectOptions(screen.getByLabelText("Nature du test"), "AUTRE");
    await user.click(screen.getByRole("button", { name: "Enregistrer le test" }));
    const message = await screen.findByText("Ce libellé existe déjà.");
    const input = screen.getByLabelText("Libellé du test");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input.getAttribute("aria-describedby")).toContain(message.id);
    await waitFor(() => expect(input).toHaveFocus());
  });

  it("creates a programme for an objective without one", async () => {
    let body: unknown;
    const user = userEvent.setup();
    renderWithClient(<StepVIIIZone mission={aMission()} step={open} />, [
      http.post(`${API_URL}/api/v1/work-programs/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(aProgramme(), { status: 201 });
      }),
      ...baseHandlers({ programs: [], tests: [] }),
    ]);
    await user.click(
      await screen.findByRole("button", { name: "Créer le programme de l'objectif OA-01" }),
    );
    await user.click(await screen.findByRole("button", { name: "Enregistrer le programme" }));
    await waitFor(() =>
      expect(body).toEqual({
        mission: aMission().id,
        objectif: OBJECTIVE_ID,
        techniques: "",
        criteres_preuve: "",
      }),
    );
  });

  it("shows no write button when step VIII is closed", async () => {
    renderWithClient(
      <StepVIIIZone mission={aMission()} step={aStep({ numero: 8, statut: "VALIDEE" })} />,
      baseHandlers({
        programs: [aProgramme({ actions_possibles: [] })],
        tests: [aTest({ actions_possibles: [] })],
      }),
    );
    expect(await screen.findByText(/OA-01 : Vérifier/)).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.getByText(/Lecture seule/)).toBeInTheDocument();
  });

  it("does not render a load error as an empty list", async () => {
    renderWithClient(<StepVIIIZone mission={aMission()} step={open} />, [
      http.get(`${API_URL}/api/v1/work-programs/`, () => HttpResponse.json({}, { status: 500 })),
      ...baseHandlers(),
    ]);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Impossible de charger le programme de travail",
    );
    expect(screen.queryByText(/Aucun objectif d'audit n'est retenu/)).not.toBeInTheDocument();
  });

  it("lists the missing deliverables when the step cannot be completed", async () => {
    const user = userEvent.setup();
    const step = aStep({ numero: 8, statut: "EN_COURS", actions_possibles: ["TERMINER"] });
    renderWithClient(
      <>
        <StepVIIIZone mission={aMission()} step={step} />
        <StepActions step={step} />
      </>,
      [
        http.post(`${API_URL}/api/v1/mission-steps/${step.id}/complete/`, () =>
          HttpResponse.json(
            { detail: "Livrables manquants.", errors: { livrables: ["Programme de travail"] } },
            { status: 422 },
          ),
        ),
        ...baseHandlers(),
      ],
    );
    await user.click(await screen.findByRole("button", { name: "Terminer l'étape" }));
    expect(await screen.findByText("Programme de travail", { selector: "li" })).toBeInTheDocument();
  });

  it("has no axe violation, dialog open included", async () => {
    const user = userEvent.setup();
    const { container } = renderWithClient(
      <StepVIIIZone mission={aMission()} step={open} />,
      baseHandlers(),
    );
    await user.click(
      await screen.findByRole("button", { name: "Ajouter un test à l'objectif OA-01" }),
    );
    await screen.findByRole("dialog");
    expect((await axe(container, NO_CONTRAST)).violations).toEqual([]);
    expect((await axe(document.body, NO_CONTRAST)).violations).toEqual([]);
  });
});
