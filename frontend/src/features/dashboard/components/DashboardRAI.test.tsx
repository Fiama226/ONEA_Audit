import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { renderWithAuth } from "@/test/shell";
import { tableauRaiFixture } from "../fixtures";
import { DashboardRAI } from "./DashboardRAI";

const URL_RAI = `${API_URL}/api/v1/dashboards/rai/`;
const t = fr.tableauxDirection;

function serve(data: object = tableauRaiFixture, seen: string[] = []) {
  server.use(
    http.get(URL_RAI, ({ request }) => {
      seen.push(new URL(request.url).search);
      return HttpResponse.json(data);
    }),
  );
  return seen;
}

describe("DashboardRAI", () => {
  it("affiche les tuiles et leurs valeurs", async () => {
    serve();
    renderWithAuth(<DashboardRAI />, "RAI");
    await screen.findByRole("list", { name: t.actionsByDirection });
    const tile = (label: string) => {
      const found = screen
        .getAllByText(label)
        .map((el) => el.closest("div.rounded-lg"))
        .find((el): el is HTMLElement => el !== null);
      if (!found) throw new Error(`Tuile introuvable : ${label}`);
      return found;
    };
    expect(within(tile(t.tileMissionsInProgress)).getByText("0")).toBeInTheDocument();
    expect(within(tile(t.tileMissionsLate)).getByText("0")).toBeInTheDocument();
    expect(within(tile(t.tileMilestones)).getByText("0")).toBeInTheDocument();
    expect(within(tile(t.tileActionsLate)).getByText("2")).toBeInTheDocument();
  });
  it("donne le tableau alternatif du graphique par direction", async () => {
    serve();
    renderWithAuth(<DashboardRAI />, "RAI");
    await screen.findByRole("list", { name: t.actionsByDirection });
    await userEvent.click(screen.getByRole("button", { name: fr.charts.showTable }));
    const table = screen.getByRole("table", { name: t.actionsByDirection });
    const row = within(table).getByRole("row", { name: /DAF/ });
    expect(
      within(row)
        .getAllByRole("cell")
        .map((c) => c.textContent),
    ).toEqual(["4", "3", "2"]);
    const detail = screen.getByRole("table", { name: t.abandonedDetail });
    expect(within(detail).getByRole("row", { name: /DAF/ })).toHaveTextContent("1");
  });

  it("mène la file de décisions à la liste filtrée", async () => {
    serve();
    renderWithAuth(<DashboardRAI />, "RAI");
    const link = await screen.findByRole("link", { name: new RegExp(t.queueToClose) });
    expect(link).toHaveAttribute("href", "/recommandations?vue=actions&statut=VERIFIEE");
  });

  it("mène reports et relances vers leurs écrans filtrés", async () => {
    serve();
    renderWithAuth(<DashboardRAI />, "RAI");
    const reports = await screen.findByRole("link", { name: new RegExp(t.queueExtensions) });
    expect(reports).toHaveAttribute("href", "/recommandations/reports?statut=EN_ATTENTE");
    expect(screen.getByRole("link", { name: new RegExp(t.queueRemindersFailed) })).toHaveAttribute(
      "href",
      "/recommandations/relances?statut=ECHEC",
    );
    expect(
      screen.getByRole("link", { name: new RegExp(t.queueRemindersNoAddress) }),
    ).toHaveAttribute("href", "/recommandations/relances?statut=SANS_ADRESSE");
  });

  it("lie les missions par statut à la liste filtrée", async () => {
    serve();
    renderWithAuth(<DashboardRAI />, "RAI");
    const link = await screen.findByRole("link", { name: /En suivi/ });
    expect(link).toHaveAttribute("href", "/missions?statut=EN_SUIVI");
  });

  it("refait la requête avec l'année choisie", async () => {
    const seen = serve();
    renderWithAuth(<DashboardRAI />, "RAI");
    await screen.findByRole("list", { name: t.actionsByDirection });
    await userEvent.selectOptions(screen.getByLabelText(t.yearLabel), "2025");
    await waitFor(() => expect(seen).toContain("?annee=2025"));
  });

  it("n'affiche pas une erreur de chargement comme un tableau vide", async () => {
    server.use(http.get(URL_RAI, () => HttpResponse.json({ detail: "x" }, { status: 500 })));
    renderWithAuth(<DashboardRAI />, "RAI");
    expect(await screen.findByRole("alert")).toHaveTextContent(t.loadError);
    expect(screen.queryByText(t.lateMissionsEmpty)).not.toBeInTheDocument();
  });

  it("annonce le chargement", () => {
    server.use(http.get(URL_RAI, () => new Promise(() => {})));
    renderWithAuth(<DashboardRAI />, "RAI");
    expect(screen.getByRole("status")).toHaveTextContent(t.loading);
  });

  it("n'a aucune violation d'accessibilité", async () => {
    serve();
    const { container } = renderWithAuth(<DashboardRAI />, "RAI");
    await screen.findByRole("list", { name: t.actionsByDirection });
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
