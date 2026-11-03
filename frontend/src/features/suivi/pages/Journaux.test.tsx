import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { API_URL, server } from "@/test/msw";
import { renderRoutes } from "@/test/shell";
import { demandeReportListeFixture, pageOf, relanceFixture } from "../testUtils";
import type { Relance } from "../types";
import { ExtensionRequestsPage } from "./ExtensionRequestsPage";
import { RemindersPage } from "./RemindersPage";

const BASE = `${API_URL}/api/v1`;

function serveReminders(urls: string[]) {
  server.use(
    http.get(`${BASE}/reminders/`, ({ request }) => {
      urls.push(request.url);
      const statut = new URL(request.url).searchParams.get("statut");
      const rows =
        statut === "SANS_ADRESSE"
          ? [{ ...relanceFixture, statut: "SANS_ADRESSE", erreur: "" } as Relance]
          : [relanceFixture as Relance];
      return HttpResponse.json(pageOf(rows));
    }),
  );
}

describe("RemindersPage", () => {
  it("applique le filtre de l'adresse (lien de la file de décisions)", async () => {
    const urls: string[] = [];
    serveReminders(urls);
    renderRoutes([{ path: "/recommandations/relances", element: <RemindersPage /> }], "RAI", {
      path: "/recommandations/relances?statut=SANS_ADRESSE",
    });
    expect(await screen.findByText(/Aucune adresse électronique/)).toBeInTheDocument();
    expect(new URL(urls[0] ?? "").searchParams.get("statut")).toBe("SANS_ADRESSE");
    expect(screen.getByRole("button", { name: "Sans adresse" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("change de filtre et conserve le choix dans l'URL", async () => {
    const urls: string[] = [];
    serveReminders(urls);
    const { router } = renderRoutes(
      [{ path: "/recommandations/relances", element: <RemindersPage /> }],
      "RAI",
      { path: "/recommandations/relances" },
    );
    await screen.findByText("Formaliser le rapprochement mensuel");
    await userEvent.click(screen.getByRole("button", { name: "En échec" }));
    await waitFor(() => expect(router.state.location.search).toBe("?statut=ECHEC"));
    await waitFor(() =>
      expect(urls.some((u) => new URL(u).searchParams.get("statut") === "ECHEC")).toBe(true),
    );
  });

  it("distingue l'erreur de chargement de la liste vide", async () => {
    server.use(
      http.get(`${BASE}/reminders/`, () => HttpResponse.json({ detail: "x" }, { status: 500 })),
    );
    renderRoutes([{ path: "/r", element: <RemindersPage /> }], "RAI", { path: "/r" });
    expect(await screen.findByRole("alert")).toHaveTextContent("n'a pas pu être chargé");
    expect(screen.queryByText(/Aucune relance/)).not.toBeInTheDocument();
  });

  it("affiche l'état vide quand le filtre ne renvoie rien", async () => {
    server.use(http.get(`${BASE}/reminders/`, () => HttpResponse.json(pageOf([]))));
    renderRoutes([{ path: "/r", element: <RemindersPage /> }], "RAI", { path: "/r" });
    expect(await screen.findByText(/Aucune relance ne correspond/)).toBeInTheDocument();
  });

  it("n'a aucune violation d'accessibilité", async () => {
    serveReminders([]);
    const { container } = renderRoutes([{ path: "/r", element: <RemindersPage /> }], "RAI", {
      path: "/r",
    });
    await screen.findByText("Formaliser le rapprochement mensuel");
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});

describe("ExtensionRequestsPage", () => {
  it("interroge les reports en attente et lie l'action", async () => {
    const urls: string[] = [];
    server.use(
      http.get(`${BASE}/follow-up/extension-requests/`, ({ request }) => {
        urls.push(request.url);
        return HttpResponse.json(pageOf([demandeReportListeFixture]));
      }),
    );
    renderRoutes([{ path: "/r", element: <ExtensionRequestsPage /> }], "RAI", {
      path: "/r?statut=EN_ATTENTE",
    });
    const link = await screen.findByRole("link", { name: "Formaliser le rapprochement mensuel" });
    expect(link).toHaveAttribute(
      "href",
      `/recommandations/actions/${demandeReportListeFixture.action}`,
    );
    expect(new URL(urls[0] ?? "").searchParams.get("statut")).toBe("EN_ATTENTE");
    expect(screen.getByRole("button", { name: "En attente" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("signale l'erreur de chargement sans la confondre avec une liste vide", async () => {
    server.use(
      http.get(`${BASE}/follow-up/extension-requests/`, () =>
        HttpResponse.json({ detail: "x" }, { status: 500 }),
      ),
    );
    renderRoutes([{ path: "/r", element: <ExtensionRequestsPage /> }], "RAI", { path: "/r" });
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByText(/Aucune demande de report/)).not.toBeInTheDocument();
  });
});
