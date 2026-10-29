import { configure, screen, waitFor } from "@testing-library/react";
import { axe } from "vitest-axe";
import { http, HttpResponse } from "msw";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { ROLES, type Role } from "@/auth/types";
import { fr } from "@/i18n/fr";
import { NAV_GROUPS, navFor, rolesFor } from "@/layouts/navigation";
import { API_URL, server } from "@/test/msw";
import { renderRoutes } from "@/test/shell";
import { aMission, allRights, allSteps, MISSION_ID } from "@/features/missions/testUtils";
import { appRoutes } from "./routes";

// La page d'accueil du référentiel (cartographies) interroge l'API.
beforeEach(() => {
  server.use(
    http.get(`${API_URL}/api/v1/risk-maps/`, () =>
      HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
    ),
  );
});

// Chaque rendu monte le shell complet : marge pour jsdom.
beforeAll(() => {
  vi.setConfig({ testTimeout: 20000 });
  configure({ asyncUtilTimeout: 4000 });
});

const RESTRICTED: [string, string, readonly Role[]][] = [
  ["/missions", fr.nav.missions, ["RAI", "AUDITEUR", "AUDITE"]],
  ["/referentiel", fr.nav.referentiel, ["ADMIN", "RAI", "AUDITEUR", "DG"]],
  ["/administration", fr.utilisateurs.title, ["ADMIN"]],
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

describe("referentiel routes", () => {
  it("redirects /referentiel to the cartographies tab for a RAI", () => {
    const { router } = renderRoutes(appRoutes, "RAI", { path: "/referentiel" });
    expect(router.state.location.pathname).toBe("/referentiel/cartographies");
    expect(screen.getByRole("link", { name: "Cartographies" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("shows the forbidden view to an AUDITE on a sub-route", () => {
    renderRoutes(appRoutes, "AUDITE", { path: "/referentiel/cartographies" });
    expect(screen.getByText(fr.errors.forbiddenTitle)).toBeInTheDocument();
  });
});

describe("administration routes", () => {
  it("redirects an ADMIN from /administration to the users list", () => {
    const { router } = renderRoutes(appRoutes, "ADMIN", { path: "/administration" });
    expect(router.state.location.pathname).toBe("/administration/utilisateurs");
    expect(
      screen.getByRole("heading", { level: 1, name: fr.utilisateurs.title }),
    ).toBeInTheDocument();
  });

  it.each(["RAI", "AUDITE"] as const)("denies %s on the users sub-route", (role) => {
    renderRoutes(appRoutes, role, { path: "/administration/utilisateurs/7" });
    expect(screen.getByText(fr.errors.forbiddenTitle)).toBeInTheDocument();
  });
});

describe("referentiel risk map routes", () => {
  it("renders the risk map list page", async () => {
    renderRoutes(appRoutes, "RAI", { path: "/referentiel/cartographies" });
    expect(await screen.findByText(fr.refCartographie.emptyTitle)).toBeInTheDocument();
  });

  it("redirects the legacy add-risk URL to the path carrying the map", async () => {
    const { router } = renderRoutes(appRoutes, "RAI", {
      path: "/referentiel/risques/nouveau?cartographie=abc",
    });
    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/referentiel/cartographies/abc/risques/nouveau"),
    );
  });

  it("renders the risk form page and asks for a map when none is given", () => {
    renderRoutes(appRoutes, "RAI", { path: "/referentiel/risques/nouveau" });
    expect(screen.getByText(fr.refCartographie.riskMapMissing)).toBeInTheDocument();
  });
});

describe("programme annuel routes", () => {
  it("shows the forbidden view to an AUDITE", () => {
    renderRoutes(appRoutes, "AUDITE", { path: "/programme-annuel" });
    expect(
      screen.getByRole("heading", { level: 1, name: fr.errors.forbiddenTitle }),
    ).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(fr.errors.forbiddenText);
  });

  it("lets a DG reach the list page", () => {
    renderRoutes(appRoutes, "DG", { path: "/programme-annuel" });
    expect(
      screen.getByRole("heading", { level: 1, name: fr.programmation.title }),
    ).toBeInTheDocument();
  });

  it("mounts the line creation route", async () => {
    const planId = "3f2b8c1e-8a4d-4c55-9a0e-1b2c3d4e5f60";
    server.use(
      http.get(`${API_URL}/api/v1/audit-plans/${planId}/`, () =>
        HttpResponse.json({ id: planId, annee: 2026, statut: "BROUILLON" }),
      ),
    );
    renderRoutes(appRoutes, "RAI", { path: `/programme-annuel/${planId}/nouvelle-ligne` });
    expect(
      await screen.findByRole("heading", { level: 1, name: fr.programmationLignes.newTitle }),
    ).toBeInTheDocument();
  });
});

describe("page introuvable", () => {
  it("affiche une vue en français avec un lien vers l'accueil", () => {
    renderRoutes(appRoutes, "RAI", { path: "/inexistant" });
    expect(screen.getByRole("heading", { name: fr.errors.pageNotFoundTitle })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: fr.errors.backToDashboard })).toHaveAttribute(
      "href",
      "/",
    );
  });
});

describe("mission routes", () => {
  const path = `/missions/${MISSION_ID}`;

  function serve(mission = aMission()) {
    server.use(
      http.get(`${API_URL}/api/v1/missions/${MISSION_ID}/`, () => HttpResponse.json(mission)),
      http.get(`${API_URL}/api/v1/mission-steps/`, () => HttpResponse.json(allSteps())),
    );
  }

  it.each(["DG", "ADMIN"] as const)("denies /missions to %s", (role) => {
    renderRoutes(appRoutes, role, { path: "/missions" });
    expect(
      screen.getByRole("heading", { level: 1, name: fr.errors.forbiddenTitle }),
    ).toBeInTheDocument();
  });

  it("sends an AUDITE on a mission to its meetings", async () => {
    serve(aMission({ mes_droits: { ...allRights(false), voir_travaux: false } }));
    const { router } = renderRoutes(appRoutes, "AUDITE", { path });
    await waitFor(() => expect(router.state.location.pathname).toBe(`${path}/reunions`));
  });

  it("sends an auditor to the current step", async () => {
    serve();
    const { router } = renderRoutes(appRoutes, "AUDITEUR", { path });
    await waitFor(() => expect(router.state.location.pathname).toBe(`${path}/etapes/4`));
    expect(await screen.findAllByRole("link", { current: "step" })).toHaveLength(1);
  });

  it("hides the work tabs when the server denies voir_travaux", async () => {
    serve(aMission({ mes_droits: { ...allRights(false), voir_travaux: false } }));
    renderRoutes(appRoutes, "AUDITE", { path });
    expect(await screen.findByRole("link", { name: fr.missions.tabMeetings })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: fr.missions.tabInterviews })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: fr.missions.tabSteps })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: fr.missions.tabTracking })).not.toBeInTheDocument();
    expect(screen.getByText(fr.missions.documentsSoon)).toBeInTheDocument();
  });
});
