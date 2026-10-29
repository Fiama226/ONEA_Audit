import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { fr } from "@/i18n/fr";
import { API_URL } from "@/test/msw";
import {
  aMission,
  allRights,
  MISSION_ID,
  missionHandlers,
  pageOf,
  renderMission,
} from "../testUtils";
import type { Affectation, Entretien, Mission, UtilisateurResume } from "../types";

const t = fr.missionTravaux;

// jsdom n'implémente pas ResizeObserver, requis par les cases à cocher Radix dans un formulaire.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

const user = (id: number, nom: string, role: UtilisateurResume["role"]): UtilisateurResume => ({
  id,
  username: nom.toLowerCase().replace(" ", "."),
  nom_complet: nom,
  role,
  direction_code: "DAI",
  fonction: "",
});
const awa = user(5, "Awa Ouedraogo", "AUDITEUR");
const issa = user(9, "Issa Traore", "AUDITEUR");
const fanta = user(12, "Fanta Sawadogo", "AUDITE");

const assignment: Affectation = {
  id: "44444444-4444-4444-8444-444444444444",
  mission: MISSION_ID,
  utilisateur: awa.id,
  utilisateur_detail: awa,
  role_mission: "AUDITEUR",
  declaration: null,
};

function anInterview(overrides: Partial<Entretien> = {}): Entretien {
  return {
    id: "55555555-5555-4555-8555-555555555555",
    mission: MISSION_ID,
    etape: null,
    etape_romain: null,
    objet: "Prise de connaissance des achats",
    date_prevue: "2026-03-10T09:00:00Z",
    duree_minutes: 60,
    lieu: "",
    auditeurs: [5],
    auditeurs_detail: [awa],
    interlocuteurs: [12],
    interlocuteurs_detail: [fanta],
    autres_interlocuteurs: "",
    themes: "",
    compte_rendu: "",
    note_synthese: "",
    statut: "PLANIFIE",
    realise_le: null,
    motif_annulation: "",
    etape_close: false,
    ...overrides,
  };
}

function handlers(interviews: Entretien[], mission: Mission = aMission({ equipe: [assignment] })) {
  return [
    ...missionHandlers(mission),
    http.get(`${API_URL}/api/v1/interviews/`, () => HttpResponse.json(pageOf(interviews))),
    http.get(`${API_URL}/api/v1/users/`, () => HttpResponse.json(pageOf([awa, issa, fanta]))),
  ];
}

const PATH = `/missions/${MISSION_ID}/entretiens`;

async function openCreate() {
  await userEvent.click(await screen.findByRole("button", { name: t.planInterview }));
  return screen.findByRole("dialog");
}

describe("InterviewsPage", () => {
  it("lists interviews sorted by date and filters by status", async () => {
    renderMission(PATH, "RAI", {
      handlers: handlers([
        anInterview({ id: "b", objet: "Second", date_prevue: "2026-03-12T09:00:00Z" }),
        anInterview({ id: "a", objet: "Premier", date_prevue: "2026-03-10T09:00:00Z" }),
        anInterview({
          id: "c",
          objet: "Annulé un",
          statut: "ANNULE",
          date_prevue: "2026-03-20T09:00:00Z",
        }),
      ]),
    });
    await screen.findByText("Premier");
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("Premier");
    expect(rows[1]).toHaveTextContent("Second");
    await userEvent.selectOptions(screen.getByLabelText(t.filterStatus), "ANNULE");
    expect(screen.queryByText("Premier")).not.toBeInTheDocument();
    expect(screen.getByText("Annulé un")).toBeInTheDocument();
  });

  it("only offers team members as auditors", async () => {
    renderMission(PATH, "RAI", { handlers: handlers([]) });
    const dialog = await openCreate();
    const group = within(dialog).getByRole("group", { name: t.auditorsLabel });
    expect(within(group).getByLabelText("Awa Ouedraogo")).toBeInTheDocument();
    expect(within(group).queryByLabelText("Issa Traore")).not.toBeInTheDocument();
  });

  it("refuses a zero duration client side", async () => {
    renderMission(PATH, "RAI", { handlers: handlers([]) });
    const dialog = await openCreate();
    await userEvent.type(within(dialog).getByLabelText(t.objectLabel), "Entretien test");
    fireEvent.change(within(dialog).getByLabelText(t.dateLabel), {
      target: { value: "2026-03-10T09:00" },
    });
    await userEvent.type(within(dialog).getByLabelText(t.durationLabel), "0");
    await userEvent.click(within(dialog).getByRole("button", { name: fr.common.save }));
    expect(await within(dialog).findByText(t.durationInvalid)).toBeInTheDocument();
  });

  it("creates an interview", async () => {
    let body: unknown;
    renderMission(PATH, "RAI", {
      handlers: [
        ...handlers([]),
        http.post(`${API_URL}/api/v1/interviews/`, async ({ request }) => {
          body = await request.json();
          return HttpResponse.json(anInterview(), { status: 201 });
        }),
      ],
    });
    const dialog = await openCreate();
    await userEvent.type(within(dialog).getByLabelText(t.objectLabel), "Entretien test");
    fireEvent.change(within(dialog).getByLabelText(t.dateLabel), {
      target: { value: "2026-03-10T09:00" },
    });
    await userEvent.type(within(dialog).getByLabelText(t.durationLabel), "45");
    await userEvent.click(
      within(within(dialog).getByRole("group", { name: t.auditorsLabel })).getByLabelText(
        "Awa Ouedraogo",
      ),
    );
    await userEvent.click(within(dialog).getByRole("button", { name: fr.common.save }));
    await waitFor(() => expect(body).toBeDefined());
    expect(body).toEqual({
      mission: MISSION_ID,
      objet: "Entretien test",
      date_prevue: "2026-03-10T09:00:00+00:00",
      etape: null,
      duree_minutes: 45,
      auditeurs: [5],
      interlocuteurs: [],
    });
  });

  it("displays the server refusal when marking done without minutes", async () => {
    renderMission(PATH, "RAI", {
      handlers: [
        ...handlers([anInterview()]),
        http.post(`${API_URL}/api/v1/interviews/:id/mark-done/`, () =>
          HttpResponse.json(
            { detail: "Le compte rendu est obligatoire.", errors: {} },
            { status: 422 },
          ),
        ),
      ],
    });
    await userEvent.click(await screen.findByRole("button", { name: new RegExp(t.markDone) }));
    const dialog = await screen.findByRole("alertdialog");
    await userEvent.click(within(dialog).getByLabelText(fr.missions.confirmCheckbox));
    await userEvent.click(within(dialog).getByRole("button", { name: t.markDone }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "Le compte rendu est obligatoire.",
    );
  });

  it("requires a reason to cancel and sends it", async () => {
    let body: unknown;
    renderMission(PATH, "RAI", {
      handlers: [
        ...handlers([anInterview()]),
        http.post(`${API_URL}/api/v1/interviews/:id/cancel/`, async ({ request }) => {
          body = await request.json();
          return HttpResponse.json(anInterview({ statut: "ANNULE" }));
        }),
      ],
    });
    await userEvent.click(
      await screen.findByRole("button", { name: new RegExp(t.cancelInterview) }),
    );
    const dialog = await screen.findByRole("alertdialog");
    await userEvent.click(within(dialog).getByRole("button", { name: t.cancelInterview }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(fr.missions.motifRequired);
    expect(body).toBeUndefined();
    await userEvent.type(within(dialog).getByLabelText(fr.missions.motifLabel), "Indisponible");
    await userEvent.click(within(dialog).getByRole("button", { name: t.cancelInterview }));
    await waitFor(() => expect(body).toEqual({ motif: "Indisponible" }));
  });

  it("shows no action to the auditee", async () => {
    renderMission(PATH, "AUDITE", {
      handlers: handlers([anInterview()], aMission({ mes_droits: allRights(false) })),
    });
    expect(await screen.findByText("Prise de connaissance des achats")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.planInterview })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: new RegExp(t.markDone) })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: new RegExp(t.enterMinutes) }),
    ).not.toBeInTheDocument();
  });

  it("prints the planning with a header and without buttons", async () => {
    renderMission(PATH, "RAI", { handlers: handlers([anInterview()]) });
    await screen.findByText("Prise de connaissance des achats");
    const title = screen.getByRole("heading", { name: t.planningTitle, hidden: true });
    expect(title.parentElement).toHaveClass("print:block");
    expect(title.parentElement).toHaveTextContent("MI-2026-001");
    const print = screen.getByRole("button", { name: t.printPlanning });
    expect(print.parentElement?.parentElement).toHaveClass("print:hidden");
    const actions = screen.getByRole("button", { name: new RegExp(t.markDone) });
    expect(actions.closest("td")).toHaveClass("print:hidden");
  });

  it("has no accessibility violation with the dialog open", async () => {
    renderMission(PATH, "RAI", { handlers: handlers([]) });
    const dialog = await openCreate();
    await within(dialog).findByLabelText("Issa Traore");
    const results = await axe(dialog, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
