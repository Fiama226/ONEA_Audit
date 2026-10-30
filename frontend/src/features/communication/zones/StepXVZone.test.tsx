import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { allRights, aMission, aStep } from "@/features/missions/testUtils";
import type { Reunion } from "@/features/missions/types";
import { fr } from "@/i18n/fr";
import { formatDate } from "@/lib/dates";
import { API_URL, server } from "@/test/msw";
import { deadlineIso } from "../draftQueries";
import {
  aRapport,
  MISSION_ID,
  pageOf,
  PROVISOIRE_ID,
  RAPPORT_ID,
  renderCommunication,
} from "../testUtils";
import type { RapportProvisoire, ReponseRapport } from "../types";
import { StepXVZone } from "./StepXVZone";

const t = fr.rapportProvisoire;
const NO_CONTRAST = { rules: { "color-contrast": { enabled: false } } };
const CONSTAT_A = "cccccccc-0000-4000-8000-00000000000a";
const CONSTAT_B = "cccccccc-0000-4000-8000-00000000000b";

const CLOSING = {
  id: "33333333-3333-4333-8333-333333333333",
  mission: MISSION_ID,
  type: "CLOTURE",
  date: "2026-10-20T09:00:00Z",
  lieu: "Salle A",
  ordre_du_jour: "",
  participants: [],
  participants_detail: [],
  participants_externes: "",
  decisions: "",
  compte_rendu: "",
  tenue_le: "2026-10-20T10:00:00Z",
  etape_close: false,
} as Reunion;

function aFinding(id: string, reference: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    mission: MISSION_ID,
    reference,
    titre: `Titre ${reference}`,
    statut: "VALIDE",
    niveau: "ELEVE",
    derniere_reponse: null,
    actions_possibles: [],
    ...extra,
  };
}

const DRAFT = {
  id: PROVISOIRE_ID,
  rapport: RAPPORT_ID,
  mission: MISSION_ID,
  numero: 1,
  transmis_le: "2026-10-21T09:00:00Z",
  transmis_par: 1,
  date_limite_reponses: "2026-11-05",
  constats: [
    {
      id: CONSTAT_A,
      reference: "C-001",
      titre: "Titre C-001",
      entite: "DAF",
      niveau: "ELEVE",
      a_repondre: false,
    },
    {
      id: CONSTAT_B,
      reference: "C-002",
      titre: "Titre C-002",
      entite: "DEX",
      niveau: "MOYEN",
      a_repondre: false,
    },
  ],
  version_document: null,
  empreinte: "ab".repeat(32),
} as RapportProvisoire;

const REPONSE = {
  id: "dddddddd-0000-4000-8000-000000000001",
  provisoire: PROVISOIRE_ID,
  constat: CONSTAT_A,
  auteur: { id: 7, nom_complet: "Issa Traoré" },
  commentaire: "D'accord",
  confirmation: { confirme_le: "2026-11-07T10:00:00Z", empreinte: "cd".repeat(32) },
  hors_delai: true,
  texte: "",
} as unknown as ReponseRapport;

type Setup = {
  rapport?: ReturnType<typeof aRapport> | null;
  drafts?: RapportProvisoire[];
  responses?: ReponseRapport[];
  closed?: boolean;
  failTransmit?: boolean;
};

function setup({ rapport, drafts = [], responses = [], closed = false, failTransmit }: Setup = {}) {
  const posted: unknown[] = [];
  const rap = rapport === undefined ? aRapport({ actions_possibles: ["TRANSMETTRE"] }) : rapport;
  server.use(
    http.get(`${API_URL}/api/v1/meetings/`, () => HttpResponse.json(pageOf([CLOSING]))),
    http.get(`${API_URL}/api/v1/documents/available/`, () => HttpResponse.json([])),
    http.get(`${API_URL}/api/v1/findings/`, () =>
      HttpResponse.json(
        pageOf([
          aFinding(CONSTAT_A, "C-001", {
            derniere_reponse: { position: "ACCORD", commentaire: "" },
          }),
          aFinding(CONSTAT_B, "C-002", { niveau: null }),
          aFinding("x", "C-003", { statut: "BROUILLON" }),
        ]),
      ),
    ),
    http.get(`${API_URL}/api/v1/reports/`, () => HttpResponse.json(pageOf(rap ? [rap] : []))),
    http.get(`${API_URL}/api/v1/draft-reports/`, () => HttpResponse.json(pageOf(drafts))),
    http.get(`${API_URL}/api/v1/draft-report-responses/`, () =>
      HttpResponse.json(pageOf(responses)),
    ),
    http.post(`${API_URL}/api/v1/reports/${RAPPORT_ID}/transmit-draft/`, async ({ request }) => {
      posted.push(await request.json());
      if (failTransmit) {
        return HttpResponse.json(
          { detail: "Délai invalide.", errors: { delai_jours: ["Délai refusé par le serveur."] } },
          { status: 422 },
        );
      }
      return HttpResponse.json(DRAFT, { status: 201 });
    }),
  );
  const utils = renderCommunication(
    <StepXVZone
      mission={aMission({ mes_droits: allRights(true) })}
      step={aStep({ numero: 15, romain: "XV", statut: closed ? "VALIDEE" : "EN_COURS" })}
    />,
  );
  return { ...utils, posted };
}

describe("StepXVZone", () => {
  it("liste les constats validés avec niveau et position, sans les brouillons", async () => {
    setup();
    const table = await screen.findByRole("table", { name: t.findingsLabel });
    expect(within(table).getByText("C-001")).toBeInTheDocument();
    expect(within(table).getByText("C-002")).toBeInTheDocument();
    expect(within(table).queryByText("C-003")).not.toBeInTheDocument();
    expect(within(table).getByText(t.positionNone)).toBeInTheDocument();
    expect(within(table).getByText("D'accord")).toBeInTheDocument();
  });

  it("transmet le rapport provisoire avec le délai et affiche la date limite", async () => {
    const user = userEvent.setup();
    const { posted } = setup();
    await user.click(await screen.findByRole("button", { name: t.transmit }));
    const dialog = await screen.findByRole("alertdialog");
    const delay = within(dialog).getByLabelText(t.delayLabel);
    expect(delay).toHaveValue(15);
    expect(
      within(dialog).getByText(t.deadlinePreview.replace("{date}", formatDate(deadlineIso(15)))),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText(/Réponses attendues au plus tard le \d{2}\/\d{2}\/\d{4}/),
    ).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: t.transmitSubmit }));
    await waitFor(() => expect(posted).toEqual([{ delai_jours: 15 }]));
    expect(await within(dialog).findByText(t.transmitDone)).toBeInTheDocument();
  });

  it("bloque un délai hors limites côté client", async () => {
    const user = userEvent.setup();
    const { posted } = setup();
    await user.click(await screen.findByRole("button", { name: t.transmit }));
    const dialog = await screen.findByRole("alertdialog");
    const delay = within(dialog).getByLabelText(t.delayLabel);
    await user.clear(delay);
    await user.type(delay, "90");
    await user.click(within(dialog).getByRole("button", { name: t.transmitSubmit }));
    expect(await within(dialog).findByText(t.delayInvalid)).toBeInTheDocument();
    expect(delay).toHaveAttribute("aria-invalid", "true");
    expect(delay).toHaveAccessibleDescription(expect.stringContaining(t.delayInvalid));
    expect(posted).toHaveLength(0);
  });

  it("affiche l'erreur du serveur sous le champ et y place le focus", async () => {
    const user = userEvent.setup();
    setup({ failTransmit: true });
    await user.click(await screen.findByRole("button", { name: t.transmit }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: t.transmitSubmit }));
    const delay = within(dialog).getByLabelText(t.delayLabel);
    await waitFor(() =>
      expect(delay).toHaveAccessibleDescription(expect.stringContaining("Délai refusé")),
    );
    expect(delay).toHaveFocus();
  });

  it("après transmission : tableau des réponses avec « Hors délai »", async () => {
    setup({ drafts: [DRAFT], responses: [REPONSE] });
    const table = await screen.findByRole("table", { name: t.responsesLabel });
    const rows = within(table).getAllByRole("row");
    expect(within(rows[1]!).getByText("DAF")).toBeInTheDocument();
    expect(within(rows[1]!).getByText(t.late)).toBeInTheDocument();
    expect(within(rows[2]!).getByText(t.pending)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.transmit })).not.toBeInTheDocument();
    expect(
      screen.getByText(
        /Transmis le 21\/10\/2026\. Réponses attendues au plus tard le 05\/11\/2026/,
      ),
    ).toBeInTheDocument();
  });

  it("étape close : aucun bouton d'écriture", async () => {
    setup({ closed: true });
    await screen.findByRole("table", { name: t.findingsLabel });
    await waitFor(() => expect(screen.queryByText(fr.common.loading)).not.toBeInTheDocument());
    expect(screen.queryByRole("button", { name: t.transmit })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.createReport })).not.toBeInTheDocument();
  });

  it("une erreur de chargement n'est pas rendue comme vide", async () => {
    setup();
    server.use(
      http.get(`${API_URL}/api/v1/reports/`, () => HttpResponse.json({}, { status: 500 })),
    );
    expect((await screen.findAllByRole("alert"))[0]).toHaveTextContent(t.loadError);
  });

  it("n'a aucune violation axe, dialogue ouvert compris", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(await screen.findByRole("button", { name: t.transmit }));
    await screen.findByRole("alertdialog");
    expect((await axe(document.body, NO_CONTRAST)).violations).toEqual([]);
  });
});
