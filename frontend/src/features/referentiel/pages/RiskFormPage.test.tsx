import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { API_URL, server } from "@/test/msw";
import { DRAFT, mockReferentiel, R1, renderCarto, risk, VALIDATED } from "../cartoFixtures";
import { RiskFormPage } from "./RiskFormPage";

const routes = [
  { path: "/referentiel/risques/nouveau", element: <RiskFormPage /> },
  { path: "/referentiel/risques/:id", element: <RiskFormPage /> },
  { path: "/referentiel/cartographies/:id", element: <p>carto</p> },
];
const newPath = `/referentiel/risques/nouveau?cartographie=${DRAFT.id}`;

describe("RiskFormPage", () => {
  it("previews the score and level and derives the priority", async () => {
    mockReferentiel();
    const user = userEvent.setup();
    renderCarto(routes, "RAI", newPath);
    await user.selectOptions(await screen.findByLabelText("Probabilité"), "4");
    await user.selectOptions(screen.getByLabelText("Impact"), "4");
    expect(screen.getByText("Score 16 · Élevé")).toBeInTheDocument();
    expect(screen.getByLabelText("Priorité")).toHaveDisplayValue("Prioritaire");
  });

  it("keeps a manually chosen priority", async () => {
    mockReferentiel();
    const user = userEvent.setup();
    renderCarto(routes, "RAI", newPath);
    await user.selectOptions(await screen.findByLabelText("Priorité"), "2");
    await user.selectOptions(screen.getByLabelText("Probabilité"), "5");
    await user.selectOptions(screen.getByLabelText("Impact"), "5");
    expect(screen.getByLabelText("Priorité")).toHaveDisplayValue("Amélioration");
  });

  it("validates required fields and creates a risk", async () => {
    mockReferentiel();
    let body: unknown;
    server.use(
      http.post(`${API_URL}/api/v1/risks/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(R1, { status: 201 });
      }),
      http.get(`${API_URL}/api/v1/risks/${R1.id}/`, () => HttpResponse.json(R1)),
    );
    const user = userEvent.setup();
    const { router } = renderCarto(routes, "RAI", newPath);
    await user.click(await screen.findByRole("button", { name: "Enregistrer" }));
    expect(await screen.findByText("Le processus est obligatoire.")).toBeInTheDocument();
    expect(screen.getByText("Le libellé est obligatoire.")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Processus"), "p-1");
    await user.type(screen.getByLabelText("Libellé du risque"), "Fraude");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));
    await waitFor(() =>
      expect(body).toMatchObject({
        version: DRAFT.id,
        processus: "p-1",
        libelle: "Fraude",
        probabilite: 1,
        impact: 1,
        priorite: 3,
      }),
    );
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/referentiel/risques/${R1.id}`),
    );
  });

  it("maps server field errors", async () => {
    mockReferentiel();
    server.use(
      http.post(`${API_URL}/api/v1/risks/`, () =>
        HttpResponse.json(
          { detail: "Données invalides.", errors: { libelle: ["Ce libellé existe déjà."] } },
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderCarto(routes, "RAI", newPath);
    await user.selectOptions(await screen.findByLabelText("Processus"), "p-1");
    await user.type(screen.getByLabelText("Libellé du risque"), "Fraude");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));
    expect(await screen.findByText("Ce libellé existe déjà.")).toBeInTheDocument();
  });

  it("disables every field and hides save/delete on a validated version", async () => {
    const frozen = risk({ version: VALIDATED.id, version_statut: "VALIDEE" });
    mockReferentiel({ map: VALIDATED });
    server.use(http.get(`${API_URL}/api/v1/risks/${frozen.id}/`, () => HttpResponse.json(frozen)));
    renderCarto(routes, "RAI", `/referentiel/risques/${frozen.id}`);
    expect(await screen.findByLabelText("Libellé du risque")).toHaveValue(
      "Fraude sur les encaissements",
    );
    for (const el of screen.getAllByRole("textbox")) expect(el).toBeDisabled();
    for (const el of screen.getAllByRole("combobox")) expect(el).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Enregistrer" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Supprimer le risque" })).not.toBeInTheDocument();
    expect(screen.getByText(/lecture seule/)).toBeInTheDocument();
  });

  it("is read-only for an AUDITEUR on a draft, with the code shown", async () => {
    mockReferentiel();
    server.use(http.get(`${API_URL}/api/v1/risks/${R1.id}/`, () => HttpResponse.json(R1)));
    renderCarto(routes, "AUDITEUR", `/referentiel/risques/${R1.id}`);
    expect(await screen.findByLabelText("Libellé du risque")).toBeDisabled();
    expect(screen.getByText("12-FEP-R1")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enregistrer" })).not.toBeInTheDocument();
  });

  it("shows the server message when an edit is refused", async () => {
    mockReferentiel();
    server.use(
      http.get(`${API_URL}/api/v1/risks/${R1.id}/`, () => HttpResponse.json(R1)),
      http.patch(`${API_URL}/api/v1/risks/${R1.id}/`, () =>
        HttpResponse.json(
          { detail: "La cartographie est validée : modification impossible." },
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderCarto(routes, "RAI", `/referentiel/risques/${R1.id}`);
    await user.click(await screen.findByRole("button", { name: "Enregistrer" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("modification impossible");
  });

  it("deletes a risk after confirmation and returns to the map", async () => {
    mockReferentiel();
    server.use(
      http.get(`${API_URL}/api/v1/risks/${R1.id}/`, () => HttpResponse.json(R1)),
      http.delete(
        `${API_URL}/api/v1/risks/${R1.id}/`,
        () => new HttpResponse(null, { status: 204 }),
      ),
    );
    const user = userEvent.setup();
    const { router } = renderCarto(routes, "RAI", `/referentiel/risques/${R1.id}`);
    await user.click(await screen.findByRole("button", { name: "Supprimer le risque" }));
    await user.click(await screen.findByRole("button", { name: "Supprimer" }));
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/referentiel/cartographies/${DRAFT.id}`),
    );
  });

  it("has no axe violations", async () => {
    mockReferentiel();
    const { container } = renderCarto(routes, "RAI", newPath);
    await screen.findByLabelText("Probabilité");
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
