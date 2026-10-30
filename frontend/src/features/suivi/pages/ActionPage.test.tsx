import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { API_URL, server } from "@/test/msw";
import { renderRoutes } from "@/test/shell";
import {
  aSuiviAction,
  demandeReportFixture,
  evenementFixture,
  pageOf,
  preuveFixture,
  PREUVE_ID,
  SUIVI_ID,
} from "../testUtils";
import type { ActionSuivie, EvenementAction, PreuveMiseEnOeuvre } from "../types";
import { ActionPage } from "./ActionPage";

const upload = vi.hoisted(() => vi.fn());
const download = vi.hoisted(() => vi.fn());
vi.mock("@/api/upload", () => ({ uploadWithProgress: upload }));
vi.mock("@/lib/download", () => ({ downloadBlob: download }));

const BASE = `${API_URL}/api/v1/follow-up`;

type State = {
  action: ActionSuivie;
  preuves: PreuveMiseEnOeuvre[];
  events: EvenementAction[];
  posts: { path: string; body: unknown }[];
};

function setup(
  role: "RAI" | "AUDITEUR" | "AUDITE" | "DG",
  action: Partial<ActionSuivie>,
  options: { preuves?: PreuveMiseEnOeuvre[]; events?: EvenementAction[] } = {},
) {
  const state: State = {
    action: aSuiviAction(action),
    preuves: options.preuves ?? [],
    events: options.events ?? [evenementFixture],
    posts: [],
  };
  server.use(
    http.get(`${BASE}/actions/${SUIVI_ID}/`, () => HttpResponse.json(state.action)),
    http.get(`${BASE}/actions/${SUIVI_ID}/events/`, () => HttpResponse.json(state.events)),
    http.get(`${BASE}/evidence/`, () => HttpResponse.json(pageOf(state.preuves))),
    http.post(`${BASE}/actions/${SUIVI_ID}/:kind/`, async ({ request, params }) => {
      state.posts.push({ path: String(params.kind), body: await request.json() });
      return HttpResponse.json(state.action);
    }),
    http.post(`${BASE}/extension-requests/`, async ({ request }) => {
      state.posts.push({ path: "extension", body: await request.json() });
      return HttpResponse.json(demandeReportFixture, { status: 201 });
    }),
  );
  const utils = renderRoutes(
    [{ path: "/recommandations/actions/:id", element: <ActionPage /> }],
    role,
    { path: `/recommandations/actions/${SUIVI_ID}` },
  );
  return { state, ...utils };
}

beforeEach(() => {
  upload.mockReset();
  download.mockReset();
});

describe("ActionPage : audité responsable", () => {
  it("démarre l'action", async () => {
    const user = userEvent.setup();
    const { state } = setup("AUDITE", {
      statut: "A_LANCER",
      actions_possibles: ["DEMARRER", "DEPOSER_PREUVE", "DEMANDER_REPORT", "COMMENTER"],
    });
    await user.click(await screen.findByRole("button", { name: "Démarrer" }));
    await waitFor(() => expect(state.posts).toContainEqual({ path: "start", body: {} }));
    expect(screen.queryByRole("button", { name: "Vérifier" })).not.toBeInTheDocument();
  });

  it("n'autorise « Déclarer réalisée » qu'avec une preuve, puis envoie le commentaire", async () => {
    const user = userEvent.setup();
    const { state } = setup("AUDITE", {
      statut: "EN_COURS",
      nombre_preuves: 0,
      actions_possibles: ["DECLARER_REALISEE", "DEPOSER_PREUVE", "COMMENTER"],
    });
    const declare = await screen.findByRole("button", { name: "Déclarer réalisée" });
    expect(declare).toBeDisabled();
    expect(screen.getByText("Déposez au moins une preuve de mise en œuvre.")).toBeInTheDocument();
    expect(declare).toHaveAccessibleDescription("Déposez au moins une preuve de mise en œuvre.");

    upload.mockImplementation(
      async (_url: string, _form: FormData, onProgress: (r: number) => void) => {
        onProgress(0.5);
        state.preuves = [preuveFixture];
        state.action = { ...state.action, nombre_preuves: 1 };
        return preuveFixture;
      },
    );
    await user.type(screen.getByLabelText("Libellé de la preuve"), "Rapprochement d'octobre");
    await user.upload(
      screen.getByLabelText("Fichier"),
      new File(["pdf"], "rapprochement.pdf", { type: "application/pdf" }),
    );
    await user.click(screen.getByRole("button", { name: "Déposer la preuve" }));
    expect(upload).toHaveBeenCalledTimes(1);
    expect(upload.mock.calls[0]?.[0]).toContain("/follow-up/evidence/");

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Déclarer réalisée" })).toBeEnabled(),
    );
    expect(await screen.findByText(/1\. Rapprochement d'octobre/)).toBeInTheDocument();
    expect(screen.getByText("e3b0c442…b855")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Déclarer réalisée" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Commentaire"), "Rapprochement signé");
    await user.click(within(dialog).getByRole("button", { name: "Déclarer réalisée" }));
    await waitFor(() =>
      expect(state.posts).toContainEqual({
        path: "declare-done",
        body: { commentaire: "Rapprochement signé" },
      }),
    );
  });

  it("refuse une date de report antérieure à l'échéance par une erreur de champ", async () => {
    const user = userEvent.setup();
    const { state } = setup("AUDITE", {
      statut: "EN_COURS",
      actions_possibles: ["DEMANDER_REPORT", "COMMENTER"],
    });
    await screen.findByRole("heading", { name: "Report d'échéance" });
    const date = screen.getByLabelText("Nouvelle échéance");
    await user.type(date, "2026-11-01");
    await user.type(screen.getByLabelText("Motif"), "Retard du fournisseur");
    await user.click(screen.getByRole("button", { name: "Demander un report" }));
    const message = await screen.findByText(
      "La nouvelle échéance doit être postérieure à l'échéance courante (31/12/2026).",
    );
    expect(date).toHaveAttribute("aria-invalid", "true");
    expect(date).toHaveAccessibleDescription(message.textContent ?? "");
    expect(date).toHaveFocus();
    expect(state.posts).toEqual([]);
  });

  it("envoie la demande de report avec une date postérieure", async () => {
    const user = userEvent.setup();
    const { state } = setup("AUDITE", {
      statut: "EN_COURS",
      actions_possibles: ["DEMANDER_REPORT"],
    });
    await screen.findByRole("heading", { name: "Report d'échéance" });
    await user.type(screen.getByLabelText("Nouvelle échéance"), "2027-02-28");
    await user.type(screen.getByLabelText("Motif"), "Retard du fournisseur");
    await user.click(screen.getByRole("button", { name: "Demander un report" }));
    await waitFor(() =>
      expect(state.posts).toContainEqual({
        path: "extension",
        body: {
          action: SUIVI_ID,
          nouvelle_echeance: "2027-02-28",
          motif: "Retard du fournisseur",
        },
      }),
    );
  });

  it("lie l'erreur serveur du libellé de la preuve au champ et lui donne le focus", async () => {
    const user = userEvent.setup();
    const { ApiError } = await import("@/api/errors");
    upload.mockRejectedValue(
      new ApiError(422, "Données invalides.", { libelle: ["Libellé déjà utilisé."] }),
    );
    setup("AUDITE", { statut: "EN_COURS", actions_possibles: ["DEPOSER_PREUVE"] });
    const label = await screen.findByLabelText("Libellé de la preuve");
    await user.type(label, "Doublon");
    await user.upload(screen.getByLabelText("Fichier"), new File(["x"], "a.pdf"));
    await user.click(screen.getByRole("button", { name: "Déposer la preuve" }));
    expect(await screen.findByText("Libellé déjà utilisé.")).toBeInTheDocument();
    expect(label).toHaveAttribute("aria-invalid", "true");
    expect(label).toHaveAccessibleDescription("Libellé déjà utilisé.");
    await waitFor(() => expect(label).toHaveFocus());
  });
});

describe("ActionPage : droits", () => {
  it("n'offre pas « Vérifier » à l'auditeur déclarant", async () => {
    setup("AUDITEUR", {
      statut: "REALISEE",
      declaree_par: { ...aSuiviAction().responsable, id: 1 },
      actions_possibles: ["COMMENTER"],
    });
    await screen.findByRole("heading", { name: "Actions possibles" });
    expect(screen.queryByRole("button", { name: "Vérifier" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ajouter" })).toBeInTheDocument();
  });

  it("n'affiche aucun bouton d'action ni « Télécharger » au DG", async () => {
    setup(
      "DG",
      { statut: "EN_COURS", nombre_preuves: 1, actions_possibles: [] },
      { preuves: [{ ...preuveFixture, actions_possibles: [] }] },
    );
    expect(await screen.findByText(/1\. Rapprochement d'octobre/)).toBeInTheDocument();
    expect(
      screen.getByText("Aucune opération n'est disponible pour votre rôle sur cette action."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Télécharger/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Retirer/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Démarrer" })).not.toBeInTheDocument();
  });

  it("télécharge une preuve par l'API authentifiée", async () => {
    const user = userEvent.setup();
    server.use(
      http.get(`${BASE}/evidence/${PREUVE_ID}/download/`, () =>
        HttpResponse.arrayBuffer(new ArrayBuffer(4), {
          headers: { "Content-Disposition": 'attachment; filename="rapprochement.pdf"' },
        }),
      ),
    );
    setup(
      "AUDITE",
      { statut: "EN_COURS", nombre_preuves: 1, actions_possibles: ["COMMENTER"] },
      { preuves: [{ ...preuveFixture, actions_possibles: ["TELECHARGER"] }] },
    );
    await user.click(await screen.findByRole("button", { name: /Télécharger/ }));
    await waitFor(() => expect(download).toHaveBeenCalledTimes(1));
    expect(download.mock.calls[0]?.[1]).toBe("rapprochement.pdf");
  });

  it("montre « Saisie pour le compte de » au RAI", async () => {
    setup("RAI", { statut: "A_LANCER", actions_possibles: ["DEMARRER", "CHANGER_RESPONSABLE"] });
    expect(await screen.findByText("Saisie pour le compte de Fatou Koné")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Changer le responsable" })).toBeInTheDocument();
  });

  it("propose la décision du RAI sur un report en attente", async () => {
    const user = userEvent.setup();
    server.use(
      http.post(`${BASE}/extension-requests/:id/:decision/`, () =>
        HttpResponse.json(demandeReportFixture),
      ),
    );
    setup("RAI", {
      statut: "EN_COURS",
      demande_report_en_attente: {
        ...demandeReportFixture,
        actions_possibles: ["ACCEPTER", "REFUSER"],
      },
      actions_possibles: ["COMMENTER"],
    });
    await screen.findByText(/Demande en attente : 28\/02\/2027/);
    await user.click(screen.getByRole("button", { name: "Refuser le report" }));
    expect(
      await screen.findByText("Le commentaire est obligatoire pour un refus."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Accepter le report" })).toBeInTheDocument();
  });

  it("affiche la chronologie du plus récent au plus ancien", async () => {
    setup(
      "AUDITE",
      { statut: "EN_COURS", actions_possibles: ["COMMENTER"] },
      {
        events: [
          { ...evenementFixture, id: "e1", type: "OUVERT", le: "2026-10-01T09:00:00Z" },
          {
            ...evenementFixture,
            id: "e2",
            type: "COMMENTAIRE",
            texte: "Premier point",
            le: "2026-10-05T09:00:00Z",
            par: aSuiviAction().responsable,
          },
        ],
      },
    );
    const items = await screen.findAllByRole("listitem");
    const texts = items.map((li) => li.textContent ?? "");
    const recent = texts.findIndex((t) => t.includes("Premier point"));
    const old = texts.findIndex((t) => t.includes("Suivi ouvert"));
    expect(recent).toBeGreaterThanOrEqual(0);
    expect(recent).toBeLessThan(old);
    expect(texts[recent]).toContain("par Fatou Koné");
  });

  it("signale une erreur de chargement au lieu d'une page vide", async () => {
    server.use(
      http.get(`${BASE}/actions/${SUIVI_ID}/`, () => HttpResponse.json({}, { status: 500 })),
    );
    renderRoutes([{ path: "/recommandations/actions/:id", element: <ActionPage /> }], "RAI", {
      path: `/recommandations/actions/${SUIVI_ID}`,
    });
    expect(await screen.findByRole("alert")).toHaveTextContent("L'action n'a pas pu être chargée.");
  });
});

describe("ActionPage : accessibilité", () => {
  it("n'a aucune violation axe, dialogue ouvert compris", async () => {
    const user = userEvent.setup();
    const { container } = setup(
      "AUDITE",
      {
        statut: "EN_COURS",
        nombre_preuves: 1,
        actions_possibles: ["DECLARER_REALISEE", "DEPOSER_PREUVE", "DEMANDER_REPORT", "COMMENTER"],
      },
      { preuves: [preuveFixture] },
    );
    await screen.findByText(/1\. Rapprochement d'octobre/);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Déclarer réalisée" })).toBeEnabled(),
    );
    const rules = { rules: { "color-contrast": { enabled: false } } };
    expect((await axe(container, rules)).violations).toEqual([]);
    await user.click(screen.getByRole("button", { name: "Déclarer réalisée" }));
    await screen.findByRole("dialog");
    expect((await axe(document.body, rules)).violations).toEqual([]);
  });
});
