import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { API_URL, server } from "@/test/msw";
import {
  aConstatAudite,
  aReponse,
  constatHandlers,
  MISSION_ID,
  renderConstats,
} from "../testUtils";
import { ConstatsAuditePage } from "./ConstatsAuditePage";

const ROUTES = [{ path: "/missions/:id/constats", element: <ConstatsAuditePage /> }];
const PATH = `/missions/${MISSION_ID}/constats`;

const repondu = aConstatAudite({
  id: "11111111-1111-4111-8111-aaaaaaaaaaaa",
  reference: "C-01",
  derniere_reponse: aReponse(),
  reponse_cycle_courant: true,
  actions_possibles: [],
});
const aRepondre = aConstatAudite({
  id: "22222222-2222-4222-8222-bbbbbbbbbbbb",
  reference: "C-02",
  titre: "Écart de caisse",
});

describe("ConstatsAuditePage", () => {
  it("liste les constats avec la réponse de l'audité et filtre « À répondre »", async () => {
    const user = userEvent.setup();
    server.use(...constatHandlers({ constats: [repondu, aRepondre] }));
    renderConstats(PATH, ROUTES, { role: "AUDITE" });
    const table = await screen.findByRole("table");
    expect(within(table).getByText("Désaccord")).toBeInTheDocument();
    expect(within(table).getByText("En attente")).toBeInTheDocument();
    expect(within(table).getByRole("link", { name: "C-01" })).toHaveAttribute(
      "href",
      `${PATH}/${repondu.id}`,
    );
    await user.click(screen.getByLabelText("À répondre"));
    expect(screen.queryByRole("link", { name: "C-01" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "C-02" })).toBeInTheDocument();
  });

  it("indique qu'aucun constat n'a été soumis", async () => {
    server.use(...constatHandlers({ constats: [] }));
    renderConstats(PATH, ROUTES, { role: "AUDITE" });
    expect(await screen.findByText("Aucun constat ne vous a été soumis.")).toBeInTheDocument();
  });

  it("montre le chargement puis l'erreur, jamais un état vide", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/findings/`, () =>
        HttpResponse.json({ detail: "x" }, { status: 500 }),
      ),
      ...constatHandlers(),
    );
    renderConstats(PATH, ROUTES, { role: "AUDITE" });
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Impossible de charger les constats",
    );
    expect(screen.queryByText("Aucun constat ne vous a été soumis.")).not.toBeInTheDocument();
  });

  it("n'a aucune violation axe", async () => {
    server.use(...constatHandlers({ constats: [repondu, aRepondre] }));
    const { container } = renderConstats(PATH, ROUTES, { role: "AUDITE" });
    await screen.findByRole("table");
    expect(
      (await axe(container, { rules: { "color-contrast": { enabled: false } } })).violations,
    ).toEqual([]);
  });
});
