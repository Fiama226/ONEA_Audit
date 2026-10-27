import { configure, screen } from "@testing-library/react";
import { axe } from "vitest-axe";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { ROLES, type Role } from "@/auth/types";
import { fr } from "@/i18n/fr";
import { NAV_GROUPS, navFor, rolesFor } from "@/layouts/navigation";
import { renderRoutes } from "@/test/shell";
import { appRoutes } from "./routes";

// Chaque rendu monte le shell complet : marge pour jsdom.
beforeAll(() => {
  vi.setConfig({ testTimeout: 20000 });
  configure({ asyncUtilTimeout: 4000 });
});

const RESTRICTED: [string, string, readonly Role[]][] = [
  ["/referentiel", fr.nav.referentiel, ["ADMIN", "RAI", "AUDITEUR"]],
  ["/administration", fr.nav.administration, ["ADMIN"]],
];

describe("guarded routes", () => {
  it.each(RESTRICTED)("%s allows exactly the roles declared in navigation", (path, _, roles) => {
    expect(rolesFor(path)).toEqual(roles);
  });

  describe.each(RESTRICTED)("%s", (path, title, roles) => {
    it.each(ROLES)("as %s", (role) => {
      renderRoutes(appRoutes, role, { path });
      if (roles.includes(role)) {
        expect(screen.getByRole("heading", { level: 1, name: title })).toBeInTheDocument();
        expect(screen.getByText(fr.shell.comingSoonTitle)).toBeInTheDocument();
        expect(screen.queryByText(fr.errors.forbiddenTitle)).not.toBeInTheDocument();
      } else {
        expect(
          screen.getByRole("heading", { level: 1, name: fr.errors.forbiddenTitle }),
        ).toBeInTheDocument();
        expect(screen.getByRole("status")).toHaveTextContent(fr.errors.forbiddenText);
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(screen.getByRole("link", { name: fr.errors.backToDashboard })).toHaveAttribute(
          "href",
          "/",
        );
        expect(screen.queryByText(fr.shell.comingSoonTitle)).not.toBeInTheDocument();
      }
    });
  });

  it("has no accessibility violation on the forbidden view", async () => {
    const { container } = renderRoutes(appRoutes, "AUDITE", { path: "/administration" });
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});

describe("sidebar and routes agree", () => {
  const paths = NAV_GROUPS.flatMap((g) => g.items.map((i) => i.to));

  it.each(ROLES)("for %s every entry is visible iff its route is accessible", (role) => {
    const visible = new Set(navFor(role).flatMap((g) => g.items.map((i) => i.to)));
    for (const path of paths) {
      const accessible = rolesFor(path)?.includes(role) ?? true;
      expect(visible.has(path), `${role} ${path}`).toBe(accessible);
    }
  });

  it.each(ROLES)("for %s hidden entries lead to the forbidden view", (role) => {
    const visible = new Set(navFor(role).flatMap((g) => g.items.map((i) => i.to)));
    for (const path of paths.filter((p) => !visible.has(p))) {
      const { unmount } = renderRoutes(appRoutes, role, { path });
      expect(
        screen.getByRole("heading", { level: 1, name: fr.errors.forbiddenTitle }),
      ).toBeInTheDocument();
      unmount();
    }
  });
});
