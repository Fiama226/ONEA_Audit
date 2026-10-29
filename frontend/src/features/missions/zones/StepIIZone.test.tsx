import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, type RequestHandler } from "msw";
import { describe, expect, it } from "vitest";
import { fr } from "@/i18n/fr";
import { API_URL } from "@/test/msw";
import {
  aMission,
  allSteps,
  MISSION_ID,
  missionHandlers,
  pageOf,
  renderMission,
} from "../testUtils";
import type { Declaration, Entretien, UtilisateurResume } from "../types";

const t = fr.missionTravaux;

const awa: UtilisateurResume = {
  id: 5,
  username: "awa.ouedraogo",
  nom_complet: "Awa Ouedraogo",
  role: "AUDITEUR",
  direction_code: "DAI",
  fonction: "",
};

function aDeclaration(overrides: Partial<Declaration> = {}): Declaration {
  return {
    id: "66666666-6666-4666-8666-666666666666",
    affectation: "44444444-4444-4444-8444-444444444444",
    mission: MISSION_ID,
    mission_reference: "MI-2026-001",
    mission_titre: "Audit des achats",
    utilisateur_detail: awa,
    role_mission: "AUDITEUR",
    statut: "EN_ATTENTE",
    levee: false,
    texte: "",
    description_conflit: "",
    confirmation: null,
    arbitrage_justification: "",
    arbitre_par: null,
    arbitre_le: null,
    ...overrides,
  } satisfies Declaration;
}

function anInterview(overrides: Partial<Entretien> = {}): Entretien {
  return {
    id: "55555555-5555-4555-8555-555555555555",
    mission: MISSION_ID,
    etape: null,
    etape_romain: null,
    objet: "Entretien",
    date_prevue: "2026-03-10T09:00:00Z",
    duree_minutes: 60,
    lieu: "",
    auditeurs: [],
    auditeurs_detail: [],
    interlocuteurs: [],
    interlocuteurs_detail: [],
    autres_interlocuteurs: "",
    themes: "",
    compte_rendu: "",
    note_synthese: "",
    statut: "PLANIFIE",
    realise_le: null,
    motif_annulation: "",
    etape_close: false,
    ...overrides,
  } satisfies Entretien;
}

const STEP_II_ID = "00000000-0000-4000-8000-000000000002";

function handlers(
  declarations: Declaration[],
  interviews: Entretien[] = [],
  extra: RequestHandler[] = [],
) {
  // msw donne priorité aux premiers handlers : les surcharges passent devant.
  return [
    ...extra,
    ...missionHandlers(aMission()),
    http.get(`${API_URL}/api/v1/meetings/`, () => HttpResponse.json(pageOf([]))),
    http.get(`${API_URL}/api/v1/interviews/`, () => HttpResponse.json(pageOf(interviews))),
    http.get(`${API_URL}/api/v1/independence-declarations/`, () =>
      HttpResponse.json(pageOf(declarations)),
    ),
  ];
}

const PATH = `/missions/${MISSION_ID}/etapes/2`;

describe("StepIIZone", () => {
  it("shows the opening meeting, the interviews calendar and the declarations link", async () => {
    renderMission(PATH, "RAI", {
      handlers: handlers([aDeclaration(), aDeclaration({ id: "x" })]),
    });
    expect(await screen.findByRole("heading", { name: t.stepIIInterviews })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Réunion d'ouverture" })).toBeInTheDocument();
    expect(
      await screen.findByText(t.declarationsPending.replace("{count}", "2")),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: t.declarationsLink })).toHaveAttribute(
      "href",
      `/missions/${MISSION_ID}/equipe`,
    );
  });

  it("does not say everything is cleared while a declared conflict is unarbitrated", async () => {
    renderMission(PATH, "RAI", {
      handlers: handlers([
        aDeclaration({ statut: "CONFIRMEE", levee: true }),
        aDeclaration({ id: "c", statut: "CONFLIT_DECLARE", levee: false }),
      ]),
    });
    expect(
      await screen.findByText(t.declarationsPending.replace("{count}", "1")),
    ).toBeInTheDocument();
    expect(screen.queryByText(t.declarationsDone)).not.toBeInTheDocument();
  });

  it("says when every declaration is cleared (confirmed or arbitrated)", async () => {
    renderMission(PATH, "RAI", {
      handlers: handlers([
        aDeclaration({ statut: "CONFIRMEE", levee: true }),
        aDeclaration({ id: "c", statut: "CONFLIT_DECLARE", levee: true }),
      ]),
    });
    expect(await screen.findByText(t.declarationsDone)).toBeInTheDocument();
  });

  it("shows the interviews of step II and planned ones without a step only", async () => {
    renderMission(PATH, "RAI", {
      handlers: handlers(
        [],
        [
          anInterview({ id: "a", objet: "De l'étape II", etape: STEP_II_ID }),
          anInterview({ id: "b", objet: "Sans étape planifié" }),
          anInterview({ id: "c", objet: "Sans étape annulé", statut: "ANNULE" }),
          anInterview({
            id: "d",
            objet: "Autre étape",
            etape: "00000000-0000-4000-8000-000000000003",
          }),
        ],
      ),
    });
    expect(await screen.findByText("De l'étape II")).toBeInTheDocument();
    expect(screen.getByText("Sans étape planifié")).toBeInTheDocument();
    expect(screen.queryByText("Sans étape annulé")).not.toBeInTheDocument();
    expect(screen.queryByText("Autre étape")).not.toBeInTheDocument();
  });

  it("shows a loading status, never an empty state or a write button, while loading", async () => {
    renderMission(PATH, "RAI", {
      handlers: handlers(
        [],
        [],
        [
          http.get(`${API_URL}/api/v1/meetings/`, async () => {
            await new Promise((r) => setTimeout(r, 300));
            return HttpResponse.json(pageOf([]));
          }),
        ],
      ),
    });
    await screen.findByRole("heading", { name: t.stepIIInterviews });
    expect(screen.queryByText(t.noMeeting)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.planMeeting })).not.toBeInTheDocument();
    expect(await screen.findByRole("button", { name: t.planMeeting })).toBeInTheDocument();
  });

  it("shows a retryable error instead of an empty state when queries fail", async () => {
    let failing = true;
    renderMission(PATH, "RAI", {
      handlers: handlers(
        [],
        [],
        [
          http.get(`${API_URL}/api/v1/meetings/`, () =>
            failing
              ? HttpResponse.json({ detail: "Erreur.", errors: {} }, { status: 500 })
              : HttpResponse.json(pageOf([])),
          ),
          http.get(`${API_URL}/api/v1/interviews/`, () =>
            HttpResponse.json({ detail: "Erreur.", errors: {} }, { status: 500 }),
          ),
          http.get(`${API_URL}/api/v1/independence-declarations/`, () =>
            HttpResponse.json({ detail: "Erreur.", errors: {} }, { status: 500 }),
          ),
        ],
      ),
    });
    const alerts = await screen.findAllByRole("alert");
    expect(alerts).toHaveLength(3);
    expect(screen.queryByText(t.noMeeting)).not.toBeInTheDocument();
    expect(screen.queryByText(t.noInterview)).not.toBeInTheDocument();
    expect(screen.queryByText(t.declarationsDone)).not.toBeInTheDocument();
    failing = false;
    await userEvent.click(screen.getAllByRole("button", { name: fr.common.retry })[0]!);
    expect(await screen.findByText(t.noMeeting)).toBeInTheDocument();
  });

  it("offers no « Planifier la réunion » on a closed step without a meeting", async () => {
    const steps = allSteps((n) => (n === 2 ? { statut: "NON_APPLICABLE" } : {}));
    renderMission(PATH, "RAI", {
      handlers: handlers([], [], missionHandlers(aMission(), steps)),
    });
    expect(await screen.findByText(t.noMeeting)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.planMeeting })).not.toBeInTheDocument();
  });
});
