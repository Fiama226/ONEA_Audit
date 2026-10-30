import { configure, screen } from "@testing-library/react";
import { axe } from "vitest-axe";
import { beforeAll, describe, expect, it, vi } from "vitest";
import type { Role } from "@/auth/types";
import { fr } from "@/i18n/fr";
import { http, HttpResponse } from "msw";
import { API_URL, server } from "@/test/msw";
import { renderWithAuth } from "@/test/shell";
import { tableauDgFixture, tableauRaiFixture } from "./fixtures";
import { DashboardPage } from "./pages/DashboardPage";

const CASES: [Role, string, string, string][] = [
  ["AUDITEUR", fr.dashboard.auditeurTitle, fr.dashboard.auditeurAction, "Disponible au lot 3"],
  ["AUDITE", fr.dashboard.auditeTitle, fr.dashboard.auditeAction, "Disponible au lot 8"],
  ["ADMIN", fr.shell.adminTitle, fr.dashboard.adminAction, "Disponible au lot 8"],
];

// Les contrôles axe sont lents sous jsdom.
beforeAll(() => {
  vi.setConfig({ testTimeout: 20000 });
  configure({ asyncUtilTimeout: 15000 });
});

describe("DashboardPage", () => {
  it.each(CASES)("renders the %s dashboard", (role, title, action, note) => {
    renderWithAuth(<DashboardPage />, role);
    expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
    const button = screen.getByRole("button", { name: action });
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription(note);
  });

  it("renders the live RAI dashboard with the real 5x5 criticality scale", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/dashboards/rai/`, () => HttpResponse.json(tableauRaiFixture)),
    );
    renderWithAuth(<DashboardPage />, "RAI");
    expect(screen.getByRole("heading", { name: fr.dashboard.raiTitle })).toBeInTheDocument();
    const matrix = await screen.findByRole("table", { name: fr.dashboard.matrixLabel });
    expect(matrix.querySelectorAll("[data-level]")).toHaveLength(25);
    expect(matrix.querySelectorAll('[data-level="high"]')).toHaveLength(6);
    expect(screen.queryByText(fr.dashboard.implementationRate)).not.toBeInTheDocument();
  });

  it("renders the live DG dashboard", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/dashboards/dg/`, () => HttpResponse.json(tableauDgFixture)),
    );
    renderWithAuth(<DashboardPage />, "DG");
    expect(screen.getByRole("heading", { name: fr.dashboard.dgTitle })).toBeInTheDocument();
    expect(await screen.findByText(fr.dashboard.implementationRate)).toBeInTheDocument();
  });
  it.each(CASES)("has no accessibility violation for %s", async (role) => {
    const { container } = renderWithAuth(<DashboardPage />, role);
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
