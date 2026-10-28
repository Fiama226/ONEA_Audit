import { cleanup, screen, within } from "@testing-library/react";
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

  it("never nests a list item inside another list item (valid HTML)", () => {
    renderWithAuth(<Breadcrumbs />, "RAI", "/referentiel/cartographies");
    const nav = screen.getByRole("navigation", { name: fr.common.breadcrumb });
    expect(nav.querySelectorAll("li li")).toHaveLength(0);
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

  it("labels a map uuid segment as Cartographie under the referentiel", () => {
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
    ).toEqual(["Tableau de bord", "Référentiel", "Cartographies", "Cartographie"]);
  });

  const ID = "3f2b8c1e-8a4d-4c55-9a0e-1b2c3d4e5f60";
  const crumbs = (path: string) => {
    cleanup();
    renderWithAuth(<Breadcrumbs />, "RAI", path);
    const nav = screen.getByRole("navigation", { name: fr.common.breadcrumb });
    return within(nav)
      .getAllByRole("listitem")
      .map((li) => li.textContent);
  };

  it("labels a risk page 'Risque', without a dead 'Risques > Détail' pair", () => {
    expect(crumbs(`/referentiel/risques/${ID}`)).toEqual([
      "Tableau de bord",
      "Référentiel",
      "Risque",
    ]);
  });

  it("labels a map page 'Cartographie' and the add-risk page 'Nouveau risque'", () => {
    expect(crumbs(`/referentiel/cartographies/${ID}`)).toEqual([
      "Tableau de bord",
      "Référentiel",
      "Cartographies",
      "Cartographie",
    ]);
    expect(crumbs(`/referentiel/cartographies/${ID}/risques/nouveau`)).toEqual([
      "Tableau de bord",
      "Référentiel",
      "Cartographies",
      "Cartographie",
      "Nouveau risque",
    ]);
  });

  it("links the map crumb back to the map from the add-risk page", () => {
    renderWithAuth(<Breadcrumbs />, "RAI", `/referentiel/cartographies/${ID}/risques/nouveau`);
    expect(screen.getByRole("link", { name: "Cartographie" })).toHaveAttribute(
      "href",
      `/referentiel/cartographies/${ID}`,
    );
  });
});
