import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import type { Role } from "@/auth/types";
import { fr } from "@/i18n/fr";
import { DashboardPage } from "@/features/dashboard/pages/DashboardPage";
import { renderRoutes } from "@/test/shell";
import { AppShell } from "./AppShell";

const routes = [
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <DashboardPage /> },
      { path: "/missions", element: <h1>Missions</h1> },
    ],
  },
];

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("AppShell", () => {
  it("exposes landmarks and a skip link", () => {
    renderRoutes(routes, "RAI");
    expect(screen.getByRole("link", { name: fr.shell.skipToContent })).toHaveAttribute(
      "href",
      "#contenu",
    );
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveAttribute("id", "contenu");
    expect(screen.getByRole("navigation", { name: fr.nav.primary })).toBeInTheDocument();
  });

  it("shows a disabled global search", () => {
    renderRoutes(routes, "RAI");
    expect(screen.getByPlaceholderText(fr.shell.searchPlaceholder)).toBeDisabled();
  });

  it("shows the user name and French role, and logs out", async () => {
    const logout = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderRoutes(routes, "RAI", { logout });
    await user.click(screen.getByRole("button", { name: new RegExp(fr.shell.userMenu) }));
    const menu = await screen.findByRole("menu");
    expect(within(menu).getByText("Awa Ouedraogo")).toBeInTheDocument();
    expect(within(menu).getByText(fr.roles.RAI)).toBeInTheDocument();
    await user.click(within(menu).getByRole("menuitem", { name: fr.auth.logout }));
    expect(logout).toHaveBeenCalledTimes(1);
  });

  it("collapses the sidebar and persists the choice", async () => {
    const user = userEvent.setup();
    const first = renderRoutes(routes, "RAI");
    await user.click(screen.getByRole("button", { name: fr.shell.collapseMenu }));
    expect(screen.getByRole("button", { name: fr.shell.expandMenu })).toBeInTheDocument();
    expect(localStorage.getItem("onea.sidebar")).toBe("collapsed");
    first.unmount();
    renderRoutes(routes, "RAI");
    expect(screen.getByRole("button", { name: fr.shell.expandMenu })).toBeInTheDocument();
  });

  it("still renders, expanded, when localStorage throws", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("denied");
    });
    const user = userEvent.setup();
    renderRoutes(routes, "RAI");
    await user.click(screen.getByRole("button", { name: fr.shell.collapseMenu }));
    expect(screen.getByRole("button", { name: fr.shell.expandMenu })).toBeInTheDocument();
  });

  it("opens the navigation drawer from the header button", async () => {
    const user = userEvent.setup();
    renderRoutes(routes, "ADMIN");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: fr.shell.openMenu }));
    const drawer = await screen.findByRole("dialog");
    expect(within(drawer).getByRole("link", { name: fr.nav.administration })).toBeInTheDocument();
  });

  it("closes the drawer after navigating", async () => {
    const user = userEvent.setup();
    renderRoutes(routes, "ADMIN");
    await user.click(screen.getByRole("button", { name: fr.shell.openMenu }));
    const drawer = await screen.findByRole("dialog");
    await user.click(within(drawer).getByRole("link", { name: fr.nav.missions }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it.each<Role>(["ADMIN", "RAI", "AUDITEUR", "AUDITE", "DG"])(
    "has no accessibility violation for %s",
    async (role) => {
      const { container } = renderRoutes(routes, role);
      const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
      expect(results.violations).toEqual([]);
    },
  );
});
