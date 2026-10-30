import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { API_URL, server } from "@/test/msw";
import { renderRoutes } from "@/test/shell";
import {
  aSuiviAction,
  missionSuiviFixture,
  pageOf,
  recommandationSuivieFixture,
} from "../testUtils";
import { RegisterPage } from "./RegisterPage";

const download = vi.hoisted(() => vi.fn());
vi.mock("@/lib/download", () => ({ downloadBlob: download }));

const BASE = `${API_URL}/api/v1`;

function setup(role: "RAI" | "AUDITE" | "DG", path = "/recommandations") {
  const urls: string[] = [];
  server.use(
    http.get(`${BASE}/missions/`, () =>
      HttpResponse.json(pageOf([{ ...missionSuiviFixture, id: missionSuiviFixture.id }])),
    ),
    http.get(`${BASE}/directions/`, () => HttpResponse.json(pageOf([]))),
    http.get(`${BASE}/follow-up/recommendations/`, ({ request }) => {
      urls.push(request.url);
      return HttpResponse.json(pageOf([recommandationSuivieFixture]));
    }),
    http.get(`${BASE}/follow-up/actions/`, ({ request }) => {
      urls.push(request.url);
      return HttpResponse.json(
        pageOf([aSuiviAction({ statut: "EN_COURS", en_retard: true, jours_retard: 3 })]),
      );
    }),
    http.get(`${BASE}/follow-up/:kind/export/`, ({ request }) => {
      urls.push(request.url);
      return HttpResponse.arrayBuffer(new ArrayBuffer(2), {
        headers: { "Content-Disposition": 'attachment; filename="export.csv"' },
      });
    }),
  );
  const utils = renderRoutes([{ path: "/recommandations", element: <RegisterPage /> }], role, {
    path,
  });
  return { urls, ...utils };
}

beforeEach(() => download.mockReset());

describe("RegisterPage", () => {
  it("liste les recommandations par défaut et bascule vers les actions (paramètre vue)", async () => {
    const user = userEvent.setup();
    const { router } = setup("RAI");
    expect(await screen.findByText("Fiabiliser les inventaires")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Actions" }));
    expect(await screen.findByText("Formaliser le rapprochement mensuel")).toBeInTheDocument();
    expect(router.state.location.search).toContain("vue=actions");
  });

  it("conserve les filtres dans l'URL et les envoie au serveur", async () => {
    const user = userEvent.setup();
    const { router, urls } = setup("RAI", "/recommandations?vue=actions");
    await screen.findByText("Formaliser le rapprochement mensuel");
    await user.type(screen.getByLabelText("Année"), "2026");
    await user.click(screen.getByLabelText("En retard"));
    await waitFor(() => {
      expect(router.state.location.search).toContain("annee=2026");
      expect(router.state.location.search).toContain("en_retard=true");
    });
    await waitFor(() =>
      expect(urls.some((u) => u.includes("annee=2026") && u.includes("en_retard=true"))).toBe(true),
    );
  });

  it("relit les filtres de l'URL au chargement", async () => {
    setup("RAI", "/recommandations?vue=actions&annee=2025&en_retard=true");
    expect(await screen.findByLabelText("Année")).toHaveValue(2025);
    expect(screen.getByLabelText("En retard")).toBeChecked();
  });

  it("dit le retard en texte avec une icône d'alerte", async () => {
    setup("RAI", "/recommandations?vue=actions");
    expect(await screen.findByText("en retard de 3 j")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Action en retard" })).toBeInTheDocument();
    expect(screen.getByText("31/12/2026")).toBeInTheDocument();
  });

  it("propose « Mes actions » seulement à l'audité, sur la vue des actions", async () => {
    const { unmount } = setup("AUDITE", "/recommandations?vue=actions");
    expect(await screen.findByLabelText("Mes actions")).toBeInTheDocument();
    unmount();
    setup("RAI", "/recommandations?vue=actions");
    await screen.findByLabelText("En retard");
    expect(screen.queryByLabelText("Mes actions")).not.toBeInTheDocument();
  });

  it("exporte avec les filtres courants", async () => {
    const user = userEvent.setup();
    const { urls } = setup("RAI", "/recommandations?vue=actions&en_retard=true&annee=2026");
    await screen.findByText("Formaliser le rapprochement mensuel");
    await user.click(screen.getByRole("button", { name: "CSV" }));
    await waitFor(() => expect(download).toHaveBeenCalledTimes(1));
    const exportUrl = urls.find((u) => u.includes("/export/")) ?? "";
    expect(exportUrl).toContain("/follow-up/actions/export/");
    expect(exportUrl).toContain("format=csv");
    expect(exportUrl).toContain("en_retard=true");
    expect(exportUrl).toContain("annee=2026");
    expect(exportUrl).not.toContain("page");
  });

  it("signale une erreur de chargement sans la présenter comme une liste vide", async () => {
    server.use(
      http.get(`${BASE}/missions/`, () => HttpResponse.json(pageOf([]))),
      http.get(`${BASE}/directions/`, () => HttpResponse.json(pageOf([]))),
      http.get(`${BASE}/follow-up/recommendations/`, () => HttpResponse.json({}, { status: 500 })),
      http.get(`${BASE}/follow-up/actions/`, () => HttpResponse.json({}, { status: 500 })),
    );
    renderRoutes([{ path: "/recommandations", element: <RegisterPage /> }], "RAI", {
      path: "/recommandations",
    });
    expect(await screen.findByText("Le registre n'a pas pu être chargé.")).toBeInTheDocument();
    expect(screen.queryByText("Aucune recommandation ne correspond aux filtres.")).toBeNull();
  });

  it("affiche l'état vide quand aucun résultat ne correspond", async () => {
    server.use(
      http.get(`${BASE}/missions/`, () => HttpResponse.json(pageOf([]))),
      http.get(`${BASE}/directions/`, () => HttpResponse.json(pageOf([]))),
      http.get(`${BASE}/follow-up/recommendations/`, () => HttpResponse.json(pageOf([]))),
      http.get(`${BASE}/follow-up/actions/`, () => HttpResponse.json(pageOf([]))),
    );
    renderRoutes([{ path: "/recommandations", element: <RegisterPage /> }], "DG", {
      path: "/recommandations",
    });
    expect(
      await screen.findByText("Aucune recommandation ne correspond aux filtres."),
    ).toBeInTheDocument();
  });

  it("n'a aucune violation axe", async () => {
    const { container } = setup("RAI", "/recommandations?vue=actions");
    await screen.findByText("Formaliser le rapprochement mensuel");
    const results = await axe(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
