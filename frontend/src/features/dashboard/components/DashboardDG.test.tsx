import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { axe } from "vitest-axe";
import { describe, expect, it, vi } from "vitest";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { renderWithAuth } from "@/test/shell";
import * as api from "../api";
import { tableauDgFixture, tauxFixture } from "../fixtures";
import { DashboardDG } from "./DashboardDG";

const URL_DG = `${API_URL}/api/v1/dashboards/dg/`;
const t = fr.tableauxDirection;

function serve(data: object = tableauDgFixture) {
  server.use(http.get(URL_DG, () => HttpResponse.json(data)));
}

describe("DashboardDG", () => {
  it("affiche les taux, y compris les rapports diffusés", async () => {
    serve();
    renderWithAuth(<DashboardDG />, "DG");
    expect(await screen.findByRole("meter", { name: t.overallRate })).toHaveAttribute(
      "aria-valuenow",
      "40",
    );
    expect(screen.getByRole("meter", { name: t.dueRate })).toHaveAttribute("aria-valuenow", "60");
    const reports = screen.getByRole("table", { name: t.diffusedReports });
    expect(within(reports).getByText("MI-2026-001")).toBeInTheDocument();
  });

  it("dit « — (aucune action) » quand le taux est null", async () => {
    serve({
      ...tableauDgFixture,
      taux: { ...tauxFixture, taux: null, taux_echues: null, total: 0, cloturees: 0 },
      taux_par_direction: [],
    });
    renderWithAuth(<DashboardDG />, "DG");
    const label = await screen.findByText(t.overallRate);
    expect(label.parentElement).toHaveTextContent("— (aucune action)");
    expect(screen.queryByRole("meter", { name: t.overallRate })).not.toBeInTheDocument();
  });

  it("dit « Non couvert » en texte avec une icône", async () => {
    serve({
      ...tableauDgFixture,
      risques_eleves: {
        couverts: 0,
        non_couverts: 1,
        risques: [{ ...tableauDgFixture.risques_eleves.risques[0], couvert: false }],
      },
    });
    renderWithAuth(<DashboardDG />, "DG");
    const table = await screen.findByRole("table", { name: t.highRisks });
    const cell = within(table).getByText(t.notCovered);
    expect(cell.querySelector("svg")).not.toBeNull();
  });

  it("est en lecture seule : un seul bouton d'export, aucun bouton d'écriture", async () => {
    serve();
    renderWithAuth(<DashboardDG />, "DG");
    await screen.findByRole("meter", { name: t.overallRate });
    const names = screen
      .getAllByRole("button")
      .map((b) => b.textContent)
      .filter((n) => n !== fr.charts.showTable);
    expect(names).toEqual([t.exportRates]);
  });

  it("exporte les taux de l'année en Excel", async () => {
    serve();
    const spy = vi.spyOn(api, "downloadImplementationRates").mockResolvedValue();
    renderWithAuth(<DashboardDG />, "DG");
    await screen.findByRole("meter", { name: t.overallRate });
    await userEvent.click(screen.getByRole("button", { name: t.exportRates }));
    expect(spy).toHaveBeenCalledWith(new Date().getUTCFullYear(), "xlsx");
    spy.mockRestore();
  });

  it("signale l'échec de l'export", async () => {
    serve();
    const spy = vi.spyOn(api, "downloadImplementationRates").mockRejectedValue(new Error("x"));
    renderWithAuth(<DashboardDG />, "DG");
    await userEvent.click(await screen.findByRole("button", { name: t.exportRates }));
    expect(await screen.findByRole("alert")).toHaveTextContent(t.exportError);
    spy.mockRestore();
  });

  it("n'affiche pas une erreur de chargement comme un tableau vide", async () => {
    server.use(http.get(URL_DG, () => HttpResponse.json({ detail: "x" }, { status: 500 })));
    renderWithAuth(<DashboardDG />, "DG");
    expect(await screen.findByRole("alert")).toHaveTextContent(t.loadError);
    expect(screen.queryByText(t.diffusedReportsEmpty)).not.toBeInTheDocument();
  });

  it("n'a aucune violation d'accessibilité", async () => {
    serve();
    const { container } = renderWithAuth(<DashboardDG />, "DG");
    await screen.findByRole("meter", { name: t.overallRate });
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
