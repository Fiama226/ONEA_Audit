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

const CASES: [Role, string][] = [["ADMIN", fr.shell.adminTitle]];

// Les contrôles axe sont lents sous jsdom.
beforeAll(() => {
  vi.setConfig({ testTimeout: 20000 });
  configure({ asyncUtilTimeout: 15000 });
});

describe("DashboardPage", () => {
  it.each([
    ["AUDITEUR", fr.dashboard.auditeurTitle, "auditor"],
    ["AUDITE", fr.dashboard.auditeTitle, "auditee"],
  ] as [Role, string, string][])("renders the live %s dashboard", async (role, title, path) => {
    server.use(
      http.get(`${API_URL}/api/v1/dashboards/${path}/`, () =>
        HttpResponse.json({}, { status: 500 }),
      ),
    );
    renderWithAuth(<DashboardPage />, role);
    expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
  it("renders the ADMIN dashboard with real shortcuts and the pending accounts", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/user-accounts/`, ({ request }) => {
        expect(new URL(request.url).searchParams.get("en_attente_connexion")).toBe("true");
        return HttpResponse.json({ count: 3, next: null, previous: null, results: [] });
      }),
    );
    renderWithAuth(<DashboardPage />, "ADMIN");
    expect(screen.getByRole("heading", { name: fr.shell.adminTitle })).toBeInTheDocument();
    for (const label of [
      fr.dashboard.adminUsers,
      fr.dashboard.adminTemplates,
      fr.dashboard.adminSignature,
      fr.dashboard.adminReferential,
    ]) {
      expect(screen.getByRole("link", { name: new RegExp(label) })).toBeInTheDocument();
    }
    expect(await screen.findByText(/3 comptes en attente de première connexion/)).toBeVisible();
    expect(screen.queryByText(/lot/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /piste d'audit/i })).not.toBeInTheDocument();
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
    server.use(
      http.get(`${API_URL}/api/v1/user-accounts/`, () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );
    const { container } = renderWithAuth(<DashboardPage />, role);
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
