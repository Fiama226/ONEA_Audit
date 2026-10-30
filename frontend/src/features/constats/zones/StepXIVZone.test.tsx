import { screen, within } from "@testing-library/react";
import { http, HttpResponse, type RequestHandler } from "msw";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { aStep, allRights } from "@/features/missions/testUtils";
import { API_URL, server } from "@/test/msw";
import {
  aConstat,
  aConstatMission,
  aReponse,
  aSheet,
  constatHandlers,
  FICHE_ID,
  MISSION_ID,
} from "../testUtils";
import type { Constat } from "../types";
import { StepXIVZone } from "./StepXIVZone";

function setup({
  constats = [] as Constat[],
  sheets = [aSheet()] as unknown[],
  contribuer = true,
  handlers = [] as RequestHandler[],
} = {}) {
  const mission = aConstatMission({ mes_droits: { ...allRights(false), contribuer } });
  server.use(...handlers, ...constatHandlers({ mission, constats, sheets }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <StepXIVZone mission={mission} step={aStep({ numero: 14, romain: "XIV" })} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("StepXIVZone", () => {
  it("liste les constats avec niveau, statut et réponse de l'audité", async () => {
    setup({
      constats: [
        aConstat({ derniere_reponse: aReponse(), reponse_cycle_courant: true }),
        aConstat({
          id: "33333333-3333-4333-8333-333333333333",
          reference: "C-02",
          titre: "Écart de caisse",
          statut: "BROUILLON",
          niveau: null,
          score: null,
        }),
      ],
    });
    const table = await screen.findByRole("table");
    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((h) => h.textContent),
    ).toEqual(["Référence", "Titre", "Entité", "Niveau", "Statut", "Réponse de l'audité"]);
    expect(within(table).getByText("Désaccord")).toBeInTheDocument();
    expect(within(table).getByText("En attente")).toBeInTheDocument();
    expect(within(table).getByText("Élevé")).toBeInTheDocument();
    expect(within(table).getByText("Soumis à l'audité")).toBeInTheDocument();
  });

  it("signale les fiches ANOMALIE sans constat et préremplit la création", async () => {
    setup({
      sheets: [
        aSheet(),
        aSheet({
          id: "44444444-4444-4444-8444-444444444444",
          test_code: "T-02",
          constats: [{ id: "x", reference: "C-09" }],
        }),
        aSheet({
          id: "55555555-5555-4555-8555-555555555555",
          test_code: "T-03",
          conclusion: "SATISFAISANT",
        }),
      ],
    });
    const region = await screen.findByRole("region", { name: "Fiches ANOMALIE sans constat" });
    expect(within(region).getByText(/T-01/)).toBeInTheDocument();
    expect(within(region).queryByText(/T-02/)).not.toBeInTheDocument();
    expect(within(region).queryByText(/T-03/)).not.toBeInTheDocument();
    expect(
      within(region).getByRole("link", { name: /Créer un constat à partir de cette fiche T-01/ }),
    ).toHaveAttribute("href", `/missions/${MISSION_ID}/constats/nouveau?fiche=${FICHE_ID}`);
    expect(screen.getByRole("link", { name: "Créer un constat" })).toHaveAttribute(
      "href",
      `/missions/${MISSION_ID}/constats/nouveau`,
    );
  });

  it("masque la création sans le droit de contribuer", async () => {
    setup({ contribuer: false });
    await screen.findByText("Aucun constat pour le moment.");
    expect(screen.queryByRole("link", { name: "Créer un constat" })).not.toBeInTheDocument();
  });

  it("montre le chargement puis l'erreur, jamais un état vide", async () => {
    setup({
      handlers: [
        http.get(`${API_URL}/api/v1/findings/`, () =>
          HttpResponse.json({ detail: "x" }, { status: 500 }),
        ),
      ],
    });
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Impossible de charger les constats",
    );
    expect(screen.queryByText("Aucun constat pour le moment.")).not.toBeInTheDocument();
  });

  it("n'a aucune violation axe", async () => {
    const { container } = setup({ constats: [aConstat()] });
    await screen.findByRole("table");
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });
});
