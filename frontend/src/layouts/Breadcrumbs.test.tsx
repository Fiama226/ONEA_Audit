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
});
