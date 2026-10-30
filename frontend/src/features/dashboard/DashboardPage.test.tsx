import { configure, screen } from "@testing-library/react";
import { axe } from "vitest-axe";
import { beforeAll, describe, expect, it, vi } from "vitest";
import type { Role } from "@/auth/types";
import { fr } from "@/i18n/fr";
import { renderWithAuth } from "@/test/shell";
import { DashboardPage } from "./pages/DashboardPage";

const CASES: [Role, string, string, string][] = [
  ["RAI", fr.dashboard.raiTitle, fr.dashboard.raiAction, "Disponible au lot 3"],
  ["AUDITEUR", fr.dashboard.auditeurTitle, fr.dashboard.auditeurAction, "Disponible au lot 3"],
  ["AUDITE", fr.dashboard.auditeTitle, fr.dashboard.auditeAction, "Disponible au lot 8"],
  ["DG", fr.dashboard.dgTitle, fr.dashboard.dgAction, "Disponible au lot 7"],
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

  it("shows only the RAI dashboard content to the RAI", () => {
    renderWithAuth(<DashboardPage />, "RAI");
    expect(screen.getByText(fr.dashboard.criticality)).toBeInTheDocument();
    expect(screen.queryByText(fr.dashboard.implementationRate)).not.toBeInTheDocument();
  });

  it("renders the real 5x5 criticality scale for the RAI", () => {
    renderWithAuth(<DashboardPage />, "RAI");
    const matrix = screen.getByRole("table", { name: fr.dashboard.matrixLabel });
    expect(matrix.querySelectorAll("[data-level]")).toHaveLength(25);
    expect(matrix.querySelectorAll('[data-level="high"]')).toHaveLength(6);
  });

  it.each(CASES)("has no accessibility violation for %s", async (role) => {
    const { container } = renderWithAuth(<DashboardPage />, role);
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
