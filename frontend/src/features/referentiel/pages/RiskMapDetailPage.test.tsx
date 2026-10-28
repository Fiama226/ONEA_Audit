import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { API_URL, server } from "@/test/msw";
import { DRAFT, mockReferentiel, renderCarto, VALIDATED } from "../cartoFixtures";
import { RiskMapDetailPage } from "./RiskMapDetailPage";

const routes = [{ path: "/referentiel/cartographies/:id", element: <RiskMapDetailPage /> }];
const draftPath = `/referentiel/cartographies/${DRAFT.id}`;

describe("RiskMapDetailPage", () => {
  let restoreUrl = () => {};
  afterEach(() => {
    restoreUrl();
    restoreUrl = () => {};
    vi.unstubAllGlobals();
  });

  it("filters the risk list from a matrix cell, reflects it in the URL and clears it", async () => {
    const seen = mockReferentiel();
    const user = userEvent.setup();
    const { router } = renderCarto(routes, "RAI", draftPath);
    expect(await screen.findByText("Retard de facturation")).toBeInTheDocument();
    expect(screen.getByText("Fraude sur les encaissements")).toBeInTheDocument();

    await user.click(await screen.findByRole("button", { name: /Probabilité 3, impact 5/i }));

    await waitFor(() =>
      expect(screen.queryByText("Retard de facturation")).not.toBeInTheDocument(),
    );
    expect(screen.getByText("12-FEP-R1")).toBeInTheDocument();
    expect(seen.some((s) => s.includes("probabilite=3") && s.includes("impact=5"))).toBe(true);
    expect(router.state.location.search).toContain("probabilite=3");
    expect(screen.getByText(/Probabilité 3 × impact 5/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Effacer le filtre" }));
    expect(await screen.findByText("Retard de facturation")).toBeInTheDocument();
    expect(router.state.location.search).toBe("");
  });

  it("is keyboard accessible on matrix cells", async () => {
    mockReferentiel();
    const user = userEvent.setup();
    const { router } = renderCarto(routes, "RAI", draftPath);
    const cell = await screen.findByRole("button", { name: /Probabilité 3, impact 5/i });
    cell.focus();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(router.state.location.search).toContain("impact=5"));
  });

  it("shows the frozen banner and hides edit controls on a validated version", async () => {
    mockReferentiel({ map: VALIDATED });
    renderCarto(routes, "RAI", `/referentiel/cartographies/${VALIDATED.id}`);
    expect(
      await screen.findByText(
        /Cartographie validée le 10\/02\/2026 par Awa Ouedraogo : lecture seule\./,
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ajouter un risque" })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Valider la cartographie" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Exporter en CSV" })).toBeInTheDocument();
  });

  it("gives an AUDITEUR export and compare but no write buttons on a draft", async () => {
    mockReferentiel();
    renderCarto(routes, "AUDITEUR", draftPath);
    expect(await screen.findByRole("button", { name: "Exporter en Excel" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ajouter un risque" })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Valider la cartographie" }),
    ).not.toBeInTheDocument();
    expect(await screen.findByLabelText("Comparer avec une autre version")).toBeInTheDocument();
  });

  it("explains irreversibility and shows the server 422 message in the dialog", async () => {
    mockReferentiel({ risks: [] });
    server.use(
      http.post(`${API_URL}/api/v1/risk-maps/${DRAFT.id}/validate/`, () =>
        HttpResponse.json(
          { detail: "Une cartographie vide ne peut pas être validée." },
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderCarto(routes, "RAI", draftPath);
    await user.click(await screen.findByRole("button", { name: "Valider la cartographie" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(
      within(dialog).getByText(
        "Une fois validée, la cartographie est figée : aucun risque ne pourra plus être ajouté, modifié ou supprimé.",
      ),
    ).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Valider définitivement" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "Une cartographie vide ne peut pas être validée.",
    );
  });

  it("calls the xlsx export endpoint", async () => {
    mockReferentiel();
    let type = "";
    server.use(
      http.get(`${API_URL}/api/v1/risk-maps/${DRAFT.id}/export/`, ({ request }) => {
        type = new URL(request.url).searchParams.get("type") ?? "";
        return new HttpResponse("data", {
          headers: { "Content-Disposition": 'attachment; filename="carto.xlsx"' },
        });
      }),
    );
    const originalCreate = URL.createObjectURL;
    const originalRevoke = URL.revokeObjectURL;
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    restoreUrl = () => {
      URL.createObjectURL = originalCreate;
      URL.revokeObjectURL = originalRevoke;
    };
    const user = userEvent.setup();
    renderCarto(routes, "RAI", draftPath);
    await user.click(await screen.findByRole("button", { name: "Exporter en Excel" }));
    await waitFor(() => expect(type).toBe("xlsx"));
  });

  it("shows an export error without leaving the page", async () => {
    mockReferentiel();
    server.use(
      http.get(`${API_URL}/api/v1/risk-maps/${DRAFT.id}/export/`, () =>
        HttpResponse.json({ detail: "Export indisponible." }, { status: 500 }),
      ),
    );
    const user = userEvent.setup();
    renderCarto(routes, "RAI", draftPath);
    await user.click(await screen.findByRole("button", { name: "Exporter en CSV" }));
    expect(await screen.findByText("Export indisponible.")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /Cartographie des risques 2026/ }),
    ).toBeInTheDocument();
  });

  it("does not navigate when choosing a version, only on the Comparer button", async () => {
    mockReferentiel();
    const user = userEvent.setup();
    const { router } = renderCarto(routes, "RAI", draftPath);
    await user.selectOptions(
      await screen.findByLabelText("Comparer avec une autre version"),
      VALIDATED.id,
    );
    expect(router.state.location.pathname).toBe(draftPath);
    await user.click(screen.getByRole("button", { name: "Comparer" }));
    expect(router.state.location.pathname).toBe(`${draftPath}/comparer`);
    expect(router.state.location.search).toBe(`?avec=${VALIDATED.id}`);
  });

  it("debounces the search and keeps the previous rows while loading", async () => {
    const seen = mockReferentiel();
    const user = userEvent.setup();
    renderCarto(routes, "RAI", draftPath);
    await screen.findByText("Retard de facturation");
    const before = seen.length;
    await user.type(screen.getByLabelText("Recherche"), "retard");
    await waitFor(() => expect(seen.some((s) => s.includes("q=retard"))).toBe(true));
    expect(seen.filter((s) => s.includes("q=")).every((s) => s.includes("q=retard"))).toBe(true);
    expect(seen.length - before).toBe(1);
  });

  it("prints every page of the filtered set", async () => {
    const seen = mockReferentiel();
    const print = vi.fn();
    vi.stubGlobal("print", print);
    const user = userEvent.setup();
    renderCarto(routes, "AUDITEUR", draftPath);
    await user.click(await screen.findByRole("button", { name: "Imprimer" }));
    await waitFor(() => expect(print).toHaveBeenCalledTimes(1));
    expect(seen.some((s) => s.includes("page_size=200"))).toBe(true);
  });

  it("has no axe violations", async () => {
    mockReferentiel();
    const { container } = renderCarto(routes, "RAI", draftPath);
    await screen.findByText("Retard de facturation");
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
