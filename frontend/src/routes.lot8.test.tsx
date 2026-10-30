import { configure, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { ROLES, type Role } from "@/auth/types";
import { fr } from "@/i18n/fr";
import { navFor, rolesFor, SEGMENT_LABELS } from "@/layouts/navigation";
import { API_URL, server } from "@/test/msw";
import { renderRoutes } from "@/test/shell";
import { SUIVI_ID } from "@/features/suivi/fixtures";
import { appRoutes } from "./routes";

beforeAll(() => {
  vi.setConfig({ testTimeout: 20000 });
  configure({ asyncUtilTimeout: 15000 });
});

beforeEach(() => {
  server.use(
    http.get(`${API_URL}/api/v1/notifications/unread-count/`, () =>
      HttpResponse.json({ count: 0 }),
    ),
  );
});

const ALLOWED: readonly Role[] = ["RAI", "AUDITEUR", "AUDITE", "DG"];

describe("routes du lot 8", () => {
  it("déclare les rôles de /recommandations dans la navigation", () => {
    expect(rolesFor("/recommandations")).toEqual(ALLOWED);
  });

  describe.each(ROLES)("/recommandations en tant que %s", (role) => {
    it(ALLOWED.includes(role) ? "ouvre le registre" : "refuse l'accès", async () => {
      renderRoutes(appRoutes, role, { path: "/recommandations" });
      if (ALLOWED.includes(role)) {
        expect(
          await screen.findByRole("heading", { level: 1, name: fr.suivi.registerTitle }),
        ).toBeInTheDocument();
      } else {
        expect(
          screen.getByRole("heading", { level: 1, name: fr.errors.forbiddenTitle }),
        ).toBeInTheDocument();
        expect(
          screen.queryByRole("heading", { level: 1, name: fr.suivi.registerTitle }),
        ).not.toBeInTheDocument();
      }
    });
  });

  it("refuse la page d'une action à l'ADMIN", () => {
    renderRoutes(appRoutes, "ADMIN", { path: `/recommandations/actions/${SUIVI_ID}` });
    expect(
      screen.getByRole("heading", { level: 1, name: fr.errors.forbiddenTitle }),
    ).toBeInTheDocument();
  });

  it("ouvre la page d'une action pour l'audité", async () => {
    renderRoutes(appRoutes, "AUDITE", { path: `/recommandations/actions/${SUIVI_ID}` });
    expect(
      await screen.findByRole("heading", { level: 1, name: fr.suivi.actionTitle }),
    ).toBeInTheDocument();
    const crumbs = screen.getByRole("navigation", { name: fr.common.breadcrumb });
    expect(crumbs).toHaveTextContent(fr.nav.recommandations);
    expect(crumbs).toHaveTextContent(fr.suivi.crumbActions);
  });

  it.each([
    ["/notifications", fr.suivi.notificationsTitle],
    ["/recherche", fr.suivi.searchTitle],
  ])("ouvre %s à tout utilisateur connecté", async (path, title) => {
    renderRoutes(appRoutes, "ADMIN", { path });
    expect(await screen.findByRole("heading", { level: 1, name: title })).toBeInTheDocument();
  });

  it("garde « Recommandations » dans le menu de l'audité et du DG, pas de l'ADMIN", () => {
    const labels = (role: Role) =>
      navFor(role)
        .flatMap((g) => g.items)
        .map((i) => i.label);
    expect(labels("AUDITE")).toContain(fr.nav.recommandations);
    expect(labels("DG")).toContain(fr.nav.recommandations);
    expect(labels("ADMIN")).not.toContain(fr.nav.recommandations);
  });

  it("nomme les segments du fil d'Ariane", () => {
    expect(SEGMENT_LABELS.actions).toBe("Actions");
    expect(SEGMENT_LABELS.notifications).toBe("Notifications");
    expect(SEGMENT_LABELS.recherche).toBe("Recherche");
    expect(SEGMENT_LABELS["suivi-recommandations"]).toBe("Suivi des recommandations");
  });
});
