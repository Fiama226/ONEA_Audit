import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { API_URL, server } from "@/test/msw";
import { renderRoutes } from "@/test/shell";
import { reponseRechercheFixture, resultatFixture } from "../fixtures";
import { SearchPage } from "./SearchPage";

const URL_SEARCH = `${API_URL}/api/v1/search/`;

function setup(path: string, handler?: Parameters<typeof http.get>[1]) {
  const urls: string[] = [];
  server.use(
    http.get(URL_SEARCH, (info) => {
      urls.push(info.request.url);
      return (handler ?? (() => HttpResponse.json(reponseRechercheFixture)))(info);
    }),
  );
  const utils = renderRoutes([{ path: "/recherche", element: <SearchPage /> }], "RAI", { path });
  return { urls, ...utils };
}

describe("SearchPage", () => {
  it("n'appelle pas l'API sous 2 caractères", async () => {
    const { urls } = setup("/recherche?q=a");
    expect(await screen.findByText("Saisissez au moins 2 caractères.")).toBeVisible();
    expect(urls).toHaveLength(0);
  });

  it("groupe les résultats par type et surligne avec <mark>", async () => {
    setup("/recherche?q=rapprochement");
    expect(await screen.findByRole("heading", { level: 2, name: "Actions" })).toBeVisible();
    const link = screen.getByRole("link", { name: /Formaliser le rapprochement mensuel/ });
    expect(link).toHaveAttribute("href", `/recommandations/actions/${resultatFixture.objet_id}`);
    expect(link.querySelector("mark")).toHaveTextContent("rapprochement");
    expect(link).toHaveTextContent("MI-2026-001");
  });

  it("affiche un extrait <script> comme du texte", async () => {
    setup("/recherche?q=script", () =>
      HttpResponse.json({
        plus: false,
        resultats: [{ ...resultatFixture, extrait: "<script>alert(1)</script> \u0002x\u0003" }],
      }),
    );
    const link = await screen.findByRole("link");
    expect(link).toHaveTextContent("<script>alert(1)</script>");
    expect(link.querySelector("script")).toBeNull();
  });

  it("indique « D'autres résultats existent » quand plus est vrai", async () => {
    setup("/recherche?q=rapprochement", () =>
      HttpResponse.json({ ...reponseRechercheFixture, plus: true }),
    );
    expect(await screen.findByText(/D'autres résultats existent/)).toBeVisible();
  });

  it("aucun résultat", async () => {
    setup("/recherche?q=zzzz", () => HttpResponse.json({ resultats: [], plus: false }));
    expect(await screen.findByText("Aucun résultat.")).toBeVisible();
  });

  it("signale le mode dégradé quand le moteur est indisponible", async () => {
    setup("/recherche?q=audit", () =>
      HttpResponse.json({ ...reponseRechercheFixture, degrade: true }),
    );
    expect(
      await screen.findByText(/Le moteur de recherche est indisponible : seules les missions/),
    ).toBeVisible();
  });

  it("propose de réessayer quand la recherche est indisponible", async () => {
    const user = userEvent.setup();
    const { urls } = setup("/recherche?q=abc", () => HttpResponse.json({}, { status: 503 }));
    await screen.findByRole("alert");
    await user.click(screen.getByRole("button", { name: "Réessayer" }));
    await vi.waitFor(() => expect(urls.length).toBeGreaterThan(1));
  });

  it("traduit 503 et 429", async () => {
    const a = setup("/recherche?q=abc", () => HttpResponse.json({}, { status: 503 }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "La recherche est momentanément indisponible. Réessayez plus tard.",
    );
    a.unmount();
    setup("/recherche?q=abc", () => HttpResponse.json({}, { status: 429 }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Trop de recherches en peu de temps : patientez une minute.",
    );
  });

  it("gère proprement le 403 de l'administrateur", async () => {
    setup("/recherche?q=abc", () => HttpResponse.json({}, { status: 403 }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "La recherche n'est pas disponible pour votre profil.",
    );
  });

  it("anti-rebond : la saisie déclenche une seule requête", async () => {
    const { urls } = setup("/recherche");
    const user = userEvent.setup();
    await user.type(screen.getByRole("searchbox", { name: "Rechercher" }), "rapp");
    await screen.findByRole("heading", { level: 2, name: "Actions" });
    expect(urls).toHaveLength(1);
    expect(urls[0]).toContain("q=rapp");
  });

  it("les liens de résultats sont atteignables au clavier et sans violation axe", async () => {
    const { container } = setup("/recherche?q=rapprochement");
    const link = await screen.findByRole("link", { name: /Formaliser/ });
    const user = userEvent.setup();
    await user.tab(); // champ
    await user.tab(); // première case du filtre
    link.focus();
    expect(link).toHaveFocus();
    expect((await axe(container)).violations).toEqual([]);
  });
});
