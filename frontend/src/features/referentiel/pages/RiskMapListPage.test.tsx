import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { API_URL, server } from "@/test/msw";
import { DRAFT, mockReferentiel, page, renderCarto, VALIDATED } from "../cartoFixtures";
import { RiskMapListPage } from "./RiskMapListPage";

const routes = [{ path: "/referentiel/cartographies", element: <RiskMapListPage /> }];
const path = "/referentiel/cartographies";
const empty = () =>
  server.use(http.get(`${API_URL}/api/v1/risk-maps/`, () => HttpResponse.json(page([]))));

describe("RiskMapListPage", () => {
  it("lists versions with their status and validator", async () => {
    mockReferentiel();
    renderCarto(routes, "AUDITEUR", path);
    const link = await screen.findByRole("link", { name: "2026" });
    expect(link).toHaveAttribute("href", `/referentiel/cartographies/${DRAFT.id}`);
    expect(screen.getByText("Validée")).toBeInTheDocument();
    expect(screen.getByText("Awa Ouedraogo")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Créer une cartographie" }),
    ).not.toBeInTheDocument();
  });

  it("shows the empty state with a create action for the RAI", async () => {
    empty();
    renderCarto(routes, "RAI", path);
    expect(
      await screen.findByText("Aucune cartographie des risques n'a encore été créée."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Créer une cartographie" })).toBeInTheDocument();
  });

  it("shows an explanation without action for other roles", async () => {
    empty();
    renderCarto(routes, "DG", path);
    expect(
      await screen.findByText("Aucune cartographie des risques n'a encore été créée."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Créer une cartographie" }),
    ).not.toBeInTheDocument();
  });

  it("shows an error state", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/risk-maps/`, () => HttpResponse.json({}, { status: 500 })),
    );
    renderCarto(routes, "RAI", path);
    expect(await screen.findByRole("alert")).toHaveTextContent("Impossible de charger");
  });

  it("creates a version with defaults and maps the 422 on annee to the field", async () => {
    empty();
    let body: unknown;
    server.use(
      http.post(`${API_URL}/api/v1/risk-maps/`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          {
            detail: "Données invalides.",
            errors: { annee: ["Une cartographie existe déjà pour cette année."] },
          },
          { status: 422 },
        );
      }),
    );
    const user = userEvent.setup();
    renderCarto(routes, "RAI", path);
    await user.click(await screen.findByRole("button", { name: "Créer une cartographie" }));
    const dialog = await screen.findByRole("dialog");
    const year = String(new Date().getFullYear());
    expect(within(dialog).getByLabelText("Année")).toHaveValue(year);
    expect(within(dialog).getByLabelText("Libellé")).toHaveValue(
      `Cartographie des risques ${year}`,
    );
    await user.click(within(dialog).getByRole("button", { name: "Créer" }));
    expect(
      await within(dialog).findByText("Une cartographie existe déjà pour cette année."),
    ).toBeInTheDocument();
    expect(body).toMatchObject({ annee: Number(year) });
    expect(within(dialog).getByLabelText("Année")).toHaveAttribute("aria-invalid", "true");
  });

  it("offers validated versions as source and resets the dialog on reopen", async () => {
    mockReferentiel();
    const user = userEvent.setup();
    renderCarto(routes, "RAI", path);
    await user.click(await screen.findByRole("button", { name: "Créer une cartographie" }));
    let dialog = await screen.findByRole("dialog");
    const source = within(dialog).getByLabelText("Copier les risques de");
    await waitFor(() => expect(within(source).getAllByRole("option")).toHaveLength(2));
    await user.clear(within(dialog).getByLabelText("Libellé"));
    await user.type(within(dialog).getByLabelText("Libellé"), "Autre");
    await user.click(within(dialog).getByRole("button", { name: "Annuler" }));
    await user.click(screen.getByRole("button", { name: "Créer une cartographie" }));
    dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByLabelText("Libellé")).toHaveValue(
      `Cartographie des risques ${new Date().getFullYear()}`,
    );
  });

  it("preselects the latest validated map as the copy source and keeps it clearable", async () => {
    mockReferentiel();
    let body: Record<string, unknown> = {};
    server.use(
      http.post(`${API_URL}/api/v1/risk-maps/`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(DRAFT, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderCarto(routes, "RAI", path);
    await user.click(await screen.findByRole("button", { name: "Créer une cartographie" }));
    const dialog = await screen.findByRole("dialog");
    const source = within(dialog).getByLabelText("Copier les risques de");
    await waitFor(() => expect(source).toHaveValue(VALIDATED.id));
    await user.selectOptions(source, "");
    expect(source).toHaveValue("");
    await user.click(within(dialog).getByRole("button", { name: "Créer" }));
    await waitFor(() => expect(body.annee).toBeDefined());
    expect(body.source).toBeUndefined();
  });

  it("has no axe violations", async () => {
    mockReferentiel();
    const { container } = renderCarto(routes, "RAI", path);
    await screen.findByRole("link", { name: "2026" });
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
