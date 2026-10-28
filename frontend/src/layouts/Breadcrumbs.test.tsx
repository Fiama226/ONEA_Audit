import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { renderWithAuth } from "@/test/shell";
import { Breadcrumbs } from "./Breadcrumbs";

describe("Breadcrumbs", () => {
  it("shows a single level on the dashboard", () => {
    renderWithAuth(<Breadcrumbs />, "RAI", "/");
    const nav = screen.getByRole("navigation", { name: fr.common.breadcrumb });
    expect(within(nav).getAllByRole("listitem")).toHaveLength(1);
    expect(within(nav).getByText(fr.nav.dashboard)).toHaveAttribute("aria-current", "page");
  });

  it("links back to the dashboard from a section", () => {
    renderWithAuth(<Breadcrumbs />, "RAI", "/missions");
    const nav = screen.getByRole("navigation", { name: fr.common.breadcrumb });
    expect(within(nav).getByRole("link", { name: fr.nav.dashboard })).toHaveAttribute("href", "/");
    expect(within(nav).getByText(fr.nav.missions)).toHaveAttribute("aria-current", "page");
  });

  it("marks the current crumb as a plain span, not a disabled link", () => {
    renderWithAuth(<Breadcrumbs />, "RAI", "/missions");
    const current = screen.getByText(fr.nav.missions);
    expect(current.tagName).toBe("SPAN");
    expect(current).not.toHaveAttribute("role");
    expect(current).not.toHaveAttribute("aria-disabled");
    expect(screen.queryByRole("link", { name: fr.nav.missions })).not.toBeInTheDocument();
  });

  it("labels a uuid segment as Détail under the referentiel", () => {
    renderWithAuth(
      <Breadcrumbs />,
      "RAI",
      "/referentiel/cartographies/3f2b8c1e-8a4d-4c55-9a0e-1b2c3d4e5f60",
    );
    const nav = screen.getByRole("navigation", { name: fr.common.breadcrumb });
    expect(
      within(nav)
        .getAllByRole("listitem")
        .map((li) => li.textContent),
    ).toEqual(["Tableau de bord", "Référentiel", "Cartographies", "Détail"]);
  });

  it("does not link the risques segment, which has no page of its own", () => {
    renderWithAuth(
      <Breadcrumbs />,
      "RAI",
      "/referentiel/risques/3f2b8c1e-8a4d-4c55-9a0e-1b2c3d4e5f60",
    );
    const nav = screen.getByRole("navigation", { name: fr.common.breadcrumb });
    expect(within(nav).getByText("Risques").tagName).toBe("SPAN");
    expect(within(nav).queryByRole("link", { name: "Risques" })).not.toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Référentiel" })).toBeInTheDocument();
  });
});
