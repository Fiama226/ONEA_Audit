import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { AuthContext } from "@/auth/useAuth";
import { fr } from "@/i18n/fr";
import { API_URL, server } from "@/test/msw";
import { authValueFor } from "@/test/shell";
import { MISSION_ID, pageOf, PROVISOIRE_ID } from "../testUtils";
import type { RapportProvisoire, ReponseRapport } from "../types";
import { ReponsesProvisoirePage } from "./ReponsesProvisoirePage";

const t = fr.rapportProvisoire;
const NO_CONTRAST = { rules: { "color-contrast": { enabled: false } } };
const CONSTAT_A = "cccccccc-0000-4000-8000-00000000000a";
const CONSTAT_B = "cccccccc-0000-4000-8000-00000000000b";
const TEXTE = "Je confirme que ma réponse engage mon entité.";

function aDraft(limit: string): RapportProvisoire {
  return {
    id: PROVISOIRE_ID,
    rapport: "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa",
    mission: MISSION_ID,
    numero: 1,
    transmis_le: "2026-10-21T09:00:00Z",
    transmis_par: 1,
    date_limite_reponses: limit,
    constats: [
      {
        id: CONSTAT_A,
        reference: "C-001",
        titre: "Écart de rapprochement",
        entite: "DAF",
        niveau: "ELEVE",
        a_repondre: true,
      },
      {
        id: CONSTAT_B,
        reference: "C-002",
        titre: "Autre écart",
        entite: "DAF",
        niveau: "MOYEN",
        a_repondre: false,
      },
    ],
    version_document: null,
    empreinte: "ab".repeat(32),
  } as RapportProvisoire;
}

function isoDay(offset: number): string {
  return new Date(Date.now() + offset * 86_400_000).toISOString().slice(0, 10);
}

type Setup = {
  limit?: string;
  drafts?: RapportProvisoire[];
  responses?: ReponseRapport[];
  respond?: (body: unknown) => Response;
};

function setup({ limit = isoDay(6), drafts, responses = [], respond }: Setup = {}) {
  const posted: unknown[] = [];
  server.use(
    http.get(`${API_URL}/api/v1/documents/available/`, () => HttpResponse.json([])),
    http.get(`${API_URL}/api/v1/draft-reports/`, () =>
      HttpResponse.json(pageOf(drafts ?? [aDraft(limit)])),
    ),
    http.get(`${API_URL}/api/v1/draft-report-responses/texte/`, () =>
      HttpResponse.json({ texte: TEXTE, date_limite_reponses: limit, hors_delai: false }),
    ),
    http.get(`${API_URL}/api/v1/draft-report-responses/`, () =>
      HttpResponse.json(pageOf(responses)),
    ),
    http.post(`${API_URL}/api/v1/draft-report-responses/`, async ({ request }) => {
      const body = await request.json();
      posted.push(body);
      if (respond) return respond(body);
      return HttpResponse.json(
        {
          id: "r1",
          provisoire: PROVISOIRE_ID,
          constat: CONSTAT_A,
          commentaire: "Nous acceptons.",
          confirmation: { confirme_le: "2026-11-07T10:00:00Z", empreinte: "ef".repeat(32) },
          hors_delai: true,
          texte: TEXTE,
        },
        { status: 201 },
      );
    }),
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const utils = render(
    <QueryClientProvider client={client}>
      <AuthContext.Provider value={authValueFor("AUDITE", vi.fn())}>
        <MemoryRouter initialEntries={[`/missions/${MISSION_ID}/reponses-rapport`]}>
          <Routes>
            <Route path="/missions/:id/reponses-rapport" element={<ReponsesProvisoirePage />} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
  return { ...utils, posted };
}

describe("ReponsesProvisoirePage", () => {
  it("affiche le délai restant", async () => {
    setup({ limit: isoDay(6) });
    expect(await screen.findByText(t.deadlineDays.replace("{count}", "6"))).toBeInTheDocument();
  });

  it("signale un délai dépassé", async () => {
    setup({ limit: isoDay(-2) });
    expect(await screen.findByText(t.deadlinePassed)).toBeInTheDocument();
  });

  it("ne propose « Répondre » que pour les constats à répondre", async () => {
    setup();
    expect(await screen.findByRole("button", { name: `${t.answer} C-001` })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: `${t.answer} C-002` })).not.toBeInTheDocument();
  });

  it("bloque un commentaire vide, puis envoie la réponse confirmée", async () => {
    const user = userEvent.setup();
    const { posted } = setup();
    await user.click(await screen.findByRole("button", { name: `${t.answer} C-001` }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: t.responseNext }));
    const field = within(dialog).getByLabelText(t.responseComment);
    expect(await within(dialog).findByText(t.commentRequired)).toBeInTheDocument();
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(posted).toHaveLength(0);

    await user.type(field, "Nous acceptons.");
    await user.click(within(dialog).getByRole("button", { name: t.responseNext }));

    await screen.findByText(TEXTE);
    const confirm = screen.getByRole("alertdialog");
    const checkbox = within(confirm).getByRole("checkbox", {
      name: fr.communication.confirmCheckbox,
    });
    expect(checkbox).not.toBeChecked();
    const send = within(confirm).getByRole("button", { name: t.responseConfirmLabel });
    expect(send).toBeDisabled();
    await user.click(checkbox);
    await user.click(send);
    await waitFor(() =>
      expect(posted).toEqual([
        {
          provisoire: PROVISOIRE_ID,
          constat: CONSTAT_A,
          commentaire: "Nous acceptons.",
          confirme: true,
        },
      ]),
    );
    expect(await within(confirm).findByRole("status")).toHaveTextContent("Empreinte");
  });

  it("revient au commentaire quand le serveur refuse ce champ", async () => {
    const user = userEvent.setup();
    setup({
      respond: () =>
        HttpResponse.json(
          { detail: "Invalide.", errors: { commentaire: ["Commentaire trop court."] } },
          { status: 422 },
        ),
    });
    await user.click(await screen.findByRole("button", { name: `${t.answer} C-001` }));
    let dialog = await screen.findByRole("alertdialog");
    await user.type(within(dialog).getByLabelText(t.responseComment), "x");
    await user.click(within(dialog).getByRole("button", { name: t.responseNext }));
    await screen.findByText(TEXTE);
    dialog = screen.getByRole("alertdialog");
    await user.click(within(dialog).getByRole("checkbox"));
    await user.click(within(dialog).getByRole("button", { name: t.responseConfirmLabel }));
    const field = await screen.findByLabelText(t.responseComment);
    await waitFor(() =>
      expect(field).toHaveAccessibleDescription(expect.stringContaining("Commentaire trop court.")),
    );
    expect(field).toHaveFocus();
  });

  it("liste mes réponses avec « Hors délai »", async () => {
    setup({
      responses: [
        {
          id: "r1",
          provisoire: PROVISOIRE_ID,
          constat: CONSTAT_A,
          commentaire: "Réponse déjà envoyée.",
          confirmation: { confirme_le: "2026-11-07T10:00:00Z", empreinte: "ef".repeat(32) },
          hors_delai: true,
          texte: "",
        } as unknown as ReponseRapport,
      ],
    });
    expect(await screen.findByText("Réponse déjà envoyée.")).toBeInTheDocument();
    expect(screen.getByText(t.late)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: `${t.answer} C-001` })).not.toBeInTheDocument();
  });

  it("n'affiche pas un état vide quand le chargement échoue", async () => {
    setup();
    server.use(
      http.get(`${API_URL}/api/v1/draft-reports/`, () => HttpResponse.json({}, { status: 500 })),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(t.loadError);
    expect(screen.queryByText(t.noDraft)).not.toBeInTheDocument();
  });

  it("signale l'absence de rapport provisoire", async () => {
    setup({ drafts: [] });
    expect(await screen.findByText(t.noDraft)).toBeInTheDocument();
  });

  it("n'a aucune violation axe, dialogues ouverts compris", async () => {
    const user = userEvent.setup();
    const { container } = setup();
    await user.click(await screen.findByRole("button", { name: `${t.answer} C-001` }));
    await screen.findByRole("alertdialog");
    expect((await axe(document.body, NO_CONTRAST)).violations).toEqual([]);
    const dialog = screen.getByRole("alertdialog");
    await user.type(within(dialog).getByLabelText(t.responseComment), "Ok");
    await user.click(within(dialog).getByRole("button", { name: t.responseNext }));
    await screen.findByText(TEXTE);
    expect((await axe(document.body, NO_CONTRAST)).violations).toEqual([]);
    expect(container).toBeTruthy();
  });
});
