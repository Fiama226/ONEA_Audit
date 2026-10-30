import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, type RequestHandler } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { API_URL, server } from "@/test/msw";
import { constatKeys } from "../keys";
import {
  aConstat,
  aConstatAudite,
  aReponse,
  CONSTAT_ID,
  constatHandlers,
  ENTITE_ID,
  FICHE_ID,
  MISSION_ID,
  PROCESSUS_ID,
  renderConstats,
} from "../testUtils";
import type { Constat, ReponseAudite } from "../types";
import { ConstatPage } from "./ConstatPage";

const NO_CONTRAST = { rules: { "color-contrast": { enabled: false } } };
const ROUTES = [
  { path: "/missions/:id/constats/:constatId", element: <ConstatPage /> },
  { path: "/missions/:id/etapes/:numero", element: <p>Étape XIV</p> },
];
const BASE = `/missions/${MISSION_ID}/constats`;

function setup(
  path: string,
  {
    constat,
    role = "AUDITEUR",
    responses = [],
  }: { constat?: Constat; role?: "AUDITEUR" | "AUDITE" | "RAI"; responses?: ReponseAudite[] } = {},
  handlers: RequestHandler[] = [],
) {
  server.use(...constatHandlers({ constats: constat ? [constat] : [], responses }));
  return renderConstats(path, ROUTES, { role, handlers });
}

describe("ConstatPage - rédaction", () => {
  it("crée un constat avec fiches, entité et causes groupées", async () => {
    let body: Record<string, unknown> | undefined;
    const user = userEvent.setup();
    const created = aConstat({ statut: "BROUILLON", actions_possibles: ["MODIFIER"] });
    setup(`${BASE}/nouveau?fiche=${FICHE_ID}`, { constat: created }, [
      http.post(`${API_URL}/api/v1/findings/`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(created, { status: 201 });
      }),
    ]);
    expect(await screen.findByRole("heading", { name: "Nouveau constat" })).toBeInTheDocument();
    expect(await screen.findByLabelText("Fiche T-01")).toBeChecked();
    expect(screen.getByLabelText("Entité concernée")).toHaveValue(ENTITE_ID);
    await user.click(screen.getByRole("button", { name: "Ajouter une cause Méthodes" }));
    await user.type(screen.getByLabelText("Cause Méthodes n° 1"), "Pas de procédure");
    await user.selectOptions(screen.getByLabelText("Probabilité (1 à 5)"), "3");
    await user.selectOptions(screen.getByLabelText("Impact (1 à 5)"), "5");
    expect(screen.getByText("Score 15 · Élevé")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Enregistrer le constat" }));
    await waitFor(() => expect(body).toBeDefined());
    expect(body).toMatchObject({
      mission: MISSION_ID,
      titre: "Rapprochements bancaires",
      fiches: [FICHE_ID],
      entite: ENTITE_ID,
      processus: PROCESSUS_ID,
      probabilite: 3,
      impact: 5,
      causes: [{ categorie: "METHODES", description: "Pas de procédure", ordre: 0 }],
      recommandations: [],
    });
    expect(await screen.findByRole("heading", { name: "Constat C-01" })).toBeInTheDocument();
  });

  it("remplace les recommandations au PATCH (ordre = position)", async () => {
    let body: Record<string, unknown> | undefined;
    const user = userEvent.setup();
    const constat = aConstat({ statut: "BROUILLON", actions_possibles: ["MODIFIER", "SOUMETTRE"] });
    setup(`${BASE}/${CONSTAT_ID}`, { constat }, [
      http.patch(`${API_URL}/api/v1/findings/${CONSTAT_ID}/`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(constat);
      }),
    ]);
    await user.click(await screen.findByRole("button", { name: "Ajouter une recommandation" }));
    await user.type(screen.getByLabelText("Recommandation n° 2"), "Contrôler chaque mois");
    await user.click(screen.getByRole("button", { name: "Monter la recommandation n° 2" }));
    await user.click(screen.getByRole("button", { name: "Enregistrer le constat" }));
    await waitFor(() => expect(body).toBeDefined());
    expect(body?.recommandations).toEqual([
      { libelle: "Contrôler chaque mois", priorite: "MOYENNE", ordre: 0 },
      {
        id: "22222222-bbbb-4bbb-8bbb-222222222222",
        libelle: "Formaliser le rapprochement mensuel",
        priorite: "HAUTE",
        ordre: 1,
      },
    ]);
  });

  it("pose une erreur 422 de soumission sur le champ et le focalise", async () => {
    const user = userEvent.setup();
    const constat = aConstat({ statut: "BROUILLON", actions_possibles: ["MODIFIER", "SOUMETTRE"] });
    setup(`${BASE}/${CONSTAT_ID}`, { constat }, [
      http.post(`${API_URL}/api/v1/findings/${CONSTAT_ID}/submit/`, () =>
        HttpResponse.json(
          {
            detail: "Données invalides.",
            errors: { fait_constate: ["Le fait constaté est incomplet."] },
          },
          { status: 422 },
        ),
      ),
    ]);
    await user.click(await screen.findByRole("button", { name: "Soumettre à l'audité" }));
    const field = await screen.findByLabelText("Fait constaté");
    await waitFor(() => expect(field).toHaveFocus());
    expect(field).toHaveAccessibleDescription("Le fait constaté est incomplet.");
    expect(field).toHaveAttribute("aria-invalid", "true");
  });

  it("n'affiche pas « Valider le constat » quand le serveur ne l'autorise pas", async () => {
    setup(`${BASE}/${CONSTAT_ID}`, { constat: aConstat({ actions_possibles: [] }), role: "RAI" });
    await screen.findByRole("heading", { name: "Constat C-01" });
    expect(screen.queryByRole("button", { name: "Valider le constat" })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Enregistrer le constat" }),
    ).not.toBeInTheDocument();
  });

  it("propose la validation quand le serveur l'autorise", async () => {
    setup(`${BASE}/${CONSTAT_ID}`, {
      constat: aConstat({ actions_possibles: ["VALIDER", "RENVOYER"] }),
      role: "RAI",
    });
    expect(await screen.findByRole("button", { name: "Valider le constat" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Renvoyer à l'auteur" })).toBeInTheDocument();
  });

  it("retire le constat du cache après suppression", async () => {
    const user = userEvent.setup();
    const constat = aConstat({ statut: "BROUILLON", actions_possibles: ["MODIFIER", "SUPPRIMER"] });
    const { client } = setup(`${BASE}/${CONSTAT_ID}`, { constat }, [
      http.delete(
        `${API_URL}/api/v1/findings/${CONSTAT_ID}/`,
        () => new HttpResponse(null, { status: 204 }),
      ),
    ]);
    await user.click(await screen.findByRole("button", { name: "Supprimer le constat" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Supprimer" }));
    expect(await screen.findByText("Étape XIV")).toBeInTheDocument();
    expect(client.getQueryState(constatKeys.detail(CONSTAT_ID))).toBeUndefined();
  });

  it("affiche une erreur de chargement, jamais un formulaire vide", async () => {
    server.use(
      http.get(`${API_URL}/api/v1/findings/:id/`, () =>
        HttpResponse.json({ detail: "x" }, { status: 500 }),
      ),
      ...constatHandlers(),
    );
    renderConstats(`${BASE}/${CONSTAT_ID}`, ROUTES);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Impossible de charger les constats",
    );
    expect(screen.queryByLabelText("Titre du constat")).not.toBeInTheDocument();
  });

  it("n'a aucune violation axe, dialogue de suppression ouvert compris", async () => {
    const user = userEvent.setup();
    const constat = aConstat({ statut: "BROUILLON", actions_possibles: ["MODIFIER", "SUPPRIMER"] });
    const { container } = setup(`${BASE}/${CONSTAT_ID}`, { constat });
    await screen.findByRole("heading", { name: "Constat C-01" });
    expect((await axe(container, NO_CONTRAST)).violations).toEqual([]);
    await user.click(screen.getByRole("button", { name: "Supprimer le constat" }));
    const dialog = await screen.findByRole("alertdialog");
    expect((await axe(dialog, NO_CONTRAST)).violations).toEqual([]);
  });
});

describe("ConstatPage - vue de l'audité", () => {
  it("n'offre aucune action d'écriture hors « Répondre »", async () => {
    setup(`${BASE}/${CONSTAT_ID}`, { constat: aConstatAudite(), role: "AUDITE" });
    expect(await screen.findByRole("button", { name: "Répondre au constat" })).toBeInTheDocument();
    for (const name of [
      "Enregistrer le constat",
      "Supprimer le constat",
      "Soumettre à l'audité",
      "Valider le constat",
      "Renvoyer à l'auteur",
      "Ajouter une recommandation",
    ]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
    expect(screen.getByLabelText("Titre du constat")).toBeDisabled();
    expect(screen.queryByLabelText("Risque de la mission")).not.toBeInTheDocument();
    expect(screen.queryByText(/Fiche T-01/)).not.toBeInTheDocument();
  });

  it("bloque un désaccord sans commentaire puis envoie la réponse confirmée", async () => {
    const bodies: unknown[] = [];
    const user = userEvent.setup();
    const constat = aConstatAudite();
    setup(`${BASE}/${CONSTAT_ID}`, { constat, role: "AUDITE" }, [
      http.post(`${API_URL}/api/v1/finding-responses/`, async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json(aReponse(), { status: 201 });
      }),
    ]);
    await user.click(await screen.findByRole("button", { name: "Répondre au constat" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByLabelText("Je confirme")).not.toBeChecked();
    expect(within(dialog).getByLabelText("Je suis en accord")).not.toBeChecked();
    expect(within(dialog).getByLabelText("Je suis en désaccord")).not.toBeChecked();
    await user.click(within(dialog).getByLabelText("Je suis en désaccord"));
    expect(
      within(dialog).getByText(/Je suis en désaccord avec ce constat ; mon commentaire/),
    ).toBeInTheDocument();
    await user.click(within(dialog).getByLabelText("Je confirme"));
    await user.click(within(dialog).getByRole("button", { name: "Enregistrer ma réponse" }));
    expect(await within(dialog).findByText("Motivez votre désaccord.")).toBeInTheDocument();
    expect(bodies).toEqual([]);
    await user.type(within(dialog).getByLabelText("Commentaire"), "Le contrôle existe.");
    await user.click(within(dialog).getByRole("button", { name: "Enregistrer ma réponse" }));
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toEqual({
      constat: CONSTAT_ID,
      position: "DESACCORD",
      commentaire: "Le contrôle existe.",
      confirme: true,
      empreinte_soumise: constat.empreinte_soumise,
    });
    expect(await within(dialog).findByRole("status")).toHaveTextContent(
      `Réponse enregistrée le 29/10/2026 à 10:30. Empreinte : ${"a".repeat(64)}`,
    );
  });

  it("exige la case de confirmation, jamais pré-cochée", async () => {
    const bodies: unknown[] = [];
    const user = userEvent.setup();
    setup(`${BASE}/${CONSTAT_ID}`, { constat: aConstatAudite(), role: "AUDITE" }, [
      http.post(`${API_URL}/api/v1/finding-responses/`, async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json(aReponse(), { status: 201 });
      }),
    ]);
    await user.click(await screen.findByRole("button", { name: "Répondre au constat" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByLabelText("Je suis en accord"));
    await user.click(within(dialog).getByRole("button", { name: "Enregistrer ma réponse" }));
    expect(
      await within(dialog).findByText("Cochez la case pour confirmer votre réponse."),
    ).toBeInTheDocument();
    expect(bodies).toEqual([]);
  });

  it("signale une réponse sur une version antérieure après un nouveau cycle", async () => {
    setup(`${BASE}/${CONSTAT_ID}`, {
      constat: aConstatAudite({ cycle: 2, reponse_cycle_courant: false }),
      role: "AUDITE",
      responses: [
        aReponse({ id: "r1", cycle: 1, version_anterieure: true }),
        aReponse({ id: "r2", cycle: 2, position: "ACCORD", version_anterieure: false }),
      ],
    });
    expect(await screen.findByText("sur une version antérieure")).toBeInTheDocument();
    expect(screen.getAllByText("sur une version antérieure")).toHaveLength(1);
    expect(screen.getAllByText("Le contrôle existe.")).toHaveLength(2);
  });

  it("n'a aucune violation axe, dialogue de réponse ouvert compris", async () => {
    const user = userEvent.setup();
    const { container } = setup(`${BASE}/${CONSTAT_ID}`, {
      constat: aConstatAudite(),
      role: "AUDITE",
    });
    await user.click(await screen.findByRole("button", { name: "Répondre au constat" }));
    const dialog = await screen.findByRole("alertdialog");
    expect((await axe(dialog, NO_CONTRAST)).violations).toEqual([]);
    expect((await axe(container, NO_CONTRAST)).violations).toEqual([]);
  });

  it("n'appelle pas les fiches de test", async () => {
    let called = false;
    setup(`${BASE}/${CONSTAT_ID}`, { constat: aConstatAudite(), role: "AUDITE" }, [
      http.get(`${API_URL}/api/v1/test-sheets/`, () => {
        called = true;
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
    ]);
    await screen.findByRole("button", { name: "Répondre au constat" });
    expect(called).toBe(false);
  });
});
